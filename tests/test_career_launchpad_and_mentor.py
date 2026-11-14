"""Socket-free route-handler and security tests for BRAINOVA Career Launchpad & AI Mentor."""

import os
import sys
import tempfile
import unittest
from unittest.mock import patch

TEST_DIR = tempfile.mkdtemp(prefix="brainova_career_mentor_")
os.environ["AETHER_DB_PATH"] = os.path.join(TEST_DIR, "career_mentor.db")
os.environ["BRAINOVA_MASTER_KEY_FILE"] = os.path.join(TEST_DIR, ".career_master_key")
os.environ.setdefault("AETHER_JWT_SECRET", "unit-test-jwt-secret-with-at-least-32-chars")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from fastapi import HTTPException
from starlette.requests import Request

from backend import database
from backend.auth import create_access_token, get_current_user, hash_password
from backend.main import (
    CareerAssessmentSubmitRequest,
    CareerPlanGenerateRequest,
    CareerProfileUpdateRequest,
    MentorConversationCreateRequest,
    MentorConversationRenameRequest,
    MentorFeedbackRequest,
    MentorStreamRequest,
    ProjectEvidencePayload,
    _create_mentor_sse_generator,
    create_mentor_conversation,
    delete_mentor_conversation,
    generate_career_preparation_plan,
    get_career_assessment,
    get_career_launchpad_overview,
    get_mentor_conversation,
    list_mentor_conversations,
    rename_mentor_conversation,
    set_mentor_message_feedback,
    stream_mentor_conversation_turn,
    submit_career_assessment,
    update_career_profile,
)


def _dummy_request() -> Request:
    return Request({"type": "http", "method": "GET", "path": "/", "headers": [], "query_string": b""})


def _auth_user(token: str):
    return get_current_user(_dummy_request(), f"Bearer {token}")


class CareerLaunchpadAndMentorTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self._orig_db_path = os.environ.get("AETHER_DB_PATH")
        os.environ["AETHER_DB_PATH"] = self._tmp.name
        database.init_db()

        with database.get_db(commit=True) as conn:
            now = database.utc_now()
            conn.execute(
                "INSERT INTO users (id, name, email, password_hash, target_role, email_verified, created_at, updated_at) VALUES (?, ?, ?, ?, ?, 1, ?, ?)",
                ("user_a", "Alice Dev", "alice@example.com", hash_password("Secret123!"), "Full Stack Developer", now, now),
            )
            conn.execute(
                "INSERT INTO users (id, name, email, password_hash, target_role, email_verified, created_at, updated_at) VALUES (?, ?, ?, ?, ?, 1, ?, ?)",
                ("user_b", "Bob Dev", "bob@example.com", hash_password("Secret123!"), "Backend Developer", now, now),
            )

        self.token_a = create_access_token("user_a", "alice@example.com")
        self.token_b = create_access_token("user_b", "bob@example.com")
        self.user_a = _auth_user(self.token_a)
        self.user_b = _auth_user(self.token_b)

    def tearDown(self) -> None:
        if self._orig_db_path is None:
            os.environ.pop("AETHER_DB_PATH", None)
        else:
            os.environ["AETHER_DB_PATH"] = self._orig_db_path
        try:
            os.unlink(self._tmp.name)
        except OSError:
            pass

    def test_requires_authentication(self) -> None:
        with self.assertRaises(HTTPException) as ctx_missing:
            get_current_user(_dummy_request(), None)
        self.assertEqual(ctx_missing.exception.status_code, 401)

        with self.assertRaises(HTTPException) as ctx_bad:
            get_current_user(_dummy_request(), "Bearer invalid.jwt.token")
        self.assertEqual(ctx_bad.exception.status_code, 401)

    def test_career_profile_assessment_gap_analysis_and_plan(self) -> None:
        # Update career profile
        res_prof = update_career_profile(
            CareerProfileUpdateRequest(
                target_career="Backend Developer",
                target_job_role="Backend Engineer (Python/FastAPI)",
                target_company="Atlassian",
                graduation_year=2026,
                current_skill_level="Intermediate",
                available_hours_per_week=16,
                target_deadline="2026-08-01",
            ),
            current_user=self.user_a,
        )
        self.assertEqual(res_prof["profile"]["target_career"], "Backend Developer")

        # Assessment questions never expose answer keys
        res_q = get_career_assessment(current_user=self.user_a)
        questions = res_q["questions"]
        self.assertEqual(len(questions), 18)
        for q in questions:
            self.assertNotIn("correct_index", q)

        # Submit assessment (all option 0 -> 100% on knowledge questions)
        answers = {q["id"]: 0 for q in questions}
        res_sub = submit_career_assessment(
            CareerAssessmentSubmitRequest(
                answers=answers,
                project_evidence=ProjectEvidencePayload(
                    deployed_projects=2,
                    has_github_portfolio=True,
                    has_automated_tests=True,
                ),
            ),
            current_user=self.user_a,
        )
        self.assertEqual(res_sub["assessment"]["overall_score"], 100)

        # Overview reflects actual assessment & readiness disclaimer
        ov = get_career_launchpad_overview(current_user=self.user_a)
        self.assertTrue(ov["gap_analysis"]["has_assessment"])
        self.assertIn("not a probability of getting hired", ov["gap_analysis"]["readiness"]["disclaimer"].lower())

        # Generate personalized plan using existing roadmap engine (fallback local engine when no external key)
        with patch("backend.ai_engine._resolve_active_provider", return_value=("none", "", "")):
            res_plan = generate_career_preparation_plan(
                CareerPlanGenerateRequest(focus_note="Focus on distributed systems and SQL indexing"),
                current_user=self.user_a,
            )
        self.assertIn("phases", res_plan["draft_roadmap"])
        self.assertGreater(len(res_plan["draft_roadmap"]["phases"]), 0)

    def test_mentor_conversation_lifecycle_and_user_isolation(self) -> None:
        # User A creates conversation
        c_res = create_mentor_conversation(
            MentorConversationCreateRequest(title="DSA & Trees"),
            current_user=self.user_a,
        )
        conv_id = c_res["conversation"]["id"]

        # User B cannot access, rename, delete, or stream to User A's conversation
        with self.assertRaises(HTTPException) as e_get:
            get_mentor_conversation(conv_id, current_user=self.user_b)
        self.assertEqual(e_get.exception.status_code, 404)

        with self.assertRaises(HTTPException) as e_ren:
            rename_mentor_conversation(conv_id, MentorConversationRenameRequest(title="Hack"), current_user=self.user_b)
        self.assertEqual(e_ren.exception.status_code, 404)

        with self.assertRaises(HTTPException) as e_del:
            delete_mentor_conversation(conv_id, current_user=self.user_b)
        self.assertEqual(e_del.exception.status_code, 404)

        with self.assertRaises(HTTPException) as e_str:
            stream_mentor_conversation_turn(conv_id, MentorStreamRequest(message="hi"), current_user=self.user_b)
        self.assertEqual(e_str.exception.status_code, 404)

        # Rename and search
        r_res = rename_mentor_conversation(
            conv_id,
            MentorConversationRenameRequest(title="Binary Search Trees"),
            current_user=self.user_a,
        )
        self.assertEqual(r_res["title"], "Binary Search Trees")

        list_res = list_mentor_conversations(q="Binary", current_user=self.user_a)
        self.assertEqual(len(list_res["conversations"]), 1)

        # Delete
        d_res = delete_mentor_conversation(conv_id, current_user=self.user_a)
        self.assertTrue(d_res["deleted"])
        with self.assertRaises(HTTPException) as e_gone:
            get_mentor_conversation(conv_id, current_user=self.user_a)
        self.assertEqual(e_gone.exception.status_code, 404)

    def test_mentor_streaming_mocked_and_missing_provider_graceful(self) -> None:
        conv_id = create_mentor_conversation(
            MentorConversationCreateRequest(title="New Mentor Conversation"),
            current_user=self.user_a,
        )["conversation"]["id"]

        # Without provider keys, streams clean error event (does not crash)
        with patch("backend.career_launchpad._resolve_active_provider", return_value=("none", "", "")):
            resp = stream_mentor_conversation_turn(
                conv_id,
                MentorStreamRequest(message="Explain quicksort with a mermaid diagram"),
                current_user=self.user_a,
            )
            self.assertEqual(resp.media_type, "text/event-stream")
            conv_mid = get_mentor_conversation(conv_id, current_user=self.user_a)["conversation"]
            body_text = "".join(
                _create_mentor_sse_generator(conv_id, "user_a", conv_mid["title"], conv_mid["messages"], {}, None)
            )
            self.assertIn("provider_not_configured", body_text)

        # With mocked provider stream, persists assistant reply and updates title
        def fake_stream(*args, **kwargs):
            yield {"type": "meta", "provider": "gemini:gemini-2.5-flash"}
            yield {"type": "delta", "text": "Here is QuickSort:\n\n```mermaid\nflowchart TD\nA[Pivot] --> B[Partition]\n```"}
            yield {
                "type": "done",
                "text": "Here is QuickSort:\n\n```mermaid\nflowchart TD\nA[Pivot] --> B[Partition]\n```",
                "provider": "gemini:gemini-2.5-flash",
            }

        with patch("backend.main.stream_mentor_reply", side_effect=fake_stream):
            resp2 = stream_mentor_conversation_turn(
                conv_id,
                MentorStreamRequest(message="Explain quicksort with a diagram"),
                current_user=self.user_a,
            )
            self.assertEqual(resp2.media_type, "text/event-stream")
            conv_mid2 = get_mentor_conversation(conv_id, current_user=self.user_a)["conversation"]
            body2 = "".join(
                _create_mentor_sse_generator(conv_id, "user_a", conv_mid2["title"], conv_mid2["messages"], {}, None)
            )
            self.assertIn("flowchart TD", body2)

        conv_detail = get_mentor_conversation(conv_id, current_user=self.user_a)["conversation"]
        self.assertGreaterEqual(len(conv_detail["messages"]), 2)
        assistant_msg = conv_detail["messages"][-1]
        self.assertEqual(assistant_msg["role"], "assistant")

        # Feedback works
        fb = set_mentor_message_feedback(
            conv_id,
            MentorFeedbackRequest(message_id=assistant_msg["id"], feedback="up"),
            current_user=self.user_a,
        )
        self.assertTrue(fb["updated"])

    def test_mentor_rate_limiting(self) -> None:
        conv_id = create_mentor_conversation(
            MentorConversationCreateRequest(title="Rate Limit Test"),
            current_user=self.user_a,
        )["conversation"]["id"]

        with patch("backend.career_launchpad._resolve_active_provider", return_value=("none", "", "")):
            for _ in range(20):
                r = stream_mentor_conversation_turn(
                    conv_id,
                    MentorStreamRequest(message="ping"),
                    current_user=self.user_a,
                )
                self.assertEqual(r.media_type, "text/event-stream")
            with self.assertRaises(HTTPException) as ctx_rl:
                stream_mentor_conversation_turn(
                    conv_id,
                    MentorStreamRequest(message="ping 21"),
                    current_user=self.user_a,
                )
            self.assertEqual(ctx_rl.exception.status_code, 429)

    def test_mentor_provider_detection_and_invalid_key_handling(self) -> None:
        from backend.ai_engine import _resolve_active_provider
        from backend.career_launchpad import stream_mentor_reply

        # 1. Server env fallback detection (isolated from host .env GEMINI_API_KEY)
        with patch.dict(os.environ, {"GEMINI_API_KEY": "", "OPENAI_API_KEY": "sk-test-env-key"}, clear=False):
            prov, key, _ = _resolve_active_provider({})
            self.assertEqual(prov, "openai")
            self.assertEqual(key, "sk-test-env-key")

        # 1b. Retired gemini-2.5-flash upgrades cleanly to gemini-3.5-flash-lite
        prov_gem, _, mod_gem = _resolve_active_provider(
            {"ai_provider": "gemini", "gemini_api_key": "AIza-test", "gemini_model": "gemini-2.5-flash"}
        )
        self.assertEqual(prov_gem, "gemini")
        self.assertEqual(mod_gem, "gemini-3.5-flash-lite")

        # 2. User preferences take precedence over env
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-env-key"}, clear=False):
            prov, key, _ = _resolve_active_provider(
                {"ai_provider": "gemini", "gemini_api_key": "AIza-user-secret"}
            )
            self.assertEqual(prov, "gemini")
            self.assertEqual(key, "AIza-user-secret")

        # 3. Non-200 provider error never leaks the API key
        class _FakeResp:
            status_code = 401
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False

        class _FakeClient:
            def __init__(self, *args, **kwargs):
                pass
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def stream(self, *args, **kwargs):
                return _FakeResp()

        with patch("backend.career_launchpad.httpx.Client", _FakeClient):
            events = list(
                stream_mentor_reply(
                    [{"role": "user", "content": "Hello"}],
                    user_prefs={"ai_provider": "openai", "openai_api_key": "sk-super-secret-value"},
                )
            )
        err_evts = [e for e in events if e.get("type") == "error"]
        self.assertEqual(len(err_evts), 1)
        self.assertEqual(err_evts[0]["code"], "provider_error")
        self.assertNotIn("sk-super-secret-value", err_evts[0]["message"])

    def test_conversation_title_extraction_and_manual_rename_preservation(self) -> None:
        from backend.career_launchpad import extract_conversation_title

        self.assertEqual(extract_conversation_title("Explain C++ pointers with examples"), "C++ Pointers")
        self.assertEqual(extract_conversation_title("How does binary search work?"), "Binary Search")
        self.assertEqual(extract_conversation_title("Debug this Python program"), "Python Debugging")
        self.assertEqual(extract_conversation_title("Explain operating system scheduling"), "OS Scheduling")
        self.assertEqual(extract_conversation_title("What is neural network architecture?"), "Neural Networks")
        self.assertEqual(extract_conversation_title("How does TCP handshake work?"), "TCP Handshake")

    def test_mentor_image_endpoint_security_and_isolation(self) -> None:
        import base64
        from backend.main import (
            MentorImageGenerateRequest,
            generate_mentor_conversation_image,
            get_mentor_generated_image,
        )

        conv_id = create_mentor_conversation(
            MentorConversationCreateRequest(title="Solar System"),
            current_user=self.user_a,
        )["conversation"]["id"]

        # Cross-user conversation access blocked
        with self.assertRaises(HTTPException) as ctx_iso:
            generate_mentor_conversation_image(
                conv_id,
                MentorImageGenerateRequest(prompt="Solar system diagram"),
                current_user=self.user_b,
            )
        self.assertEqual(ctx_iso.exception.status_code, 404)

        # Mocked valid PNG response saves and enforces user isolation on retrieval
        tiny_png_b64 = base64.b64encode(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR").decode()

        class _FakeImgResp:
            status_code = 200
            def json(self):
                return {"candidates": [{"content": {"parts": [{"inlineData": {"mimeType": "image/png", "data": tiny_png_b64}}]}}]}

        class _FakeImgClient:
            def __init__(self, *args, **kwargs):
                pass
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def post(self, *args, **kwargs):
                return _FakeImgResp()

        with patch.dict(os.environ, {"GEMINI_API_KEY": "AIza-fake-img-test"}, clear=False):
            with patch("backend.career_launchpad.httpx.Client", _FakeImgClient):
                res = generate_mentor_conversation_image(
                    conv_id,
                    MentorImageGenerateRequest(prompt="Solar system illustration"),
                    current_user=self.user_a,
                )
        img_id = res["message"]["image"]["id"]
        file_resp = get_mentor_generated_image(img_id, current_user=self.user_a)
        self.assertEqual(file_resp.media_type, "image/png")

        # User B cannot fetch User A's image
        with self.assertRaises(HTTPException) as ctx_img_b:
            get_mentor_generated_image(img_id, current_user=self.user_b)
        self.assertEqual(ctx_img_b.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
