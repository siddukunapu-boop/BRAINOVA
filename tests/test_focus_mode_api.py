"""Comprehensive backend unit & persistence tests for BRAINOVA Strict Focus Mode API."""

import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from starlette.requests import Request

from backend import database as db_mod
from backend.main import (
    FocusEventCreateRequest,
    FocusSessionStartRequest,
    abort_focus_session,
    clear_focus_session_history,
    complete_focus_session,
    delete_focus_session,
    get_active_focus_session,
    get_current_user,
    get_focus_session_detail,
    list_focus_sessions,
    record_focus_event,
    start_focus_session,
)


class FocusModeBackendTests(unittest.TestCase):
    def setUp(self):
        self.orig_db = os.environ.get("AETHER_DB_PATH")
        fd, self.tmp_db = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        os.environ["AETHER_DB_PATH"] = self.tmp_db
        db_mod.init_db()

        now = db_mod.utc_now()
        with db_mod.get_db(commit=True) as conn:
            for uid, email in [("fm_u1", "fm1@example.com"), ("fm_u2", "fm2@example.com")]:
                conn.execute(
                    "INSERT INTO users (id, name, email, password_hash, target_role, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (uid, uid, email, "hash", "Full Stack Developer", now, now),
                )
        self.u1 = {"id": "fm_u1", "email": "fm1@example.com"}
        self.u2 = {"id": "fm_u2", "email": "fm2@example.com"}

    def tearDown(self):
        if self.orig_db is None:
            os.environ.pop("AETHER_DB_PATH", None)
        else:
            os.environ["AETHER_DB_PATH"] = self.orig_db
        if os.path.exists(self.tmp_db):
            os.remove(self.tmp_db)

    def test_authentication_required(self):
        scope = {"type": "http", "headers": [], "query_string": b""}
        req = Request(scope)
        with self.assertRaises(HTTPException) as ctx:
            get_current_user(req, authorization=None)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_create_retrieve_and_complete_session(self):
        started = start_focus_session(
            FocusSessionStartRequest(
                duration_seconds=1500,
                session_title="Distributed Systems",
                short_break_minutes=5,
                sound_enabled=True,
                animations_enabled=True,
                client_request_id="req_abc_1",
            ),
            current_user=self.u1,
        )
        session = started["session"]
        self.assertEqual(session["status"], "active")
        self.assertEqual(session["duration_seconds"], 1500)
        self.assertEqual(session["session_title"], "Distributed Systems")
        self.assertEqual(session["short_break_minutes"], 5)
        self.assertEqual(session["distraction_event_count"], 0)

        active = get_active_focus_session(current_user=self.u1)
        self.assertIsNotNone(active["session"])
        self.assertEqual(active["session"]["id"], session["id"])

        completed = complete_focus_session(session["id"], current_user=self.u1)["session"]
        self.assertEqual(completed["status"], "completed")
        self.assertTrue(bool(completed["completed_at"]))

        # Duplicate completion is idempotent
        completed_again = complete_focus_session(session["id"], current_user=self.u1)["session"]
        self.assertEqual(completed_again["status"], "completed")
        self.assertEqual(completed_again["completed_at"], completed["completed_at"])

        # Active is now None, history contains 1 session
        self.assertIsNone(get_active_focus_session(current_user=self.u1)["session"])
        history = list_focus_sessions(limit=20, current_user=self.u1)["sessions"]
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["id"], session["id"])

    def test_duplicate_start_and_idempotency(self):
        first = start_focus_session(
            FocusSessionStartRequest(duration_seconds=900, client_request_id="idem_1"),
            current_user=self.u1,
        )["session"]

        # Same client_request_id returns same session idempotently
        idem = start_focus_session(
            FocusSessionStartRequest(duration_seconds=900, client_request_id="idem_1"),
            current_user=self.u1,
        )["session"]
        self.assertEqual(idem["id"], first["id"])

        # Different request while active returns 409 Conflict
        with self.assertRaises(HTTPException) as ctx:
            start_focus_session(
                FocusSessionStartRequest(duration_seconds=900, client_request_id="idem_2"),
                current_user=self.u1,
            )
        self.assertEqual(ctx.exception.status_code, 409)

    def test_invalid_durations_rejected(self):
        for bad_dur in [0, 30, -60, 14401]:
            with self.assertRaises(HTTPException) as ctx:
                start_focus_session(
                    FocusSessionStartRequest(duration_seconds=bad_dur),
                    current_user=self.u1,
                )
            self.assertEqual(ctx.exception.status_code, 400)

        with self.assertRaises(HTTPException) as ctx:
            start_focus_session(
                FocusSessionStartRequest(duration_seconds=1500, short_break_minutes=45),
                current_user=self.u1,
            )
        self.assertEqual(ctx.exception.status_code, 400)

    def test_event_recording_and_invalid_event_types(self):
        session = start_focus_session(
            FocusSessionStartRequest(duration_seconds=1500, session_title="Algorithms"),
            current_user=self.u1,
        )["session"]

        # Invalid event type rejected
        with self.assertRaises(HTTPException) as ctx:
            record_focus_event(
                session["id"],
                FocusEventCreateRequest(event_type="keystroke_capture"),
                current_user=self.u1,
            )
        self.assertEqual(ctx.exception.status_code, 400)

        # Distraction events increment distraction_event_count
        r1 = record_focus_event(
            session["id"],
            FocusEventCreateRequest(event_type="visibility_hidden", metadata={"route": "/dashboard"}),
            current_user=self.u1,
        )
        self.assertEqual(r1["session"]["distraction_event_count"], 1)

        r2 = record_focus_event(
            session["id"],
            FocusEventCreateRequest(event_type="external_navigation_blocked", metadata={"host": "example.com"}),
            current_user=self.u1,
        )
        self.assertEqual(r2["session"]["distraction_event_count"], 2)

        # Informational events are recorded without incrementing distraction count
        r3 = record_focus_event(
            session["id"],
            FocusEventCreateRequest(event_type="visibility_visible"),
            current_user=self.u1,
        )
        self.assertEqual(r3["session"]["distraction_event_count"], 2)

        detail = get_focus_session_detail(session["id"], current_user=self.u1)
        self.assertEqual(len(detail["events"]), 3)
        self.assertEqual(detail["session"]["distraction_event_count"], 2)

    def test_user_ownership_isolation(self):
        session = start_focus_session(
            FocusSessionStartRequest(duration_seconds=1500, session_title="Private Study"),
            current_user=self.u1,
        )["session"]

        with self.assertRaises(HTTPException) as ctx1:
            get_focus_session_detail(session["id"], current_user=self.u2)
        self.assertEqual(ctx1.exception.status_code, 404)

        with self.assertRaises(HTTPException) as ctx2:
            record_focus_event(
                session["id"],
                FocusEventCreateRequest(event_type="visibility_hidden"),
                current_user=self.u2,
            )
        self.assertEqual(ctx2.exception.status_code, 404)

        with self.assertRaises(HTTPException) as ctx3:
            complete_focus_session(session["id"], current_user=self.u2)
        self.assertEqual(ctx3.exception.status_code, 404)

        with self.assertRaises(HTTPException) as ctx4:
            abort_focus_session(session["id"], current_user=self.u2)
        self.assertEqual(ctx4.exception.status_code, 404)

        # User 2 active and history should be empty
        self.assertIsNone(get_active_focus_session(current_user=self.u2)["session"])
        self.assertEqual(list_focus_sessions(limit=20, current_user=self.u2)["sessions"], [])

    def test_abort_session(self):
        session = start_focus_session(
            FocusSessionStartRequest(duration_seconds=1500),
            current_user=self.u1,
        )["session"]

        aborted = abort_focus_session(session["id"], current_user=self.u1)["session"]
        self.assertEqual(aborted["status"], "aborted")

        # Cannot complete an aborted session
        with self.assertRaises(HTTPException) as ctx:
            complete_focus_session(session["id"], current_user=self.u1)
        self.assertEqual(ctx.exception.status_code, 409)

    def test_expired_session_auto_completes_on_recovery(self):
        session = start_focus_session(
            FocusSessionStartRequest(duration_seconds=1500, session_title="Recovery Test"),
            current_user=self.u1,
        )["session"]

        # Simulate time passing beyond ends_at while browser was closed
        past_start = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
        past_end = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        with db_mod.get_db(commit=True) as conn:
            conn.execute(
                "UPDATE focus_sessions SET started_at = ?, ends_at = ? WHERE id = ?",
                (past_start, past_end, session["id"]),
            )

        recovered = get_active_focus_session(current_user=self.u1)
        self.assertIsNone(recovered["session"])
        self.assertIsNotNone(recovered["recently_completed"])
        self.assertEqual(recovered["recently_completed"]["id"], session["id"])
        self.assertEqual(recovered["recently_completed"]["status"], "completed")
        self.assertEqual(recovered["recently_completed"]["completed_at"], past_end)

    def test_delete_individual_history_session_and_ownership_and_active_guard(self):
        s1 = start_focus_session(
            FocusSessionStartRequest(duration_seconds=900, session_title="To Delete"),
            current_user=self.u1,
        )["session"]
        record_focus_event(
            s1["id"],
            FocusEventCreateRequest(event_type="visibility_hidden"),
            current_user=self.u1,
        )
        # Active session cannot be deleted
        with self.assertRaises(HTTPException) as active_err:
            delete_focus_session(s1["id"], current_user=self.u1)
        self.assertEqual(active_err.exception.status_code, 409)

        complete_focus_session(s1["id"], current_user=self.u1)

        # User 2 cannot delete User 1's session
        with self.assertRaises(HTTPException) as cross_err:
            delete_focus_session(s1["id"], current_user=self.u2)
        self.assertEqual(cross_err.exception.status_code, 404)

        # Unknown ID returns 404
        with self.assertRaises(HTTPException) as missing_err:
            delete_focus_session("focus_nonexistent", current_user=self.u1)
        self.assertEqual(missing_err.exception.status_code, 404)

        # User 1 deletes completed session; session + events are removed
        res = delete_focus_session(s1["id"], current_user=self.u1)
        self.assertTrue(res["deleted"])
        self.assertEqual(list_focus_sessions(limit=20, current_user=self.u1)["sessions"], [])
        with db_mod.get_db() as conn:
            ev_count = conn.execute(
                "SELECT COUNT(*) AS cnt FROM focus_events WHERE session_id = ?",
                (s1["id"],),
            ).fetchone()["cnt"]
        self.assertEqual(ev_count, 0)

    def test_clear_all_history_preserves_active_and_other_users(self):
        # User 1: 1 completed, 1 aborted, 1 active
        c1 = start_focus_session(
            FocusSessionStartRequest(duration_seconds=900, session_title="Completed 1"),
            current_user=self.u1,
        )["session"]
        record_focus_event(c1["id"], FocusEventCreateRequest(event_type="visibility_hidden"), current_user=self.u1)
        complete_focus_session(c1["id"], current_user=self.u1)

        a1 = start_focus_session(
            FocusSessionStartRequest(duration_seconds=900, session_title="Aborted 1"),
            current_user=self.u1,
        )["session"]
        abort_focus_session(a1["id"], current_user=self.u1)

        active1 = start_focus_session(
            FocusSessionStartRequest(duration_seconds=1500, session_title="Active 1"),
            current_user=self.u1,
        )["session"]

        # User 2: 1 completed (must remain untouched)
        u2_s = start_focus_session(
            FocusSessionStartRequest(duration_seconds=900, session_title="User 2 Session"),
            current_user=self.u2,
        )["session"]
        complete_focus_session(u2_s["id"], current_user=self.u2)

        cleared = clear_focus_session_history(current_user=self.u1)
        self.assertEqual(cleared["deleted_count"], 2)
        self.assertTrue(cleared["active_preserved"])

        # User 1 only has the active session remaining
        u1_list = list_focus_sessions(limit=20, current_user=self.u1)["sessions"]
        self.assertEqual(len(u1_list), 1)
        self.assertEqual(u1_list[0]["id"], active1["id"])

        # User 2 history is untouched
        u2_list = list_focus_sessions(limit=20, current_user=self.u2)["sessions"]
        self.assertEqual(len(u2_list), 1)
        self.assertEqual(u2_list[0]["id"], u2_s["id"])

    def test_three_finger_touchpad_interruption_preserves_active_session(self):
        # 1. Start 25-minute session
        started = start_focus_session(
            FocusSessionStartRequest(duration_seconds=1500, session_title="Touchpad Survival"),
            current_user=self.u1,
        )["session"]
        session_id = started["id"]
        original_ends_at = started["ends_at"]

        # 2-4. Simulate window.blur -> visibility_hidden -> fullscreen_exited (Task View / app switch)
        record_focus_event(
            session_id,
            FocusEventCreateRequest(event_type="window_blur", metadata={"visibility": "visible"}),
            current_user=self.u1,
        )
        record_focus_event(
            session_id,
            FocusEventCreateRequest(event_type="visibility_hidden"),
            current_user=self.u1,
        )
        record_focus_event(
            session_id,
            FocusEventCreateRequest(event_type="fullscreen_exited"),
            current_user=self.u1,
        )

        # 5-7. User returns after interruption and restores visibility + fullscreen
        record_focus_event(
            session_id,
            FocusEventCreateRequest(event_type="window_focus", metadata={"visibility": "visible"}),
            current_user=self.u1,
        )
        record_focus_event(
            session_id,
            FocusEventCreateRequest(event_type="visibility_visible"),
            current_user=self.u1,
        )
        record_focus_event(
            session_id,
            FocusEventCreateRequest(event_type="fullscreen_restored"),
            current_user=self.u1,
        )

        # 8. Fetch active session again: must still be the exact same active session
        active = get_active_focus_session(current_user=self.u1)["session"]
        self.assertIsNotNone(active)
        self.assertEqual(active["id"], session_id)
        self.assertEqual(active["status"], "active")
        self.assertEqual(active["ends_at"], original_ends_at)
        self.assertEqual(active["distraction_event_count"], 3)

        # No duplicate session created
        all_sessions = list_focus_sessions(limit=20, current_user=self.u1)["sessions"]
        self.assertEqual(len(all_sessions), 1)


if __name__ == "__main__":
    unittest.main()
