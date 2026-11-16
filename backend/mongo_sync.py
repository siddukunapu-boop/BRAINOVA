"""
STUDYOS — MongoDB Atlas Authoritative Cloud Persistence & Synchronization Layer

Architecture Guarantees (Phase 1):
1. Authoritative Production Database: In production (VERCEL=1 / STUDYOS_ENV=production),
   MongoDB Atlas is the single authoritative database. Ephemeral /tmp SQLite acts strictly
   as a per-request/container relational query cache hydrated from MongoDB.
2. Zero Destructive Sync: Never deletes MongoDB records based on missing rows in an
   empty or partially hydrated local SQLite file (eliminates AUD-01).
3. Zero Record Resurrection: Every INSERT, UPDATE, and DELETE (including ON DELETE CASCADE)
   is captured via SQLite TEMP triggers into a transactional changelog and applied
   synchronously (upserts + explicit delete_many by PK) to MongoDB before returning (eliminates AUD-02 & AUD-03).
4. Multi-Instance Consistency: Uses an atomic `_meta_sync.global_seq` counter in MongoDB
   so warm serverless containers detect remote writes/deletes immediately.
"""

from concurrent.futures import ThreadPoolExecutor
import logging
import os
import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_logger = logging.getLogger("studyos.mongo_sync")


class DatabaseConfigurationError(RuntimeError):
    """Raised when required database configuration for the current environment is invalid or missing."""


class DatabaseUnavailableError(RuntimeError):
    """Raised when the authoritative database cannot be reached or fails a write/read operation."""


# Topological order (parents before children) for safe SQLite hydration and MongoDB indexing.
SYNC_TABLES: List[tuple[str, str]] = [
    ("users", "id"),
    ("user_preferences", "user_id"),
    ("pending_registrations", "id"),
    ("registration_rate_limits", "rate_key"),
    ("login_rate_limits", "rate_key"),
    ("revoked_tokens", "jti"),
    ("roadmaps", "id"),
    ("roadmap_phases", "id"),
    ("roadmap_topics", "id"),
    ("topic_tutorials", "id"),
    ("topic_readings", "id"),
    ("mcq_sets", "id"),
    ("quiz_attempts", "id"),
    ("studio_outputs", "id"),
    ("flashcards", "id"),
    ("personal_notes", "id"),
    ("sources", "id"),
    ("source_chunks", "id"),
    ("generation_jobs", "id"),
    ("activity_logs", "id"),
    ("diary_entries", "id"),
    ("study_journal_entries", "id"),
    ("focus_sessions", "id"),
    ("focus_events", "id"),
    ("career_profiles", "user_id"),
    ("career_skill_assessments", "id"),
    ("mentor_rate_limits", "user_id,window_start_epoch"),
    ("ai_conversations", "id"),
    ("tech_pulse_sources", "id"),
    ("tech_pulse_stories", "id"),
    ("tech_pulse_daily_feed", "ist_date,story_id"),
    ("tech_pulse_bookmarks", "id"),
    ("user_music_tracks", "id"),
]

SYNC_TABLE_PK_MAP: Dict[str, str] = dict(SYNC_TABLES)

_CLIENT_LOCK = threading.Lock()
_MONGO_CLIENT: Any = None
_MONGO_URI_CACHED: str = ""
_INDEXES_ENSURED_FOR_DB: str = ""
_CONTAINER_SYNC_SEQ: Dict[str, int] = {}
_HYDRATE_LOCK = threading.Lock()


def _load_env_if_needed() -> None:
    if os.environ.get("MONGODB_URI") or os.environ.get("MONGO_URI"):
        return
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if not env_file.is_file():
        return
    try:
        for raw_line in env_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k = k.strip()
            v = v.strip()
            if len(v) >= 2 and ((v[0] == v[-1] == '"') or (v[0] == v[-1] == "'")):
                v = v[1:-1]
            if k:
                os.environ.setdefault(k, v)
    except OSError:
        pass


def get_mongodb_uri() -> str:
    _load_env_if_needed()
    return (os.environ.get("MONGODB_URI") or os.environ.get("MONGO_URI") or "").strip()


def get_mongodb_db_name() -> str:
    return (os.environ.get("MONGODB_DB_NAME") or "brainova").strip() or "brainova"


def get_mongo_database(require_configured: bool = False) -> Optional[Any]:
    global _MONGO_CLIENT, _MONGO_URI_CACHED, _INDEXES_ENSURED_FOR_DB
    uri = get_mongodb_uri()
    if not uri:
        if require_configured:
            raise DatabaseConfigurationError(
                "Production database configuration is missing (MONGODB_URI)."
            )
        return None
    try:
        from pymongo import MongoClient
    except ImportError as exc:
        if require_configured:
            raise DatabaseConfigurationError("pymongo driver is not installed.") from exc
        return None

    with _CLIENT_LOCK:
        if _MONGO_CLIENT is None or _MONGO_URI_CACHED != uri:
            _MONGO_CLIENT = MongoClient(
                uri,
                serverSelectionTimeoutMS=4000,
                connectTimeoutMS=4000,
                socketTimeoutMS=8000,
                maxPoolSize=10,
                minPoolSize=0,
                retryWrites=True,
            )
            _MONGO_URI_CACHED = uri
            _INDEXES_ENSURED_FOR_DB = ""
        db = _MONGO_CLIENT[get_mongodb_db_name()]
        if _INDEXES_ENSURED_FOR_DB != db.name:
            try:
                ensure_mongo_indexes(db)
                _INDEXES_ENSURED_FOR_DB = db.name
            except Exception as exc:
                _logger.warning("Mongo index initialization deferred: %s", type(exc).__name__)
        return db


def ensure_mongo_indexes(db: Any) -> None:
    """Create idempotent unique and query indexes on authoritative MongoDB collections."""
    from pymongo import ASCENDING, DESCENDING

    db["users"].create_index([("email", ASCENDING)], unique=True, name="idx_users_email_unique")
    db["user_preferences"].create_index([("user_id", ASCENDING)], unique=True, name="idx_prefs_user_unique")
    db["revoked_tokens"].create_index([("jti", ASCENDING)], unique=True, name="idx_revoked_jti_unique")
    db["revoked_tokens"].create_index([("expires_at", ASCENDING)], name="idx_revoked_exp")
    db["pending_registrations"].create_index([("pending_token", ASCENDING)], name="idx_pending_token")
    db["pending_registrations"].create_index([("email", ASCENDING)], name="idx_pending_email")
    db["roadmaps"].create_index([("user_id", ASCENDING), ("updated_at", DESCENDING)], name="idx_roadmaps_user")
    db["ai_conversations"].create_index(
        [("user_id", ASCENDING), ("context_type", ASCENDING), ("updated_at", DESCENDING)],
        name="idx_conv_user",
    )
    db["tech_pulse_bookmarks"].create_index(
        [("user_id", ASCENDING), ("story_id", ASCENDING)],
        unique=True,
        name="idx_tp_bookmark_unique",
    )
    db["user_music_tracks"].create_index(
        [("user_id", ASCENDING), ("created_at", DESCENDING)],
        name="idx_music_user",
    )


def check_mongo_connection() -> Dict[str, Any]:
    db = get_mongo_database()
    if db is None:
        return {"configured": False, "connected": False}
    try:
        db.command("ping")
        return {"configured": True, "connected": True, "database": db.name}
    except Exception as exc:
        return {"configured": True, "connected": False, "error": type(exc).__name__}


def get_mongo_global_seq(db: Any) -> int:
    doc = db["_meta_sync"].find_one({"_id": "global_seq"})
    if not doc:
        return 0
    return int(doc.get("seq") or 0)


def bump_mongo_global_seq(db: Any) -> int:
    from pymongo import ReturnDocument

    res = db["_meta_sync"].find_one_and_update(
        {"_id": "global_seq"},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return int((res or {}).get("seq") or 1)


def get_cached_sync_seq(db_path: str) -> Optional[int]:
    return _CONTAINER_SYNC_SEQ.get(db_path)


def set_cached_sync_seq(db_path: str, seq: int) -> None:
    _CONTAINER_SYNC_SEQ[db_path] = seq


def clear_cached_sync_seq(db_path: Optional[str] = None) -> None:
    if db_path is None:
        _CONTAINER_SYNC_SEQ.clear()
    else:
        _CONTAINER_SYNC_SEQ.pop(db_path, None)


def _insert_mongo_docs_into_sqlite(conn: sqlite3.Connection, table_name: str, docs: List[Dict[str, Any]]) -> int:
    if not docs:
        return 0
    col_info = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    valid_cols = [c["name"] if isinstance(c, dict) else c[1] for c in col_info]
    if not valid_cols:
        return 0
    placeholders = ", ".join(["?"] * len(valid_cols))
    col_list_sql = ", ".join(valid_cols)
    sql = f"INSERT OR REPLACE INTO {table_name} ({col_list_sql}) VALUES ({placeholders})"
    rows_to_insert = [tuple(doc.get(c) for c in valid_cols) for doc in docs]
    conn.executemany(sql, rows_to_insert)
    return len(rows_to_insert)


def hydrate_sqlite_from_mongo_authoritative(conn: sqlite3.Connection, db_path: str) -> int:
    """
    Pull authoritative state from MongoDB Atlas into the local /tmp SQLite cache when:
    - Cold start (db_path not yet hydrated), OR
    - Remote global_seq changed due to another serverless instance writing/deleting.

    Deletes stale rows from the local /tmp SQLite cache so deleted MongoDB records
    can NEVER resurrect, while never deleting anything in MongoDB Atlas.
    """
    db = get_mongo_database(require_configured=True)
    with _HYDRATE_LOCK:
        try:
            remote_seq = get_mongo_global_seq(db)
        except Exception as exc:
            raise DatabaseUnavailableError(
                f"Unable to reach authoritative database ({type(exc).__name__})."
            ) from exc

        if _CONTAINER_SYNC_SEQ.get(db_path) == remote_seq:
            return remote_seq

        def _fetch_table(item: tuple[str, str]) -> tuple[str, List[Dict[str, Any]]]:
            t_name, _ = item
            return t_name, list(db[t_name].find({}))

        try:
            with ThreadPoolExecutor(max_workers=8) as pool:
                fetched = list(pool.map(_fetch_table, SYNC_TABLES))
        except Exception as exc:
            raise DatabaseUnavailableError(
                f"Failed to read authoritative state from database ({type(exc).__name__})."
            ) from exc

        conn.execute("PRAGMA foreign_keys = OFF;")
        try:
            # Clear local ephemeral cache tables in reverse topological order, then populate in forward order
            for table_name, _ in reversed(SYNC_TABLES):
                try:
                    conn.execute(f"DELETE FROM {table_name}")
                except sqlite3.Error:
                    pass
            for table_name, docs in fetched:
                if docs:
                    _insert_mongo_docs_into_sqlite(conn, table_name, docs)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.execute("PRAGMA foreign_keys = ON;")

        _CONTAINER_SYNC_SEQ[db_path] = remote_seq
        return remote_seq


def install_changelog_triggers(conn: sqlite3.Connection) -> None:
    """
    Install TEMP triggers on all synced tables so every INSERT, UPDATE, and DELETE
    (including ON DELETE CASCADE) within a transaction is recorded in _mongo_changelog.
    """
    conn.execute("PRAGMA recursive_triggers = ON;")
    conn.execute(
        """
        CREATE TEMP TABLE IF NOT EXISTS _mongo_changelog (
            seq INTEGER PRIMARY KEY AUTOINCREMENT,
            tbl TEXT NOT NULL,
            op TEXT NOT NULL,
            pk TEXT NOT NULL
        )
        """
    )
    conn.execute("DELETE FROM _mongo_changelog")

    existing = {
        row["name"] if isinstance(row, dict) else row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_temp_master WHERE type = 'trigger'"
        ).fetchall()
    }

    for table_name, pk_col in SYNC_TABLES:
        pk_cols = [c.strip() for c in pk_col.split(",") if c.strip()]
        if len(pk_cols) == 1:
            new_pk_expr = f"CAST(NEW.{pk_cols[0]} AS TEXT)"
            old_pk_expr = f"CAST(OLD.{pk_cols[0]} AS TEXT)"
        else:
            new_pk_expr = " || ':' || ".join(f"CAST(NEW.{c} AS TEXT)" for c in pk_cols)
            old_pk_expr = " || ':' || ".join(f"CAST(OLD.{c} AS TEXT)" for c in pk_cols)

        t_ins = f"_chg_ins_{table_name}"
        t_upd = f"_chg_upd_{table_name}"
        t_del = f"_chg_del_{table_name}"

        if t_ins not in existing:
            conn.execute(
                f"CREATE TEMP TRIGGER {t_ins} AFTER INSERT ON {table_name} "
                f"BEGIN INSERT INTO _mongo_changelog(tbl, op, pk) VALUES ('{table_name}', 'U', {new_pk_expr}); END"
            )
        if t_upd not in existing:
            conn.execute(
                f"CREATE TEMP TRIGGER {t_upd} AFTER UPDATE ON {table_name} "
                f"BEGIN INSERT INTO _mongo_changelog(tbl, op, pk) VALUES ('{table_name}', 'U', {new_pk_expr}); END"
            )
        if t_del not in existing:
            conn.execute(
                f"CREATE TEMP TRIGGER {t_del} AFTER DELETE ON {table_name} "
                f"BEGIN INSERT INTO _mongo_changelog(tbl, op, pk) VALUES ('{table_name}', 'D', {old_pk_expr}); END"
            )


def apply_changelog_to_mongo(conn: sqlite3.Connection, db_path: str) -> int:
    """
    Synchronously push ONLY the exact row upserts and deletes captured in `_mongo_changelog`
    during the current committed transaction to MongoDB Atlas.
    Never performs whole-table diffs or $nin deletions.
    """
    rows = conn.execute("SELECT tbl, op, pk FROM _mongo_changelog ORDER BY seq ASC").fetchall()
    conn.execute("DELETE FROM _mongo_changelog")
    if not rows:
        return 0

    # Coalesce multiple mutations to the same (tbl, pk) in chronological order
    final_ops: Dict[tuple[str, str], str] = {}
    for r in rows:
        tbl = r["tbl"] if isinstance(r, dict) else r[0]
        op = r["op"] if isinstance(r, dict) else r[1]
        pk = r["pk"] if isinstance(r, dict) else r[2]
        final_ops[(tbl, pk)] = op

    by_table: Dict[str, Dict[str, List[str]]] = {}
    for (tbl, pk), op in final_ops.items():
        bucket = by_table.setdefault(tbl, {"U": [], "D": []})
        bucket[op].append(pk)

    db = get_mongo_database(require_configured=True)
    from pymongo import ReplaceOne

    total_applied = 0
    try:
        for tbl, actions in by_table.items():
            coll = db[tbl]
            pk_col = SYNC_TABLE_PK_MAP[tbl]
            pk_cols = [c.strip() for c in pk_col.split(",") if c.strip()]

            upserts = actions["U"]
            if upserts:
                ops = []
                for pk_val in upserts:
                    if len(pk_cols) == 1:
                        row = conn.execute(
                            f"SELECT * FROM {tbl} WHERE {pk_cols[0]} = ?",
                            (pk_val,),
                        ).fetchone()
                    else:
                        parts = pk_val.split(":", len(pk_cols) - 1)
                        where_sql = " AND ".join(f"{c} = ?" for c in pk_cols)
                        row = conn.execute(
                            f"SELECT * FROM {tbl} WHERE {where_sql}",
                            tuple(parts),
                        ).fetchone()
                    if row:
                        doc = dict(row)
                        doc["_id"] = pk_val
                        ops.append(ReplaceOne({"_id": pk_val}, doc, upsert=True))
                if ops:
                    coll.bulk_write(ops, ordered=False)
                    total_applied += len(ops)

            deletes = actions["D"]
            if deletes:
                res = coll.delete_many({"_id": {"$in": deletes}})
                total_applied += int(res.deleted_count or len(deletes))

        new_seq = bump_mongo_global_seq(db)
        _CONTAINER_SYNC_SEQ[db_path] = new_seq
        return total_applied
    except Exception as exc:
        # Invalidate local cache seq so the next request re-hydrates from MongoDB
        _CONTAINER_SYNC_SEQ.pop(db_path, None)
        raise DatabaseUnavailableError(
            f"Authoritative cloud write failed ({type(exc).__name__})."
        ) from exc


def restore_user_by_email_from_mongo(conn: sqlite3.Connection, email: str) -> Optional[Dict[str, Any]]:
    """Non-destructive single-user lookup from MongoDB Atlas."""
    db = get_mongo_database()
    if db is None:
        return None
    try:
        email_clean = (email or "").strip().lower()
        user_doc = db["users"].find_one({"email": email_clean})
        if not user_doc:
            return None
        conn.execute("PRAGMA foreign_keys = OFF;")
        try:
            _insert_mongo_docs_into_sqlite(conn, "users", [user_doc])
            pref_doc = db["user_preferences"].find_one({"user_id": user_doc.get("id")})
            if pref_doc:
                _insert_mongo_docs_into_sqlite(conn, "user_preferences", [pref_doc])
            conn.commit()
        finally:
            conn.execute("PRAGMA foreign_keys = ON;")
        return conn.execute("SELECT * FROM users WHERE email = ?", (email_clean,)).fetchone()
    except Exception as exc:
        _logger.warning("Single-user restore warning: %s", type(exc).__name__)
        return None


def restore_user_by_id_from_mongo(conn: sqlite3.Connection, user_id: str) -> Optional[Dict[str, Any]]:
    """Non-destructive single-user lookup by ID from MongoDB Atlas."""
    db = get_mongo_database()
    if db is None:
        return None
    try:
        uid = (user_id or "").strip()
        if not uid:
            return None
        user_doc = db["users"].find_one({"id": uid})
        if not user_doc:
            return None
        conn.execute("PRAGMA foreign_keys = OFF;")
        try:
            _insert_mongo_docs_into_sqlite(conn, "users", [user_doc])
            pref_doc = db["user_preferences"].find_one({"user_id": uid})
            if pref_doc:
                _insert_mongo_docs_into_sqlite(conn, "user_preferences", [pref_doc])
            conn.commit()
        finally:
            conn.execute("PRAGMA foreign_keys = ON;")
        return conn.execute(
            "SELECT id, email, name, role, target_role, bio, avatar_color, avatar_url, created_at, updated_at FROM users WHERE id = ?",
            (uid,),
        ).fetchone()
    except Exception as exc:
        _logger.warning("Single-user ID restore warning: %s", type(exc).__name__)
        return None


def sync_sqlite_to_mongo(conn: sqlite3.Connection) -> Dict[str, int]:
    """
    Non-destructive manual export/sync from SQLite into MongoDB Atlas collections.
    Strictly performs upserts only — NEVER deletes any MongoDB documents.
    """
    db = get_mongo_database()
    if db is None:
        return {}

    counts: Dict[str, int] = {}
    from pymongo import ReplaceOne

    for table_name, pk_col in SYNC_TABLES:
        try:
            rows = conn.execute(f"SELECT * FROM {table_name}").fetchall()
        except sqlite3.Error:
            continue

        coll = db[table_name]
        ops = []
        pk_cols = [c.strip() for c in pk_col.split(",") if c.strip()]
        for r in rows:
            doc = dict(r)
            doc_id = ":".join(str(doc.get(c, "")) for c in pk_cols)
            if not doc_id or doc_id == ":":
                continue
            doc["_id"] = doc_id
            ops.append(ReplaceOne({"_id": doc_id}, doc, upsert=True))

        if ops:
            coll.bulk_write(ops, ordered=False)
        counts[table_name] = len(ops)

    bump_mongo_global_seq(db)
    return counts


def restore_sqlite_from_mongo(conn: sqlite3.Connection) -> Dict[str, int]:
    """Non-destructive full import of rows from MongoDB Atlas into SQLite."""
    db = get_mongo_database()
    if db is None:
        return {}

    restored: Dict[str, int] = {}

    def _fetch_table(item: tuple[str, str]) -> tuple[str, List[Dict[str, Any]]]:
        t_name, _ = item
        try:
            return t_name, list(db[t_name].find({}))
        except Exception:
            return t_name, []

    with ThreadPoolExecutor(max_workers=8) as pool:
        fetched = list(pool.map(_fetch_table, SYNC_TABLES))

    conn.execute("PRAGMA foreign_keys = OFF;")
    try:
        for table_name, docs in fetched:
            if not docs:
                continue
            count = _insert_mongo_docs_into_sqlite(conn, table_name, docs)
            if count:
                restored[table_name] = count
        conn.commit()
    finally:
        conn.execute("PRAGMA foreign_keys = ON;")
    return restored
