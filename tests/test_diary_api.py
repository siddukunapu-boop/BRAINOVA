"""Backend unit & persistence tests for the BRAINOVA Personal Diary API."""

import os
import tempfile
import unittest
from fastapi import HTTPException
from starlette.requests import Request

from backend import database as db_mod
from backend import main as main_mod
from backend.main import (
    DiaryEntryCreateRequest,
    DiaryEntryUpdateRequest,
    create_diary_entry,
    delete_diary_entry,
    get_current_user,
    get_diary_entry,
    get_latest_diary_draft,
    list_diary_entries,
    update_diary_entry,
)


class DiaryBackendTests(unittest.TestCase):
    def setUp(self):
        self.orig_db = os.environ.get("AETHER_DB_PATH")
        fd, self.tmp_db = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        os.environ["AETHER_DB_PATH"] = self.tmp_db
        db_mod.init_db()

        now = db_mod.utc_now()
        with db_mod.get_db(commit=True) as conn:
            for uid, email in [("diary_u1", "d1@example.com"), ("diary_u2", "d2@example.com")]:
                conn.execute(
                    "INSERT INTO users (id, name, email, password_hash, target_role, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (uid, uid, email, "hash", "Student", now, now),
                )
        self.u1 = {"id": "diary_u1", "email": "d1@example.com"}
        self.u2 = {"id": "diary_u2", "email": "d2@example.com"}

    def tearDown(self):
        if self.orig_db is None:
            os.environ.pop("AETHER_DB_PATH", None)
        else:
            os.environ["AETHER_DB_PATH"] = self.orig_db
        if os.path.exists(self.tmp_db):
            os.remove(self.tmp_db)

    def test_1_create_and_3_retrieve_multipage_entry(self):
        res = create_diary_entry(
            DiaryEntryCreateRequest(
                title="Evening Reflections",
                entry_date="2026-11-10",
                pages=["Page one thoughts.", "Page two continues."],
                is_draft=False,
            ),
            current_user=self.u1,
        )
        entry = res["entry"]
        self.assertEqual(entry["title"], "Evening Reflections")
        self.assertEqual(entry["entry_date"], "2026-11-10")
        self.assertEqual(entry["pages"], ["Page one thoughts.", "Page two continues."])
        self.assertEqual(entry["page_count"], 2)
        self.assertFalse(entry["is_draft"])

        fetched = get_diary_entry(entry["id"], current_user=self.u1)["entry"]
        self.assertEqual(fetched["pages"], ["Page one thoughts.", "Page two continues."])

    def test_2_list_only_authenticated_users_entries_newest_first(self):
        create_diary_entry(
            DiaryEntryCreateRequest(title="Older", entry_date="2026-11-01", pages=["Old"]),
            current_user=self.u1,
        )
        create_diary_entry(
            DiaryEntryCreateRequest(title="Newer", entry_date="2026-11-12", pages=["New"]),
            current_user=self.u1,
        )
        create_diary_entry(
            DiaryEntryCreateRequest(title="Other User", entry_date="2026-11-13", pages=["Secret"]),
            current_user=self.u2,
        )
        entries = list_diary_entries(include_drafts=True, current_user=self.u1)["entries"]
        self.assertEqual([e["title"] for e in entries], ["Newer", "Older"])

    def test_4_5_10_12_update_add_page_preserve_date_and_no_duplicates(self):
        created = create_diary_entry(
            DiaryEntryCreateRequest(
                title="Draft Title",
                entry_date="2026-11-05",
                pages=["First page"],
                is_draft=True,
                client_draft_key="draft_abc",
            ),
            current_user=self.u1,
        )["entry"]

        # Retry create with same client_draft_key must not duplicate
        retried = create_diary_entry(
            DiaryEntryCreateRequest(
                title="Draft Title v2",
                entry_date="2026-11-13",
                pages=["First page updated"],
                is_draft=True,
                client_draft_key="draft_abc",
            ),
            current_user=self.u1,
        )["entry"]
        self.assertEqual(retried["id"], created["id"])

        # Promote and add a second page; original entry_date must be preserved
        updated = update_diary_entry(
            created["id"],
            DiaryEntryUpdateRequest(
                title="Final Entry",
                pages=["First page updated", "Second page added"],
                is_draft=False,
            ),
            current_user=self.u1,
        )["entry"]
        self.assertEqual(updated["id"], created["id"])
        self.assertEqual(updated["entry_date"], "2026-11-05")
        self.assertEqual(updated["pages"], ["First page updated", "Second page added"])
        self.assertFalse(updated["is_draft"])
        self.assertEqual(len(list_diary_entries(current_user=self.u1)["entries"]), 1)

    def test_6_11_delete_removes_entry_permanently(self):
        created = create_diary_entry(
            DiaryEntryCreateRequest(title="To Delete", entry_date="2026-11-11", pages=["Bye"]),
            current_user=self.u1,
        )["entry"]
        del_res = delete_diary_entry(created["id"], current_user=self.u1)
        self.assertTrue(del_res["ok"])
        self.assertEqual(len(list_diary_entries(current_user=self.u1)["entries"]), 0)
        with self.assertRaises(HTTPException) as ctx:
            get_diary_entry(created["id"], current_user=self.u1)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_7_reject_cross_user_access(self):
        created = create_diary_entry(
            DiaryEntryCreateRequest(title="Private", entry_date="2026-11-11", pages=["Mine"]),
            current_user=self.u1,
        )["entry"]
        for fn in (
            lambda: get_diary_entry(created["id"], current_user=self.u2),
            lambda: update_diary_entry(created["id"], DiaryEntryUpdateRequest(title="Hacked"), current_user=self.u2),
            lambda: delete_diary_entry(created["id"], current_user=self.u2),
        ):
            with self.assertRaises(HTTPException) as ctx:
                fn()
            self.assertEqual(ctx.exception.status_code, 404)

    def test_8_reject_unauthenticated_access(self):
        fake_req = Request({"type": "http", "headers": [], "query_string": b""})
        with self.assertRaises(HTTPException) as ctx:
            get_current_user(request=fake_req, authorization=None)
        self.assertEqual(ctx.exception.status_code, 401)
        with self.assertRaises(HTTPException) as ctx2:
            get_current_user(request=fake_req, authorization="Bearer bad.token.here")
        self.assertEqual(ctx2.exception.status_code, 401)

    def test_9_invalid_or_malformed_payloads(self):
        with self.assertRaises(HTTPException) as ctx_empty:
            create_diary_entry(
                DiaryEntryCreateRequest(title="   ", pages=["   ", ""], is_draft=False),
                current_user=self.u1,
            )
        self.assertEqual(ctx_empty.exception.status_code, 400)

        with self.assertRaises(HTTPException) as ctx_date:
            create_diary_entry(
                DiaryEntryCreateRequest(title="Test", entry_date="not-a-date", pages=["Hello"], is_draft=False),
                current_user=self.u1,
            )
        self.assertEqual(ctx_date.exception.status_code, 400)

        with self.assertRaises(HTTPException) as ctx_pages:
            main_mod._normalize_diary_pages(["ok", 123])
        self.assertEqual(ctx_pages.exception.status_code, 400)

    def test_draft_recovery_endpoint(self):
        self.assertIsNone(get_latest_diary_draft(current_user=self.u1)["draft"])
        create_diary_entry(
            DiaryEntryCreateRequest(title="Autosaved", pages=["Page 1 draft"], is_draft=True, client_draft_key="k1"),
            current_user=self.u1,
        )
        draft = get_latest_diary_draft(current_user=self.u1)["draft"]
        self.assertIsNotNone(draft)
        self.assertTrue(draft["is_draft"])
        self.assertEqual(draft["pages"], ["Page 1 draft"])


if __name__ == "__main__":
    unittest.main()
