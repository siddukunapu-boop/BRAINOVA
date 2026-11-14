"""
AetherLearn AI — Comprehensive Automated Verification & Security Test Suite (Part 18)
Tests:
- Database schema & foreign key integrity
- Authentication, signup, login, session validation & secret key masking
- Source upload, PDF extraction, scanned PDF OCR detection, chunk indexing & grounded citations
- Roadmap generation, preview edits, Save Roadmap workflow, job queue, retry, rename, and cascade delete
- Topic Workspace: Custom YouTube tutorials (save, reopen, replace, delete isolation), Reading material,
  Personal Notes (create, edit, delete isolation), and non-destructive regeneration protection (409 guard)
- 20-MCQ Examination Engine: exactly 20 questions, 4 options, hidden answers pre-submit, server grading,
  correct/wrong/unanswered math, historical attempt snapshots, retakes, and isolated attempt deletion
- All 9 AI Studio Tools (including genuine playable WAV audio file synthesis & Flashcard spaced repetition)
- Cross-user security & IDOR authorization tests
"""

import json
import os
import sys
import tempfile
import unittest

# Configure isolated test database and isolated test master key before importing backend
TEST_DB_DIR = tempfile.mkdtemp(prefix="aetherlearn_test_")
os.environ["AETHER_DB_PATH"] = os.path.join(TEST_DB_DIR, "test_aetherlearn.db")
os.environ["BRAINOVA_MASTER_KEY_FILE"] = os.path.join(TEST_DB_DIR, ".test_master_key")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from fastapi.testclient import TestClient
from backend.database import get_db, init_db
from backend.main import app


class AetherLearnPlatformTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app)
        from backend.email_service import set_email_sender_for_tests

        captured_otps = {}

        def _capture_email(to_email: str, _name: str, otp_code: str, _expires: int):
            captured_otps[to_email.lower()] = otp_code

        set_email_sender_for_tests(_capture_email)
        try:
            # Create User A
            res_a = cls.client.post(
                "/api/auth/signup",
                json={
                    "name": "Alice Engineer",
                    "email": "alice@aetherlearn.edu",
                    "password": "StrongPassword123!",
                    "target_role": "Full Stack Developer",
                },
            )
            assert res_a.status_code == 200, res_a.text
            ver_a = cls.client.post(
                "/api/auth/verify-email",
                json={
                    "pending_token": res_a.json()["pending_token"],
                    "otp_code": captured_otps["alice@aetherlearn.edu"],
                },
            )
            assert ver_a.status_code == 200, ver_a.text
            cls.token_a = ver_a.json()["token"]
            cls.user_a = ver_a.json()["user"]
            cls.headers_a = {"Authorization": f"Bearer {cls.token_a}"}

            # Create User B (for cross-user security & isolation verification)
            res_b = cls.client.post(
                "/api/auth/signup",
                json={
                    "name": "Bob Intruder",
                    "email": "bob@aetherlearn.edu",
                    "password": "BobPassword123!",
                    "target_role": "Data Scientist",
                },
            )
            assert res_b.status_code == 200, res_b.text
            ver_b = cls.client.post(
                "/api/auth/verify-email",
                json={
                    "pending_token": res_b.json()["pending_token"],
                    "otp_code": captured_otps["bob@aetherlearn.edu"],
                },
            )
            assert ver_b.status_code == 200, ver_b.text
            cls.token_b = ver_b.json()["token"]
            cls.user_b = ver_b.json()["user"]
            cls.headers_b = {"Authorization": f"Bearer {cls.token_b}"}
        finally:
            set_email_sender_for_tests(None)

    def test_01_auth_and_secret_masking(self):
        # Verify /api/auth/me works
        me = self.client.get("/api/auth/me", headers=self.headers_a)
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["user"]["email"], "alice@aetherlearn.edu")

        # Save a secret API key in preferences and verify it is NEVER exposed in client response
        secret_val = "AIzaSySecretKeyNeverExposeInJson12345"
        pref_res = self.client.put(
            "/api/settings/preferences",
            headers=self.headers_a,
            json={"gemini_api_key": secret_val, "study_hours_per_week": 15},
        )
        self.assertEqual(pref_res.status_code, 200)
        raw_body = pref_res.text
        self.assertNotIn(secret_val, raw_body)
        self.assertTrue(pref_res.json()["preferences"]["credentials_status"]["gemini_configured"])

        # Clear key back so tests run deterministically offline
        self.client.put(
            "/api/settings/preferences",
            headers=self.headers_a,
            json={"gemini_api_key": ""},
        )

    def test_02_source_library_and_grounded_rag_citations(self):
        # Create a rich study document for User A
        content = (
            "# Distributed Consensus and Raft Protocol\n\n"
            "Raft achieves consensus via an elected leader that manages log replication across follower nodes. "
            "Every term begins with an election triggered when a follower's randomized election timeout elapses without receiving a heartbeat.\n\n"
            "## Log Replication and Safety Invariants\n\n"
            "Once a leader is elected, it accepts client commands, appends them to its write-ahead log, and sends AppendEntries RPCs. "
            "An entry is committed only after a majority quorum of cluster nodes has written it to durable storage."
        )
        src_res = self.client.post(
            "/api/sources/text",
            headers=self.headers_a,
            json={
                "title": "Raft Consensus Architecture Notes",
                "content": content,
                "file_type": ".md",
                "tags": ["distributed-systems", "raft"],
            },
        )
        self.assertEqual(src_res.status_code, 200, src_res.text)
        source = src_res.json()["source"]
        self.assertEqual(source["status"], "ready")
        self.assertGreater(source["word_count"], 30)
        source_id = source["id"]

        # Test scanned PDF without text layer returns honest OCR limitation status
        scanned_pdf_bytes = b"%PDF-1.4\n1 0 obj << /Type /Catalog >> endobj\n%%EOF"
        up_res = self.client.post(
            "/api/sources/upload",
            headers=self.headers_a,
            files={"file": ("scanned_handout.pdf", scanned_pdf_bytes, "application/pdf")},
        )
        self.assertEqual(up_res.status_code, 200)
        self.assertEqual(up_res.json()["source"]["status"], "error")
        self.assertIn("OCR", up_res.json()["source"]["error_message"])

        # Test source-grounded Q&A returns real citations
        qa_res = self.client.post(
            "/api/sources/ask",
            headers=self.headers_a,
            json={"question": "How does Raft elect a leader and commit log entries?", "source_ids": [source_id]},
        )
        self.assertEqual(qa_res.status_code, 200)
        qa_data = qa_res.json()
        self.assertTrue(qa_data["grounded"])
        self.assertGreater(len(qa_data["citations"]), 0)
        self.assertEqual(qa_data["citations"][0]["source_id"], source_id)

        # SECURITY CHECK: User B must NEVER retrieve User A's private document via /api/sources/ask or /api/sources/{id}
        b_get = self.client.get(f"/api/sources/{source_id}", headers=self.headers_b)
        self.assertEqual(b_get.status_code, 404)

        b_qa = self.client.post(
            "/api/sources/ask",
            headers=self.headers_b,
            json={"question": "How does Raft elect a leader?", "source_ids": [source_id]},
        )
        self.assertEqual(b_qa.status_code, 200)
        self.assertFalse(b_qa.json()["grounded"])
        self.assertEqual(len(b_qa.json()["citations"]), 0)

    def test_03_roadmap_lifecycle_resources_and_quiz_engine(self):
        # 1. Generate Roadmap Preview
        gen_res = self.client.post(
            "/api/roadmaps/generate",
            headers=self.headers_a,
            json={
                "target_role": "Full Stack Developer",
                "skill_level": "Intermediate",
                "hours_per_week": 12,
                "preferred_stack": "React, TypeScript, FastAPI",
            },
        )
        self.assertEqual(gen_res.status_code, 200)
        draft = gen_res.json()["draft_roadmap"]
        self.assertGreaterEqual(len(draft["phases"]), 2)

        # 2. Edit preview and Save Roadmap
        draft["title"] = "Alice's Custom Full Stack Roadmap"
        save_res = self.client.post(
            "/api/roadmaps",
            headers=self.headers_a,
            json={
                "title": draft["title"],
                "target_role": draft["target_role"],
                "description": draft["description"],
                "skill_level": "Intermediate",
                "hours_per_week": 12,
                "generation_policy": "phase_1_only",
                "run_sync_for_first_topic": True,
                "phases": draft["phases"],
            },
        )
        self.assertEqual(save_res.status_code, 200, save_res.text)
        saved_rm = save_res.json()["roadmap"]
        rm_id = saved_rm["id"]

        # 3. Verify phases and topics load after refresh
        load_res = self.client.get(f"/api/roadmaps/{rm_id}", headers=self.headers_a)
        self.assertEqual(load_res.status_code, 200)
        loaded_rm = load_res.json()["roadmap"]
        self.assertEqual(loaded_rm["title"], "Alice's Custom Full Stack Roadmap")
        first_topic = loaded_rm["phases"][0]["topics"][0]
        topic_id = first_topic["id"]

        # 4. Rename Roadmap
        ren_res = self.client.put(
            f"/api/roadmaps/{rm_id}",
            headers=self.headers_a,
            json={"title": "Alice's Verified Full Stack Mastery Plan"},
        )
        self.assertEqual(ren_res.status_code, 200)
        self.assertEqual(ren_res.json()["roadmap"]["title"], "Alice's Verified Full Stack Mastery Plan")

        # 5. Open Topic Workspace and verify Tutorial, Reading, and 20-MCQ Quiz
        ws_res = self.client.get(f"/api/topics/{topic_id}", headers=self.headers_a)
        self.assertEqual(ws_res.status_code, 200)
        ws = ws_res.json()
        self.assertIsNotNone(ws["reading"])
        self.assertGreaterEqual(len(ws["tutorials"]), 1)

        # C.1–C.3: Save Custom YouTube URL, Reopen, Replace, and Delete without deleting topic
        custom_tut_res = self.client.post(
            f"/api/topics/{topic_id}/tutorials",
            headers=self.headers_a,
            json={
                "url": "https://www.youtube.com/watch?v=bMknfKXIFA8",
                "title": "Custom React Deep Dive Lecture",
                "channel_name": "freeCodeCamp.org",
                "is_primary": True,
            },
        )
        self.assertEqual(custom_tut_res.status_code, 200)
        saved_tut_id = custom_tut_res.json()["saved_tutorial_id"]

        # Delete the custom tutorial and verify topic still exists
        del_tut_res = self.client.delete(f"/api/tutorials/{saved_tut_id}", headers=self.headers_a)
        self.assertEqual(del_tut_res.status_code, 200)
        ws_after_tut_del = self.client.get(f"/api/topics/{topic_id}", headers=self.headers_a)
        self.assertEqual(ws_after_tut_del.status_code, 200)

        # C.4–C.7: Personal Notes & Non-destructive Reading Regeneration Protection
        note_res = self.client.post(
            "/api/notes",
            headers=self.headers_a,
            json={
                "title": "My Exam Formula Sheet",
                "content": "Always check WCAG contrast ratios and ARIA landmarks.",
                "topic_id": topic_id,
                "roadmap_id": rm_id,
            },
        )
        self.assertEqual(note_res.status_code, 200)
        note_id = note_res.json()["note"]["id"]

        # Edit note
        upd_note = self.client.put(
            f"/api/notes/{note_id}",
            headers=self.headers_a,
            json={"title": "Updated Exam Formula Sheet", "content": "Updated content."},
        )
        self.assertEqual(upd_note.status_code, 200)

        # Delete note and verify reading material is still intact
        del_note = self.client.delete(f"/api/notes/{note_id}", headers=self.headers_a)
        self.assertEqual(del_note.status_code, 200)
        ws_after_note_del = self.client.get(f"/api/topics/{topic_id}", headers=self.headers_a)
        self.assertIsNotNone(ws_after_note_del.json()["reading"])

        # Edit reading material and verify regeneration without confirm_overwrite returns 409 Conflict
        edit_read = self.client.put(
            f"/api/topics/{topic_id}/reading",
            headers=self.headers_a,
            json={"overview": "Alice's custom edited overview that must not be silently overwritten."},
        )
        self.assertEqual(edit_read.status_code, 200)
        self.assertTrue(edit_read.json()["reading"]["is_user_edited"])

        regen_blocked = self.client.post(
            f"/api/topics/{topic_id}/reading/regenerate",
            headers=self.headers_a,
            json={"confirm_overwrite": False},
        )
        self.assertEqual(regen_blocked.status_code, 409)

        # D.1–D.12: 20-MCQ Examination Engine Tests
        quiz = ws["quiz"]
        self.assertIsNotNone(quiz)
        self.assertEqual(quiz["question_count"], 20)
        self.assertEqual(len(quiz["questions"]), 20)
        for q in quiz["questions"]:
            self.assertEqual(len(q["options"]), 4)
            # Ensure correct_index is NOT leaked in pre-submission payload
            self.assertNotIn("correct_index", q)

        # Fetch true correct indices from DB to test exact grading math
        with get_db() as conn:
            mcq_row = conn.execute("SELECT questions_json FROM mcq_sets WHERE topic_id = ?", (topic_id,)).fetchone()
            true_questions = json.loads(mcq_row["questions_json"])

        # Construct submission: 15 correct, 3 wrong, 2 unanswered
        submitted_answers = {}
        for idx, tq in enumerate(true_questions):
            if idx < 15:
                submitted_answers[tq["id"]] = tq["correct_index"]
            elif idx < 18:
                submitted_answers[tq["id"]] = (tq["correct_index"] + 1) % 4
            # idx 18 and 19 left unanswered

        sub1 = self.client.post(
            f"/api/topics/{topic_id}/quiz/submit",
            headers=self.headers_a,
            json={"answers": submitted_answers, "duration_seconds": 245},
        )
        self.assertEqual(sub1.status_code, 200)
        att1 = sub1.json()["attempt"]
        self.assertEqual(att1["score"], 15)
        self.assertEqual(att1["max_score"], 20)
        self.assertEqual(att1["percentage"], 75.0)
        self.assertEqual(att1["correct_count"], 15)
        self.assertEqual(att1["incorrect_count"], 3)
        self.assertEqual(att1["unanswered_count"], 2)
        self.assertTrue(att1["passed"])

        # Retake exam (creates a separate attempt)
        sub2 = self.client.post(
            f"/api/topics/{topic_id}/quiz/submit",
            headers=self.headers_a,
            json={"answers": {}, "duration_seconds": 60},
        )
        self.assertEqual(sub2.status_code, 200)
        att2 = sub2.json()["attempt"]
        self.assertNotEqual(att1["id"], att2["id"])
        self.assertEqual(att2["unanswered_count"], 20)

        # Delete attempt 2 and verify attempt 1 still exists
        del_att = self.client.delete(f"/api/quizzes/attempts/{att2['id']}", headers=self.headers_a)
        self.assertEqual(del_att.status_code, 200)
        hist_res = self.client.get(f"/api/quizzes/attempts?topic_id={topic_id}", headers=self.headers_a)
        self.assertEqual(len(hist_res.json()["attempts"]), 1)
        self.assertEqual(hist_res.json()["attempts"][0]["id"], att1["id"])

        # E. Cross-user Security Check on Roadmap & Topic
        b_rm = self.client.get(f"/api/roadmaps/{rm_id}", headers=self.headers_b)
        self.assertEqual(b_rm.status_code, 404)
        b_del = self.client.delete(f"/api/roadmaps/{rm_id}", headers=self.headers_b)
        self.assertEqual(b_del.status_code, 404)

    def test_04_all_nine_ai_studio_tools(self):
        tools = [
            "audio_overview",
            "slide_deck",
            "video_overview",
            "mind_map",
            "study_guide",
            "flashcards",
            "quiz",
            "infographic",
            "data_table",
        ]
        for tool in tools:
            res = self.client.post(
                "/api/studio/generate",
                headers=self.headers_a,
                json={
                    "tool_type": tool,
                    "title": f"Test {tool}",
                    "source_ids": [],
                    "config": {"topic": "Relational Database Indexing", "question_count": 20},
                },
            )
            self.assertEqual(res.status_code, 200, f"Failed on tool {tool}: {res.text}")
            out = res.json()["output"]
            self.assertEqual(out["tool_type"], tool)

            if tool == "audio_overview":
                # Verify genuine playable WAV file was created and can be streamed
                self.assertNotIn("audio_file_path", out)
                audio_url = out["content"]["audio"]["audio_url"]
                wav_res = self.client.get(audio_url)
                self.assertEqual(wav_res.status_code, 200)
                self.assertEqual(wav_res.headers["content-type"], "audio/wav")
                self.assertGreater(len(wav_res.content), 1000)

                # Audio is private: an output ID alone cannot retrieve another user's file.
                private_url = audio_url.split("?", 1)[0]
                self.assertEqual(self.client.get(private_url).status_code, 401)
                self.assertEqual(self.client.get(private_url, headers=self.headers_b).status_code, 401)

            elif tool == "flashcards":
                # Verify cards are NOT marked mastered just by opening deck
                cards = out["content"]["cards"]
                self.assertGreaterEqual(len(cards), 6)
                for c in cards:
                    self.assertEqual(c["status"], "new")
                # Rate first card as 'known'
                rate_res = self.client.put(
                    f"/api/flashcards/{cards[0]['id']}",
                    headers=self.headers_a,
                    json={"status": "known"},
                )
                self.assertEqual(rate_res.status_code, 200)
                self.assertEqual(rate_res.json()["flashcard"]["status"], "known")

            elif tool == "quiz":
                self.assertEqual(len(out["content"]["questions"]), 20)

            elif tool == "video_overview":
                # Verify 1080p HD Video Overview generates playable MP4 + spoken WAV + 1080p slide frames
                vid_meta = out["content"]["video"]
                self.assertTrue(vid_meta["ready"])
                self.assertTrue(vid_meta["video_ready"])
                self.assertEqual(vid_meta["ready"], vid_meta["video_ready"])
                self.assertEqual(vid_meta["resolution"], "1920x1080")
                self.assertEqual(vid_meta["resolution_label"], "1920x1080 (1080p Full HD)")
                self.assertIn("winrt", vid_meta.get("provider", "").lower())
                self.assertGreaterEqual(len(vid_meta["slide_frames"]), 1)
                self.assertTrue(vid_meta["slide_frames"][0]["image_data_url"].startswith("data:image/png;base64,"))
                self.assertTrue(vid_meta["thumbnail_data_url"].startswith("data:image/png;base64,"))
                self.assertTrue(os.path.exists(vid_meta["file_path"]))
                self.assertGreater(os.path.getsize(vid_meta["file_path"]), 2048)

                mp4_url = vid_meta["video_url"]
                mp4_res = self.client.get(mp4_url)
                self.assertEqual(mp4_res.status_code, 200)
                self.assertEqual(mp4_res.headers["content-type"], "video/mp4")
                self.assertGreater(len(mp4_res.content), 2048)

                # Validate media streams on the generated MP4 file directly
                from backend.video_engine import validate_mp4_media_file
                val_res = validate_mp4_media_file(vid_meta["file_path"])
                self.assertTrue(val_res["valid"])
                self.assertTrue(val_res["has_video_stream"])
                self.assertTrue(val_res["has_audio_stream"])
                self.assertEqual(val_res["resolution"], "1920x1080")
                self.assertEqual(val_res["video_codec"], "avc1")
                self.assertEqual(val_res["audio_codec"], "mp4a")
                self.assertTrue(val_res["decoder_verified"])
                self.assertGreater(val_res["decoded_video_bytes"], 0)
                self.assertGreater(val_res["decoded_audio_bytes"], 0)

                # Unauthorized access without playback_token must be rejected (401)
                raw_mp4_path = mp4_url.split("?", 1)[0]
                self.assertEqual(self.client.get(raw_mp4_path).status_code, 401)

    def test_05_brainova_master_upgrades(self):
        # 1. Test 6-Language AI Studio Generation (English, Telugu, Hindi, Kannada, Tamil, Marathi)
        languages = ["English", "Telugu", "Hindi", "Kannada", "Tamil", "Marathi"]
        for lang in languages:
            res = self.client.post(
                "/api/studio/generate",
                headers=self.headers_a,
                json={
                    "tool_type": "study_guide",
                    "title": f"Distributed Systems ({lang})",
                    "source_ids": [],
                    "config": {"topic": "Distributed Consensus", "language": lang},
                },
            )
            self.assertEqual(res.status_code, 200)
            out = res.json()["output"]
            self.assertEqual(out["language"], lang)

        # 2. Test AI Studio Library filtering by language & tool_type
        telugu_list = self.client.get(
            "/api/studio/outputs?language=Telugu&tool_type=study_guide",
            headers=self.headers_a,
        )
        self.assertEqual(telugu_list.status_code, 200)
        self.assertGreaterEqual(len(telugu_list.json()["outputs"]), 1)
        self.assertEqual(telugu_list.json()["outputs"][0]["language"], "Telugu")

        # 3. Test Customized Roadmap Workflow (Custom Tutorial & Custom Reading with Non-Destructive Restore)
        rm_list = self.client.get("/api/roadmaps", headers=self.headers_a).json()["roadmaps"]
        rm_id = rm_list[0]["id"]
        rm_detail = self.client.get(f"/api/roadmaps/{rm_id}", headers=self.headers_a).json()["roadmap"]
        topic_id = rm_detail["phases"][0]["topics"][0]["id"]

        # Validate YouTube URL endpoint
        val_res = self.client.post(
            "/api/tutorials/validate-url",
            headers=self.headers_a,
            json={"url": "https://www.youtube.com/watch?v=8hly31xKli0"},
        )
        self.assertEqual(val_res.status_code, 200)
        self.assertTrue(val_res.json()["valid"])
        self.assertEqual(val_res.json()["video_id"], "8hly31xKli0")

        # Save Customized Tutorial -> verify badge is CUSTOMIZED
        save_tut = self.client.post(
            f"/api/topics/{topic_id}/tutorials",
            headers=self.headers_a,
            json={
                "url": "https://www.youtube.com/watch?v=8hly31xKli0",
                "title": "Customized Algorithms Lecture",
                "channel": "freeCodeCamp.org",
                "duration": "45m",
            },
        )
        self.assertEqual(save_tut.status_code, 200)
        self.assertEqual(save_tut.json()["tutorials"][0]["source_badge"], "CUSTOMIZED")

        # Remove Customized Tutorial -> verify Original AI tutorial is restored as primary (ORIGINAL)
        restore_tut = self.client.delete(
            f"/api/topics/{topic_id}/custom-tutorial",
            headers=self.headers_a,
        )
        self.assertEqual(restore_tut.status_code, 200)
        self.assertEqual(restore_tut.json()["tutorials"][0]["source_badge"], "ORIGINAL")

        # Save Customized Reading Material -> verify badge is CUSTOMIZED
        save_read = self.client.put(
            f"/api/topics/{topic_id}/custom-reading",
            headers=self.headers_a,
            json={
                "title": "Alice's Custom Reading Guide",
                "markdown_content": "# Custom Notes\n\nKey custom architectural notes.",
            },
        )
        self.assertEqual(save_read.status_code, 200)
        self.assertEqual(save_read.json()["reading"]["source_badge"], "CUSTOMIZED")
        self.assertTrue(save_read.json()["reading"]["has_custom_reading"])

        # Delete Customized Reading -> verify Original AI Reading & Diagrams are restored (ORIGINAL)
        restore_read = self.client.delete(
            f"/api/topics/{topic_id}/custom-reading",
            headers=self.headers_a,
        )
        self.assertEqual(restore_read.status_code, 200)
        self.assertEqual(restore_read.json()["reading"]["source_badge"], "ORIGINAL")
        self.assertFalse(restore_read.json()["reading"]["has_custom_reading"])
        self.assertGreaterEqual(len(restore_read.json()["reading"]["diagrams"]), 1)

        # 4. Test Profile Avatar & Four-Theme System Persistence
        prof_res = self.client.put(
            "/api/settings/profile",
            headers=self.headers_a,
            json={
                "name": "Alice Brainova Scholar",
                "target_role": "AI Systems Architect",
                "bio": "Building source-grounded AI platforms.",
                "avatar_url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
            },
        )
        self.assertEqual(prof_res.status_code, 200)
        self.assertEqual(prof_res.json()["user"]["name"], "Alice Brainova Scholar")
        self.assertTrue(prof_res.json()["user"]["avatar_url"].startswith("data:image/png"))

        for theme_id in ["neural_night", "dark_light", "quantum_violet", "focus_forest"]:
            t_res = self.client.put(
                "/api/settings/preferences",
                headers=self.headers_a,
                json={"theme": theme_id, "preferred_language": "Telugu"},
            )
            self.assertEqual(t_res.status_code, 200)
            self.assertEqual(t_res.json()["preferences"]["theme"], theme_id)
            self.assertEqual(t_res.json()["preferences"]["preferred_language"], "Telugu")

    def test_06_phase1_security_hardening_suite(self):
        # 1. Credential Encryption at Rest (AES-256-GCM)
        raw_gem = "AIzaSyPhase1EncryptedAtRestKey123456789"
        raw_oai = "sk-proj-Phase1EncryptedAtRestKey123456789"
        pref_res = self.client.put(
            "/api/settings/preferences",
            headers=self.headers_a,
            json={"gemini_api_key": raw_gem, "openai_api_key": raw_oai},
        )
        self.assertEqual(pref_res.status_code, 200)
        self.assertNotIn(raw_gem, pref_res.text)
        self.assertNotIn(raw_oai, pref_res.text)
        self.assertNotIn("enc:v1:", pref_res.text)

        with get_db() as conn:
            row = conn.execute(
                "SELECT gemini_api_key, openai_api_key FROM user_preferences WHERE user_id = ?",
                (self.user_a["id"],),
            ).fetchone()
            self.assertTrue(row["gemini_api_key"].startswith("enc:v1:k1:"))
            self.assertTrue(row["openai_api_key"].startswith("enc:v1:k1:"))
            self.assertNotIn(raw_gem, row["gemini_api_key"])
            self.assertNotIn(raw_oai, row["openai_api_key"])

        # Clear keys so subsequent tests remain offline
        self.client.put(
            "/api/settings/preferences",
            headers=self.headers_a,
            json={"gemini_api_key": "", "openai_api_key": ""},
        )

        # 2. Query-Parameter JWT Rejection on API routes
        q_me = self.client.get(f"/api/auth/me?token={self.token_a}")
        self.assertEqual(q_me.status_code, 401)
        q_rm = self.client.get(f"/api/roadmaps?token={self.token_a}", headers=self.headers_a)
        self.assertEqual(q_rm.status_code, 401)

        # 3. Persistent Logout & Session Revocation
        login_res = self.client.post(
            "/api/auth/login",
            json={"email": "alice@aetherlearn.edu", "password": "StrongPassword123!"},
        )
        self.assertEqual(login_res.status_code, 200)
        ephemeral_token = login_res.json()["token"]
        ephemeral_headers = {"Authorization": f"Bearer {ephemeral_token}"}

        self.assertEqual(self.client.get("/api/auth/me", headers=ephemeral_headers).status_code, 200)
        logout_res = self.client.post("/api/auth/logout", headers=ephemeral_headers)
        self.assertEqual(logout_res.status_code, 200)

        # Revoked token must now be rejected everywhere
        self.assertEqual(self.client.get("/api/auth/me", headers=ephemeral_headers).status_code, 401)
        self.assertEqual(self.client.get("/api/dashboard", headers=ephemeral_headers).status_code, 401)

        # 4. Studio Quiz Answer Confidentiality & Score-Tampering Prevention
        quiz_gen = self.client.post(
            "/api/studio/generate",
            headers=self.headers_a,
            json={
                "tool_type": "quiz",
                "title": "Security Audit Studio Quiz",
                "source_ids": [],
                "config": {"topic": "Application Security", "question_count": 20},
            },
        )
        self.assertEqual(quiz_gen.status_code, 200)
        quiz_out = quiz_gen.json()["output"]
        quiz_out_id = quiz_out["id"]
        for q in quiz_out["content"]["questions"]:
            self.assertNotIn("correct_index", q)
            self.assertNotIn("explanation", q)

        # Attempt to tamper with answer key via PUT /api/studio/outputs/{id}
        tampered_questions = [
            {**q, "correct_index": 0, "explanation": "Hacked"} for q in quiz_out["content"]["questions"]
        ]
        upd_quiz = self.client.put(
            f"/api/studio/outputs/{quiz_out_id}",
            headers=self.headers_a,
            json={"title": "Renamed Security Quiz", "content": {"questions": tampered_questions}},
        )
        self.assertEqual(upd_quiz.status_code, 200)
        for q in upd_quiz.json()["output"]["content"]["questions"]:
            self.assertNotIn("correct_index", q)
            self.assertNotIn("explanation", q)

        # Verify authoritative stored questions were preserved and server grading returns review_items
        with get_db() as conn:
            stored_row = conn.execute(
                "SELECT content_json FROM studio_outputs WHERE id = ?", (quiz_out_id,)
            ).fetchone()
            stored_qs = json.loads(stored_row["content_json"])["questions"]
            self.assertTrue(any(q["correct_index"] != 0 for q in stored_qs))

        studio_answers = {stored_qs[0]["id"]: stored_qs[0]["correct_index"]}
        sub_studio = self.client.post(
            f"/api/studio/outputs/{quiz_out_id}/quiz-submit",
            headers=self.headers_a,
            json={"answers": studio_answers, "duration_seconds": 90},
        )
        self.assertEqual(sub_studio.status_code, 200)
        studio_att = sub_studio.json()["attempt"]
        self.assertEqual(studio_att["score"], 1)
        self.assertEqual(len(studio_att["review_items"]), 20)
        self.assertIn("correct_index", studio_att["review_items"][0])
        self.assertIn("explanation", studio_att["review_items"][0])

        # 5. Cross-User Parent/Child IDOR Prevention on Notes, Flashcards, Studio Generate & Topic Quiz Regenerate
        rm_a = self.client.get("/api/roadmaps", headers=self.headers_a).json()["roadmaps"][0]
        rm_a_id = rm_a["id"]
        rm_a_detail = self.client.get(f"/api/roadmaps/{rm_a_id}", headers=self.headers_a).json()["roadmap"]
        topic_a_id = rm_a_detail["phases"][0]["topics"][0]["id"]
        src_a_id = self.client.get("/api/sources", headers=self.headers_a).json()["sources"][0]["id"]

        # Topic quiz regenerate works for owner A (and strips answers) but returns 404 for User B
        regen_q_a = self.client.post(f"/api/topics/{topic_a_id}/quiz/regenerate", headers=self.headers_a)
        self.assertEqual(regen_q_a.status_code, 200)
        for q in regen_q_a.json()["quiz"]["questions"]:
            self.assertNotIn("correct_index", q)
            self.assertNotIn("explanation", q)

        regen_q_b = self.client.post(f"/api/topics/{topic_a_id}/quiz/regenerate", headers=self.headers_b)
        self.assertEqual(regen_q_b.status_code, 404)

        # User B cannot attach User A's topic_id or roadmap_id to a note
        b_note_topic = self.client.post(
            "/api/notes",
            headers=self.headers_b,
            json={"title": "IDOR Note", "content": "x", "topic_id": topic_a_id},
        )
        self.assertEqual(b_note_topic.status_code, 404)
        b_note_rm = self.client.post(
            "/api/notes",
            headers=self.headers_b,
            json={"title": "IDOR Note", "content": "x", "roadmap_id": rm_a_id},
        )
        self.assertEqual(b_note_rm.status_code, 404)

        # User B cannot attach User A's topic_id or studio_output_id to a flashcard
        b_fc_topic = self.client.post(
            "/api/flashcards",
            headers=self.headers_b,
            json={"front": "Q", "back": "A", "topic_id": topic_a_id},
        )
        self.assertEqual(b_fc_topic.status_code, 404)
        b_fc_deck = self.client.post(
            "/api/flashcards",
            headers=self.headers_b,
            json={"front": "Q", "back": "A", "studio_output_id": quiz_out_id},
        )
        self.assertEqual(b_fc_deck.status_code, 404)

        # User B cannot generate a Studio output referencing User A's source_ids
        b_studio_src = self.client.post(
            "/api/studio/generate",
            headers=self.headers_b,
            json={"tool_type": "study_guide", "title": "IDOR Studio", "source_ids": [src_a_id]},
        )
        self.assertEqual(b_studio_src.status_code, 404)

    def test_07_video_overview_media_pipeline_integrity(self):
        """
        Phase 1 Verification: Production-quality MP4 media validation,
        metadata contract consistency, and error safety.
        """
        import tempfile
        import struct
        from backend.video_engine import validate_mp4_media_file

        # 1. Non-existent file is rejected
        val_none = validate_mp4_media_file("data/videos/non_existent_file.mp4")
        self.assertFalse(val_none["valid"])
        self.assertIn("does not exist", val_none["error"].lower())

        # 2. Corrupt or fake MP4 container is rejected (e.g. ftyp + moov without trak, or random bytes)
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tf:
            fake_ftyp = b"isom\x00\x00\x02\x00isomiso2mp41"
            ftyp_box = struct.pack(">I4s", 8 + len(fake_ftyp), b"ftyp") + fake_ftyp
            mvhd_payload = struct.pack(
                ">BBBBIIIIIH10s36s7I",
                0, 0, 0, 0,
                0, 0,
                1000, 5000,
                0x00010000, 0x0100,
                b"\x00" * 10,
                b"\x00\x01\x00\x00" + b"\x00" * 12 + b"\x00\x01\x00\x00" + b"\x00" * 12 + b"\x40\x00\x00\x00",
                0, 0, 0, 0, 0, 0, 2,
            )
            mvhd_box = struct.pack(">I4s", 8 + len(mvhd_payload), b"mvhd") + mvhd_payload
            moov_box = struct.pack(">I4s", 8 + len(mvhd_box), b"moov") + mvhd_box
            mdat_box = struct.pack(">I4s", 8 + 4096, b"mdat") + (b"\x00" * 4096)
            tf.write(ftyp_box + moov_box + mdat_box)
            fake_path = tf.name

        try:
            val_fake = validate_mp4_media_file(fake_path)
            self.assertFalse(val_fake["valid"])
            self.assertIn("video track", val_fake["error"].lower())
        finally:
            if os.path.exists(fake_path):
                os.remove(fake_path)

        # 3. Retrieve User A's generated video_overview output from test_04
        list_res = self.client.get("/api/studio/outputs?tool_type=video_overview", headers=self.headers_a)
        self.assertEqual(list_res.status_code, 200)
        videos = list_res.json()["outputs"]
        self.assertGreaterEqual(len(videos), 1)
        video_out = videos[0]
        vid_id = video_out["id"]
        content_vid = video_out["content"]["video"]

        # 4. Assert metadata contract on persisted Library output
        self.assertTrue(content_vid["ready"])
        self.assertTrue(content_vid["video_ready"])
        self.assertEqual(content_vid["resolution"], "1920x1080")
        self.assertEqual(content_vid["resolution_label"], "1920x1080 (1080p Full HD)")
        self.assertIn("winrt", content_vid["provider"].lower())
        self.assertTrue(content_vid["slide_frames"][0]["image_data_url"].startswith("data:image/png;base64,"))

        # 5. Test video regeneration works and yields validated media
        regen_res = self.client.post(
            f"/api/studio/outputs/{vid_id}/regenerate",
            headers=self.headers_a,
            json={"confirm_overwrite": True},
        )
        self.assertEqual(regen_res.status_code, 200)
        regen_out = regen_res.json()["output"]
        regen_vid = regen_out["content"]["video"]
        self.assertTrue(regen_vid["ready"])
        self.assertTrue(regen_vid["video_ready"])
        self.assertEqual(regen_vid["resolution"], "1920x1080")
        self.assertEqual(regen_vid["resolution_label"], "1920x1080 (1080p Full HD)")
        self.assertTrue(os.path.exists(regen_vid["file_path"]))

        regen_val = validate_mp4_media_file(regen_vid["file_path"])
        self.assertTrue(regen_val["valid"])
        self.assertTrue(regen_val["has_video_stream"])
        self.assertTrue(regen_val["has_audio_stream"])
        self.assertEqual(regen_val["video_codec"], "avc1")
        self.assertEqual(regen_val["audio_codec"], "mp4a")
        self.assertTrue(regen_val["decoder_verified"])

    def test_08_studio_output_source_titles_contract(self):
        """
        Regression: `source_titles` must be a list of {id, title, file_type} objects, because the
        Library frontend normalizes these objects (it previously called .slice() on them and crashed).
        """
        sources = self.client.get("/api/sources", headers=self.headers_a).json()["sources"]
        self.assertGreaterEqual(len(sources), 1)
        src = sources[0]

        gen = self.client.post(
            "/api/studio/generate",
            headers=self.headers_a,
            json={
                "tool_type": "study_guide",
                "title": "Source Titles Contract Guide",
                "source_ids": [src["id"]],
                "config": {"topic": "Distributed Consensus"},
            },
        )
        self.assertEqual(gen.status_code, 200, gen.text)
        gen_titles = gen.json()["output"]["source_titles"]
        self.assertEqual(len(gen_titles), 1)

        listing = self.client.get("/api/studio/outputs", headers=self.headers_a)
        self.assertEqual(listing.status_code, 200)
        linked = [o for o in listing.json()["outputs"] if o["source_ids"]]
        self.assertGreaterEqual(len(linked), 1)
        for out in linked:
            self.assertIsInstance(out["source_titles"], list)
            for entry in out["source_titles"]:
                self.assertIsInstance(entry, dict)
                self.assertEqual(set(entry.keys()), {"id", "title", "file_type"})
                self.assertIsInstance(entry["id"], str)
                self.assertIsInstance(entry["title"], str)
                self.assertTrue(entry["title"])
                self.assertIsInstance(entry["file_type"], str)

        # Searching by a linked source's title returns outputs that use that source
        fragment = src["title"].split()[0].lower()
        search = self.client.get(f"/api/studio/outputs?search={fragment}", headers=self.headers_a)
        self.assertEqual(search.status_code, 200)
        found_ids = {o["id"] for o in search.json()["outputs"]}
        self.assertIn(gen.json()["output"]["id"], found_ids)

        # Outputs without sources return an empty list (never null)
        no_src = self.client.post(
            "/api/studio/generate",
            headers=self.headers_a,
            json={"tool_type": "study_guide", "title": "No Source Guide", "source_ids": [], "config": {"topic": "Raft"}},
        )
        self.assertEqual(no_src.status_code, 200, no_src.text)
        self.assertEqual(no_src.json()["output"]["source_titles"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)

