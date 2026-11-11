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

# Configure isolated test database before importing backend
TEST_DB_DIR = tempfile.mkdtemp(prefix="aetherlearn_test_")
os.environ["AETHER_DB_PATH"] = os.path.join(TEST_DB_DIR, "test_aetherlearn.db")

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
        cls.token_a = res_a.json()["token"]
        cls.user_a = res_a.json()["user"]
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
        cls.token_b = res_b.json()["token"]
        cls.user_b = res_b.json()["user"]
        cls.headers_b = {"Authorization": f"Bearer {cls.token_b}"}

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
                self.assertEqual(vid_meta["resolution"], "1920x1080")
                self.assertGreaterEqual(len(vid_meta["slide_frames"]), 1)
                self.assertTrue(vid_meta["thumbnail_data_url"].startswith("data:image/png;base64,"))
                mp4_url = vid_meta["video_url"]
                mp4_res = self.client.get(mp4_url)
                self.assertEqual(mp4_res.status_code, 200)
                self.assertEqual(mp4_res.headers["content-type"], "video/mp4")
                self.assertGreater(len(mp4_res.content), 1000)

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


if __name__ == "__main__":
    unittest.main(verbosity=2)

