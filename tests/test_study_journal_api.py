"""Comprehensive backend unit & persistence tests for BRAINOVA Study Journal API."""

import os
import tempfile
import unittest
from fastapi import HTTPException
from starlette.requests import Request

from backend import database as db_mod
from backend.main import (
    StudyJournalCreateRequest,
    StudyJournalUpdateRequest,
    create_study_journal_entry,
    delete_study_journal_entry,
    get_current_user,
    get_latest_study_journal_draft,
    get_study_journal_entry,
    list_study_journal_entries,
    update_study_journal_entry,
)


def make_rich_page_1():
    return {
        "type": "doc",
        "blocks": [
            {
                "type": "heading",
                "level": 1,
                "runs": [{"text": "Asynchronous JavaScript", "bold": True, "font": "serif", "glitter": "royal-violet"}],
            },
            {
                "type": "paragraph",
                "runs": [
                    {"text": "JavaScript is single-threaded. ", "font": "handwriting", "glitter": "default"},
                    {"text": "Promises run in the Microtask Queue.", "bold": True, "italic": True, "underline": True, "font": "handwriting", "glitter": "glitter-blue"},
                    {"text": " Important definition here.", "font": "soft", "glitter": "golden-sparkle"},
                ],
            },
            {
                "type": "bulletList",
                "items": [
                    [{"text": "Call Stack", "bold": True, "font": "sans", "glitter": "emerald-glow"}],
                    [{"text": "Web APIs", "font": "sans", "glitter": "aqua-crystal"}],
                ],
            },
            {
                "type": "orderedList",
                "items": [
                    [{"text": "Step 1", "font": "typewriter", "glitter": "default"}],
                ],
            },
            {
                "type": "romanList",
                "items": [
                    [{"text": "Phase I", "font": "serif", "glitter": "champagne-gold"}],
                    [{"text": "Phase II", "font": "serif", "glitter": "amethyst"}],
                ],
            },
        ],
    }


def make_rich_page_2():
    return {
        "type": "doc",
        "blocks": [
            {
                "type": "heading",
                "level": 2,
                "runs": [{"text": "Async/Await", "font": "typewriter", "glitter": "sunset-copper"}],
            },
            {
                "type": "paragraph",
                "runs": [{"text": "Syntactic sugar over Promises.", "italic": True, "font": "soft", "glitter": "mint-crystal"}],
            },
        ],
    }


class StudyJournalBackendTests(unittest.TestCase):
    def setUp(self):
        self.orig_db = os.environ.get("AETHER_DB_PATH")
        fd, self.tmp_db = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        os.environ["AETHER_DB_PATH"] = self.tmp_db
        db_mod.init_db()

        now = db_mod.utc_now()
        with db_mod.get_db(commit=True) as conn:
            for uid, email in [("sj_u1", "sj1@example.com"), ("sj_u2", "sj2@example.com")]:
                conn.execute(
                    "INSERT INTO users (id, name, email, password_hash, target_role, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (uid, uid, email, "hash", "Full Stack Developer", now, now),
                )
        self.u1 = {"id": "sj_u1", "email": "sj1@example.com"}
        self.u2 = {"id": "sj_u2", "email": "sj2@example.com"}

    def tearDown(self):
        if self.orig_db is None:
            os.environ.pop("AETHER_DB_PATH", None)
        else:
            os.environ["AETHER_DB_PATH"] = self.orig_db
        if os.path.exists(self.tmp_db):
            os.remove(self.tmp_db)

    def test_create_retrieve_and_preserve_all_rich_formatting(self):
        p1 = make_rich_page_1()
        p2 = make_rich_page_2()
        res = create_study_journal_entry(
            StudyJournalCreateRequest(
                title="Async JS Deep Dive",
                subject="Programming",
                topic="Asynchronous JavaScript",
                chapter_or_module="Module 4",
                study_date="2026-11-12",
                duration_minutes=45,
                learning_status="understood",
                key_concepts="Event Loop, Microtasks",
                learning_outcomes="Trace async execution",
                revision_notes="Review starvation edge case",
                pages=[p1, p2],
                is_draft=False,
            ),
            current_user=self.u1,
        )
        entry = res["entry"]
        self.assertEqual(entry["title"], "Async JS Deep Dive")
        self.assertEqual(entry["subject"], "Programming")
        self.assertEqual(entry["topic"], "Asynchronous JavaScript")
        self.assertEqual(entry["duration_minutes"], 45)
        self.assertEqual(entry["learning_status"], "understood")
        self.assertEqual(entry["page_count"], 2)

        fetched = get_study_journal_entry(entry["id"], current_user=self.u1)["entry"]
        self.assertEqual(fetched["title"], "Async JS Deep Dive")
        blocks1 = fetched["pages"][0]["blocks"]
        self.assertEqual(blocks1[0]["type"], "heading")
        self.assertEqual(blocks1[0]["level"], 1)
        self.assertEqual(blocks1[0]["runs"][0]["glitter"], "royal-violet")
        self.assertEqual(blocks1[0]["runs"][0]["font"], "serif")
        # Independent text runs on same paragraph
        p_runs = blocks1[1]["runs"]
        self.assertEqual(p_runs[0]["glitter"], "default")
        self.assertEqual(p_runs[1]["glitter"], "glitter-blue")
        self.assertTrue(p_runs[1]["bold"] and p_runs[1]["italic"] and p_runs[1]["underline"])
        self.assertEqual(p_runs[2]["glitter"], "golden-sparkle")
        self.assertEqual(p_runs[2]["font"], "soft")
        # Lists: bullet, ordered, roman
        self.assertEqual(blocks1[2]["type"], "bulletList")
        self.assertEqual(blocks1[3]["type"], "orderedList")
        self.assertEqual(blocks1[4]["type"], "romanList")
        self.assertEqual(blocks1[4]["items"][0][0]["glitter"], "champagne-gold")
        # Update title & verify search finds by title
        updated = update_study_journal_entry(
            entry["id"],
            StudyJournalUpdateRequest(title="Async Runtime Mastery"),
            current_user=self.u1,
        )["entry"]
        self.assertEqual(updated["title"], "Async Runtime Mastery")
        by_title = list_study_journal_entries(
            search="runtime mastery",
            subject=None,
            study_date=None,
            learning_status=None,
            sort="newest",
            include_drafts=True,
            current_user=self.u1,
        )["entries"]
        self.assertEqual(len(by_title), 1)
        self.assertEqual(by_title[0]["id"], entry["id"])

        # Page 2 preserved
        self.assertEqual(fetched["pages"][1]["blocks"][0]["runs"][0]["font"], "typewriter")

    def test_list_filter_sort_and_user_isolation(self):
        create_study_journal_entry(
            StudyJournalCreateRequest(
                subject="Databases",
                topic="Normalization",
                study_date="2026-11-01",
                duration_minutes=30,
                learning_status="needs_revision",
                pages=[make_rich_page_1()],
            ),
            current_user=self.u1,
        )
        create_study_journal_entry(
            StudyJournalCreateRequest(
                subject="Programming",
                topic="Event Loop",
                study_date="2026-11-12",
                duration_minutes=60,
                learning_status="understood",
                pages=[make_rich_page_2()],
            ),
            current_user=self.u1,
        )
        create_study_journal_entry(
            StudyJournalCreateRequest(
                subject="Programming",
                topic="Other User Secret",
                study_date="2026-11-13",
                duration_minutes=20,
                pages=[make_rich_page_1()],
            ),
            current_user=self.u2,
        )

        all_u1 = list_study_journal_entries(search=None, subject=None, study_date=None, learning_status=None, sort="newest", include_drafts=True, current_user=self.u1)["entries"]
        self.assertEqual([e["topic"] for e in all_u1], ["Event Loop", "Normalization"])

        oldest_u1 = list_study_journal_entries(search=None, subject=None, study_date=None, learning_status=None, sort="oldest", include_drafts=True, current_user=self.u1)["entries"]
        self.assertEqual([e["topic"] for e in oldest_u1], ["Normalization", "Event Loop"])

        rev_only = list_study_journal_entries(search=None, subject=None, study_date=None, learning_status="needs_revision", sort="newest", include_drafts=True, current_user=self.u1)["entries"]
        self.assertEqual([e["topic"] for e in rev_only], ["Normalization"])

        subj_only = list_study_journal_entries(search=None, subject="Programming", study_date=None, learning_status=None, sort="newest", include_drafts=True, current_user=self.u1)["entries"]
        self.assertEqual([e["topic"] for e in subj_only], ["Event Loop"])

        search_res = list_study_journal_entries(search="normal", subject=None, study_date=None, learning_status=None, sort="newest", include_drafts=True, current_user=self.u1)["entries"]
        self.assertEqual([e["topic"] for e in search_res], ["Normalization"])

    def test_update_metadata_add_page_draft_recovery_and_no_duplicates(self):
        draft = create_study_journal_entry(
            StudyJournalCreateRequest(
                subject="CS",
                topic="Draft Topic",
                study_date="2026-11-10",
                duration_minutes=25,
                learning_status="needs_revision",
                pages=[make_rich_page_1()],
                is_draft=True,
                client_draft_key="sj_key_1",
            ),
            current_user=self.u1,
        )["entry"]

        recovered = get_latest_study_journal_draft(current_user=self.u1)["draft"]
        self.assertIsNotNone(recovered)
        self.assertEqual(recovered["id"], draft["id"])

        # Retry with same client_draft_key must not duplicate
        retry = create_study_journal_entry(
            StudyJournalCreateRequest(
                subject="CS",
                topic="Draft Topic Updated",
                study_date="2026-11-10",
                duration_minutes=30,
                pages=[make_rich_page_1()],
                is_draft=True,
                client_draft_key="sj_key_1",
            ),
            current_user=self.u1,
        )["entry"]
        self.assertEqual(retry["id"], draft["id"])

        # Update metadata, add page 2, promote to saved
        updated = update_study_journal_entry(
            draft["id"],
            StudyJournalUpdateRequest(
                duration_minutes=55,
                learning_status="understood",
                pages=[make_rich_page_1(), make_rich_page_2()],
                is_draft=False,
            ),
            current_user=self.u1,
        )["entry"]
        self.assertEqual(updated["duration_minutes"], 55)
        self.assertEqual(updated["learning_status"], "understood")
        self.assertEqual(updated["topic"], "Draft Topic Updated")
        self.assertEqual(updated["page_count"], 2)
        self.assertFalse(updated["is_draft"])
        self.assertEqual(len(list_study_journal_entries(search=None, subject=None, study_date=None, learning_status=None, sort="newest", include_drafts=True, current_user=self.u1)["entries"]), 1)

    def test_delete_cross_user_and_validation_guards(self):
        created = create_study_journal_entry(
            StudyJournalCreateRequest(
                subject="Math",
                topic="Linear Algebra",
                study_date="2026-11-08",
                duration_minutes=40,
                pages=[make_rich_page_1()],
            ),
            current_user=self.u1,
        )["entry"]

        # Cross-user rejected
        for fn in (
            lambda: get_study_journal_entry(created["id"], current_user=self.u2),
            lambda: update_study_journal_entry(created["id"], StudyJournalUpdateRequest(topic="Steal"), current_user=self.u2),
            lambda: delete_study_journal_entry(created["id"], current_user=self.u2),
        ):
            with self.assertRaises(HTTPException) as ctx:
                fn()
            self.assertEqual(ctx.exception.status_code, 404)

        # Unauthenticated rejected
        fake_req = Request({"type": "http", "headers": [], "query_string": b""})
        with self.assertRaises(HTTPException) as ctx_auth:
            get_current_user(request=fake_req, authorization=None)
        self.assertEqual(ctx_auth.exception.status_code, 401)

        # Invalid duration rejected
        with self.assertRaises(HTTPException) as ctx_dur:
            create_study_journal_entry(
                StudyJournalCreateRequest(subject="Math", topic="Test", duration_minutes=-5, pages=[make_rich_page_1()]),
                current_user=self.u1,
            )
        self.assertEqual(ctx_dur.exception.status_code, 400)

        # Malformed editor document rejected
        with self.assertRaises(HTTPException) as ctx_doc:
            create_study_journal_entry(
                StudyJournalCreateRequest(subject="Math", topic="Test", duration_minutes=10, pages=[{"type": "bad", "blocks": []}]),
                current_user=self.u1,
            )
        self.assertEqual(ctx_doc.exception.status_code, 400)

        # Delete & verify permanently gone
        del_res = delete_study_journal_entry(created["id"], current_user=self.u1)
        self.assertTrue(del_res["ok"])
        self.assertEqual(len(list_study_journal_entries(search=None, subject=None, study_date=None, learning_status=None, sort="newest", include_drafts=True, current_user=self.u1)["entries"]), 0)
        with self.assertRaises(HTTPException) as ctx_gone:
            get_study_journal_entry(created["id"], current_user=self.u1)
        self.assertEqual(ctx_gone.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
