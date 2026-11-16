"""
STUDYOS — Phase 1 Database Integrity, Synchronization, Migration, Concurrency & Security Test Suite.

Uses isolated temporary SQLite databases and an in-memory FakeMongoDatabase implementing
PyMongo's collection API (`find`, `find_one`, `bulk_write`, `delete_many`, `find_one_and_update`,
`create_index`) so tests never touch the live production database while exercising the real
SQLite <-> MongoDB changelog triggers, authoritative hydration, transactions, and migrations.
"""

import os
import shutil
import sqlite3
import tempfile
import threading
import unittest
from typing import Any, Dict, List
from unittest.mock import patch

from fastapi import HTTPException
from pymongo import ReplaceOne
from starlette.requests import Request

import backend.database as db_mod
import backend.mongo_sync as mongo_mod
from backend.auth import (
    create_access_token,
    ensure_user_preferences,
    get_current_user,
    hash_password,
    revoke_access_token,
)
from backend.main import LoginRequest, login


class _FakeDeleteResult:
    def __init__(self, count: int) -> None:
        self.deleted_count = count


class _FakeCollection:
    def __init__(self, name: str) -> None:
        self.name = name
        self.docs: Dict[str, Dict[str, Any]] = {}
        self.indexes: List[Dict[str, Any]] = []

    def create_index(self, keys: Any, unique: bool = False, name: str = "") -> str:
        self.indexes.append({"keys": keys, "unique": unique, "name": name})
        return name or "idx"

    def find(self, filt: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        filt = filt or {}
        if not filt:
            return [dict(d) for d in self.docs.values()]
        out = []
        for doc in self.docs.values():
            if all(doc.get(k) == v for k, v in filt.items()):
                out.append(dict(doc))
        return out

    def find_one(self, filt: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        for doc in self.docs.values():
            if all(doc.get(k) == v for k, v in filt.items()):
                return dict(doc)
        return None

    def bulk_write(self, ops: List[ReplaceOne], ordered: bool = False) -> None:
        _ = ordered
        for op in ops:
            doc_id = str(op._filter["_id"])
            self.docs[doc_id] = dict(op._doc)

    def delete_many(self, filt: Dict[str, Any]) -> _FakeDeleteResult:
        in_ids = (filt.get("_id") or {}).get("$in")
        if in_ids is not None:
            removed = 0
            for doc_id in list(in_ids):
                if str(doc_id) in self.docs:
                    del self.docs[str(doc_id)]
                    removed += 1
            return _FakeDeleteResult(removed)
        nin_ids = (filt.get("_id") or {}).get("$nin")
        if nin_ids is not None:
            keep = set(str(x) for x in nin_ids)
            removed = 0
            for doc_id in list(self.docs.keys()):
                if doc_id not in keep:
                    del self.docs[doc_id]
                    removed += 1
            return _FakeDeleteResult(removed)
        return _FakeDeleteResult(0)

    def find_one_and_update(
        self,
        filt: Dict[str, Any],
        update: Dict[str, Any],
        upsert: bool = False,
        return_document: Any = None,
    ) -> Optional[Dict[str, Any]]:
        _ = return_document
        doc_id = str(filt.get("_id"))
        doc = self.docs.get(doc_id)
        if doc is None:
            if not upsert:
                return None
            doc = {"_id": doc_id}
        inc = update.get("$inc") or {}
        for k, v in inc.items():
            doc[k] = int(doc.get(k) or 0) + int(v)
        self.docs[doc_id] = doc
        return dict(doc)


class _FakeMongoDB:
    def __init__(self, name: str = "studyos_test_fake") -> None:
        self.name = name
        self.collections: Dict[str, _FakeCollection] = {}

    def __getitem__(self, item: str) -> _FakeCollection:
        if item not in self.collections:
            self.collections[item] = _FakeCollection(item)
        return self.collections[item]

    def command(self, cmd: str) -> Dict[str, Any]:
        if cmd == "ping":
            return {"ok": 1}
        return {"ok": 1}


class TestPhase1DatabaseIntegrity(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.mkdtemp(prefix="studyos_p1_test_")
        self.fake_db = _FakeMongoDB()
        mongo_mod.clear_cached_sync_seq()
        db_mod._INITIALIZED_SCHEMA_PATHS.clear()

    def tearDown(self) -> None:
        mongo_mod.clear_cached_sync_seq()
        db_mod._INITIALIZED_SCHEMA_PATHS.clear()
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _seed_fake_user(self, uid: str, email: str, name: str, pw_hash: str) -> None:
        now = db_mod.utc_now()
        self.fake_db["users"].docs[uid] = {
            "_id": uid,
            "id": uid,
            "email": email,
            "name": name,
            "password_hash": pw_hash,
            "role": "student",
            "target_role": "Full Stack Developer",
            "bio": "",
            "avatar_color": "#d6b56d",
            "avatar_url": "",
            "email_verified": 1,
            "created_at": now,
            "updated_at": now,
        }
        self.fake_db["user_preferences"].docs[uid] = {
            "_id": uid,
            "user_id": uid,
            "ai_provider": "auto",
            "gemini_model": "gemini-2.5-flash",
            "openai_model": "gpt-4o-mini",
            "anthropic_model": "claude-3-5-sonnet-latest",
            "default_skill_level": "Intermediate",
            "study_hours_per_week": 12,
            "auto_generate_policy": "all_async",
            "show_demo_data": 0,
            "reduced_motion": 0,
            "theme": "midnight_luxe",
            "preferred_language": "English",
            "music_last_track_id": "builtin_study_gentle",
            "music_last_category": "all",
            "music_volume": 0.65,
            "music_playback_enabled": 0,
            "music_last_position": 0.0,
            "updated_at": now,
        }
        mongo_mod.bump_mongo_global_seq(self.fake_db)

    def test_01_production_rejects_missing_mongodb_uri_no_silent_sqlite_fallback(self) -> None:
        """Production must explicitly fail if MONGODB_URI is missing rather than silently using /tmp SQLite."""
        with patch.dict(
            os.environ,
            {
                "STUDYOS_ENV": "production",
                "VERCEL": "1",
                "MONGODB_URI": "",
                "MONGO_URI": "",
                "AETHER_DB_PATH": os.path.join(self.tmp_dir, "aetherlearn.db"),
            },
            clear=False,
        ):
            os.environ.pop("BRAINOVA_ALLOW_EPHEMERAL_SQLITE_FOR_TESTS", None)
            os.environ.pop("BRAINOVA_DISABLE_MONGO_SYNC", None)
            with patch.object(mongo_mod, "get_mongodb_uri", return_value=""):
                with self.assertRaises(mongo_mod.DatabaseConfigurationError):
                    db_mod.validate_database_configuration()

    def test_02_aud01_empty_or_partial_local_sqlite_never_deletes_other_cloud_users(self) -> None:
        """
        AUD-01 Regression Test:
        Two users exist in MongoDB Atlas. A fresh Vercel instance boots with an empty /tmp SQLite DB,
        logs in User 1, and triggers a write. User 2 MUST remain untouched in MongoDB Atlas.
        """
        pw_hash = hash_password("Password123!")
        self._seed_fake_user("usr_1", "user1@example.com", "User One", pw_hash)
        self._seed_fake_user("usr_2", "user2@example.com", "User Two", pw_hash)

        prod_tmp_db = os.path.join(self.tmp_dir, "aetherlearn.db")
        with patch.dict(
            os.environ,
            {
                "STUDYOS_ENV": "production",
                "VERCEL": "1",
                "MONGODB_URI": "mongodb+srv://fake-test",
                "AETHER_DB_PATH": prod_tmp_db,
            },
            clear=False,
        ):
            with patch.object(mongo_mod, "get_mongo_database", return_value=self.fake_db):
                req = Request({"type": "http", "headers": [], "query_string": b"", "client": ("127.0.0.1", 9000)})
                res = login(LoginRequest(email="user1@example.com", password="Password123!"), req)
                self.assertEqual(res["user"]["email"], "user1@example.com")

                # Update user 1's bio (triggers commit + apply_changelog_to_mongo)
                with db_mod.get_db(commit=True) as conn:
                    conn.execute("UPDATE users SET bio = ? WHERE id = ?", ("Updated bio", "usr_1"))

                # Assert User 2 is STILL intact in MongoDB Atlas!
                self.assertIn("usr_1", self.fake_db["users"].docs)
                self.assertIn("usr_2", self.fake_db["users"].docs)
                self.assertEqual(len(self.fake_db["users"].docs), 2)
                self.assertEqual(self.fake_db["users"].docs["usr_1"]["bio"], "Updated bio")

    def test_03_aud02_deleting_last_record_prevents_resurrection_across_restarts(self) -> None:
        """
        AUD-02 Regression Test:
        Deleting the ONLY record in a table deletes it from MongoDB Atlas and it NEVER reappears
        even after wiping /tmp SQLite (simulating a cold-start container restart).
        """
        pw_hash = hash_password("Password123!")
        self._seed_fake_user("usr_1", "user1@example.com", "User One", pw_hash)

        prod_tmp_db = os.path.join(self.tmp_dir, "aetherlearn.db")
        with patch.dict(
            os.environ,
            {
                "STUDYOS_ENV": "production",
                "VERCEL": "1",
                "MONGODB_URI": "mongodb+srv://fake-test",
                "AETHER_DB_PATH": prod_tmp_db,
            },
            clear=False,
        ):
            with patch.object(mongo_mod, "get_mongo_database", return_value=self.fake_db):
                # Create the single record in personal_notes
                with db_mod.get_db(commit=True) as conn:
                    conn.execute(
                        "INSERT INTO personal_notes (id, user_id, title, content, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                        ("note_only", "usr_1", "Only Note", "Secret body", db_mod.utc_now(), db_mod.utc_now()),
                    )
                self.assertEqual(len(self.fake_db["personal_notes"].docs), 1)

                # Delete that ONLY record
                with db_mod.get_db(commit=True) as conn:
                    conn.execute("DELETE FROM personal_notes WHERE id = ?", ("note_only",))

                # Authoritative MongoDB collection MUST now be empty
                self.assertEqual(len(self.fake_db["personal_notes"].docs), 0)

                # Simulate cold-start container wipe of /tmp SQLite
                for suffix in ("", "-wal", "-shm"):
                    p = prod_tmp_db + suffix
                    if os.path.exists(p):
                        os.remove(p)
                db_mod._INITIALIZED_SCHEMA_PATHS.clear()
                mongo_mod.clear_cached_sync_seq()

                # Read after restart: deleted record must NEVER reappear
                with db_mod.get_db(commit=False) as conn:
                    rows = conn.execute("SELECT * FROM personal_notes").fetchall()
                    self.assertEqual(rows, [])

    def test_04_cascade_delete_propagates_to_authoritative_mongo(self) -> None:
        """ON DELETE CASCADE in SQLite propagates child deletions cleanly to MongoDB Atlas."""
        pw_hash = hash_password("Password123!")
        self._seed_fake_user("usr_1", "user1@example.com", "User One", pw_hash)
        prod_tmp_db = os.path.join(self.tmp_dir, "aetherlearn.db")

        with patch.dict(
            os.environ,
            {
                "STUDYOS_ENV": "production",
                "VERCEL": "1",
                "MONGODB_URI": "mongodb+srv://fake-test",
                "AETHER_DB_PATH": prod_tmp_db,
            },
            clear=False,
        ):
            with patch.object(mongo_mod, "get_mongo_database", return_value=self.fake_db):
                now = db_mod.utc_now()
                with db_mod.get_db(commit=True) as conn:
                    conn.execute(
                        "INSERT INTO roadmaps (id, user_id, title, target_role, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                        ("rm_1", "usr_1", "Backend", "Backend Dev", now, now),
                    )
                    conn.execute(
                        "INSERT INTO roadmap_phases (id, roadmap_id, user_id, phase_order, title, created_at, updated_at) VALUES (?, ?, ?, 1, ?, ?, ?)",
                        ("ph_1", "rm_1", "usr_1", "Phase 1", now, now),
                    )
                self.assertIn("rm_1", self.fake_db["roadmaps"].docs)
                self.assertIn("ph_1", self.fake_db["roadmap_phases"].docs)

                # Delete parent roadmap -> child phase must cascade delete in BOTH SQLite and MongoDB
                with db_mod.get_db(commit=True) as conn:
                    conn.execute("DELETE FROM roadmaps WHERE id = ?", ("rm_1",))

                self.assertNotIn("rm_1", self.fake_db["roadmaps"].docs)
                self.assertNotIn("ph_1", self.fake_db["roadmap_phases"].docs)

    def test_05_multi_instance_serverless_consistency_via_global_seq(self) -> None:
        """Two separate Vercel instances sharing MongoDB Atlas stay consistent on writes and deletes."""
        pw_hash = hash_password("Password123!")
        self._seed_fake_user("usr_1", "user1@example.com", "User One", pw_hash)

        container_a_db = os.path.join(self.tmp_dir, "container_a", "aetherlearn.db")
        container_b_db = os.path.join(self.tmp_dir, "container_b", "aetherlearn.db")

        with patch.dict(
            os.environ,
            {"STUDYOS_ENV": "production", "VERCEL": "1", "MONGODB_URI": "mongodb+srv://fake-test"},
            clear=False,
        ):
            with patch.object(mongo_mod, "get_mongo_database", return_value=self.fake_db):
                # Container A writes a note
                with patch.dict(os.environ, {"AETHER_DB_PATH": container_a_db}):
                    with db_mod.get_db(commit=True) as conn:
                        conn.execute(
                            "INSERT INTO personal_notes (id, user_id, title, content, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                            ("note_shared", "usr_1", "Shared Note", "Hello", db_mod.utc_now(), db_mod.utc_now()),
                        )

                # Container B reads it cleanly
                with patch.dict(os.environ, {"AETHER_DB_PATH": container_b_db}):
                    with db_mod.get_db(commit=False) as conn:
                        row = conn.execute("SELECT title FROM personal_notes WHERE id = ?", ("note_shared",)).fetchone()
                        self.assertEqual(row["title"], "Shared Note")

                # Container A deletes the note
                with patch.dict(os.environ, {"AETHER_DB_PATH": container_a_db}):
                    with db_mod.get_db(commit=True) as conn:
                        conn.execute("DELETE FROM personal_notes WHERE id = ?", ("note_shared",))

                # Warm Container B detects global_seq change and removes the deleted note
                with patch.dict(os.environ, {"AETHER_DB_PATH": container_b_db}):
                    with db_mod.get_db(commit=False) as conn:
                        row_after = conn.execute("SELECT title FROM personal_notes WHERE id = ?", ("note_shared",)).fetchone()
                        self.assertIsNone(row_after)

    def test_06_failed_transaction_rolls_back_and_never_touches_mongo(self) -> None:
        """If an exception occurs mid-transaction, SQLite rolls back and MongoDB is untouched."""
        pw_hash = hash_password("Password123!")
        self._seed_fake_user("usr_1", "user1@example.com", "User One", pw_hash)
        prod_tmp_db = os.path.join(self.tmp_dir, "aetherlearn.db")

        with patch.dict(
            os.environ,
            {
                "STUDYOS_ENV": "production",
                "VERCEL": "1",
                "MONGODB_URI": "mongodb+srv://fake-test",
                "AETHER_DB_PATH": prod_tmp_db,
            },
            clear=False,
        ):
            with patch.object(mongo_mod, "get_mongo_database", return_value=self.fake_db):
                with self.assertRaises(RuntimeError):
                    with db_mod.get_db(commit=True) as conn:
                        conn.execute(
                            "INSERT INTO personal_notes (id, user_id, title, content, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                            ("note_abort", "usr_1", "Aborted", "Body", db_mod.utc_now(), db_mod.utc_now()),
                        )
                        raise RuntimeError("Simulated failure before commit")

                self.assertNotIn("note_abort", self.fake_db["personal_notes"].docs)
                with db_mod.get_db(commit=False) as conn:
                    self.assertIsNone(
                        conn.execute("SELECT id FROM personal_notes WHERE id = 'note_abort'").fetchone()
                    )

    def test_07_versioned_migrations_are_ordered_and_idempotent(self) -> None:
        """Fresh initialization and repeated run_migrations record versions cleanly without data loss."""
        test_db = os.path.join(self.tmp_dir, "migrations_test.db")
        with patch.dict(os.environ, {"AETHER_DB_PATH": test_db, "STUDYOS_ENV": "test"}, clear=False):
            db_mod.init_db()
            with db_mod.get_db(commit=True) as conn:
                versions_1 = [
                    r["version"]
                    for r in conn.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()
                ]
                self.assertEqual(versions_1, [1, 2, 3])
                db_mod.run_migrations(conn)
                versions_2 = [
                    r["version"]
                    for r in conn.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()
                ]
                self.assertEqual(versions_2, [1, 2, 3])

    def test_08_login_rate_limiting_and_avatar_url_persistence(self) -> None:
        """Login returns avatar_url and enforces HTTP 429 rate limiting after repeated failed attempts."""
        pw_hash = hash_password("CorrectPassword123!")
        self._seed_fake_user("usr_rl", "rl_test@example.com", "RL User", pw_hash)
        self.fake_db["users"].docs["usr_rl"]["avatar_url"] = "data:image/png;base64,AAAA"

        prod_tmp_db = os.path.join(self.tmp_dir, "aetherlearn.db")
        with patch.dict(
            os.environ,
            {
                "STUDYOS_ENV": "production",
                "VERCEL": "1",
                "MONGODB_URI": "mongodb+srv://fake-test",
                "AETHER_DB_PATH": prod_tmp_db,
            },
            clear=False,
        ):
            with patch.object(mongo_mod, "get_mongo_database", return_value=self.fake_db):
                req = Request({"type": "http", "headers": [], "query_string": b"", "client": ("10.0.0.5", 1234)})

                # Valid login returns avatar_url
                ok_res = login(LoginRequest(email="rl_test@example.com", password="CorrectPassword123!"), req)
                self.assertEqual(ok_res["user"]["avatar_url"], "data:image/png;base64,AAAA")

                # 15 failed attempts return 401; 16th returns 429
                for _ in range(15):
                    with self.assertRaises(HTTPException) as ctx:
                        login(LoginRequest(email="rl_test@example.com", password="WrongPassword!"), req)
                    self.assertEqual(ctx.exception.status_code, 401)

                with self.assertRaises(HTTPException) as ctx_429:
                    login(LoginRequest(email="rl_test@example.com", password="WrongPassword!"), req)
                self.assertEqual(ctx_429.exception.status_code, 429)

    def test_09_logout_token_revocation_persists_across_containers(self) -> None:
        """Revoking a JWT on Container A immediately blocks that token on Container B."""
        pw_hash = hash_password("Password123!")
        self._seed_fake_user("usr_rev", "rev@example.com", "Rev User", pw_hash)

        container_a_db = os.path.join(self.tmp_dir, "c_a", "aetherlearn.db")
        container_b_db = os.path.join(self.tmp_dir, "c_b", "aetherlearn.db")
        token = create_access_token("usr_rev", "rev@example.com")
        req = Request({"type": "http", "headers": [], "query_string": b"", "client": ("127.0.0.1", 8000)})

        with patch.dict(
            os.environ,
            {"STUDYOS_ENV": "production", "VERCEL": "1", "MONGODB_URI": "mongodb+srv://fake-test"},
            clear=False,
        ):
            with patch.object(mongo_mod, "get_mongo_database", return_value=self.fake_db):
                with patch.dict(os.environ, {"AETHER_DB_PATH": container_a_db}):
                    revoke_access_token(token, expected_user_id="usr_rev")

                with patch.dict(os.environ, {"AETHER_DB_PATH": container_b_db}):
                    with self.assertRaises(HTTPException) as ctx_unauth:
                        get_current_user(req, authorization=f"Bearer {token}")
                    self.assertEqual(ctx_unauth.exception.status_code, 401)

    def test_10_concurrent_unique_email_prevents_duplicates(self) -> None:
        """Unique email constraint prevents duplicate user records under concurrent writes."""
        test_db = os.path.join(self.tmp_dir, "concurrency.db")
        with patch.dict(os.environ, {"AETHER_DB_PATH": test_db, "STUDYOS_ENV": "test"}, clear=False):
            db_mod.init_db()
            pw_hash = hash_password("Password123!")
            now = db_mod.utc_now()
            errors: List[Exception] = []
            successes: List[str] = []
            lock = threading.Lock()

            def _worker(idx: int) -> None:
                try:
                    with db_mod.get_db(commit=True) as conn:
                        conn.execute(
                            """
                            INSERT INTO users (id, email, name, password_hash, role, target_role, bio, avatar_color, created_at, updated_at)
                            VALUES (?, ?, ?, ?, 'student', 'Dev', '', '#6366f1', ?, ?)
                            """,
                            (f"usr_conc_{idx}", "same_email@example.com", f"User {idx}", pw_hash, now, now),
                        )
                    with lock:
                        successes.append(f"usr_conc_{idx}")
                except sqlite3.IntegrityError as exc:
                    with lock:
                        errors.append(exc)

            threads = [threading.Thread(target=_worker, args=(i,)) for i in range(4)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            self.assertEqual(len(successes), 1)
            self.assertEqual(len(errors), 3)


if __name__ == "__main__":
    unittest.main()
