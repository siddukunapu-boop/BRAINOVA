"""Targeted tests for BRAINOVA Reading Materials & React Error #31 backend fixes."""

import json
import unittest
from backend.ai_engine import generateTopicReading
from backend.main import _format_reading_row, _normalize_mistakes_list


class ReadingMaterialsTests(unittest.TestCase):
    def test_programming_topic_event_loop_reading_and_diagram(self):
        res = generateTopicReading(
            topic_title="JavaScript Event Loop & Async Execution",
            topic_description="How Call Stack, Web APIs, Microtask Queue, and Callback Queue work.",
            subtopics=["Call Stack", "Web APIs", "Microtask Queue", "Callback Queue"],
            difficulty="Intermediate",
            target_role="Full Stack Developer",
        )
        self.assertIn("Event Loop", res["overview"])
        self.assertGreaterEqual(len(res["sections"]), 2)
        self.assertGreaterEqual(len(res["diagrams"]), 1)
        node_labels = [n["label"] for n in res["diagrams"][0]["nodes"]]
        self.assertIn("Call Stack", node_labels)
        self.assertIn("Microtask Queue", node_labels)
        self.assertIn("Event Loop", node_labels)
        self.assertGreaterEqual(len(res["code_examples"]), 1)
        self.assertTrue(all(isinstance(m, dict) and "mistake" in m and "why_it_happens" in m and "fix" in m for m in res["common_mistakes"]))

    def test_conceptual_topic_database_normalization_reading_and_diagram(self):
        res = generateTopicReading(
            topic_title="Database Normalization (1NF, 2NF, 3NF)",
            topic_description="Eliminating anomalies with primary and foreign keys.",
            subtopics=["1NF Atomicity", "2NF Partial Dependencies", "3NF Transitive Dependencies"],
            difficulty="Intermediate",
            target_role="Backend Engineer",
        )
        self.assertIn("Normalization", res["overview"])
        self.assertGreaterEqual(len(res["diagrams"]), 1)
        node_steps = [n["step"] for n in res["diagrams"][0]["nodes"]]
        self.assertIn("1NF", node_steps)
        self.assertIn("3NF", node_steps)
        self.assertGreaterEqual(len(res["comparison_tables"]), 1)

    def test_generic_topic_uses_subtopic_progression_not_boilerplate(self):
        res = generateTopicReading(
            topic_title="CSS Grid & Flexbox Layout",
            topic_description="Two-dimensional and one-dimensional responsive CSS layout systems.",
            subtopics=["Flexbox Main & Cross Axis", "CSS Grid Tracks", "Responsive Breakpoints"],
            difficulty="Beginner",
            target_role="Frontend Developer",
        )
        self.assertGreaterEqual(len(res["diagrams"]), 1)
        node_labels = [n["label"] for n in res["diagrams"][0]["nodes"]]
        self.assertNotIn("Input & Contract Gate", node_labels)
        self.assertIn("Flexbox Main & Cross Axis", node_labels)

    def test_normalize_mistakes_and_format_reading_row(self):
        normalized = _normalize_mistakes_list([
            {"mistake": "M1", "why_it_happens": "W1", "fix": "F1"},
            "Plain string mistake",
            {"title": "Alt", "reason": "Why", "solution": "Fix"},
            123,
        ])
        self.assertEqual(len(normalized), 3)
        self.assertEqual(normalized[0], {"mistake": "M1", "why_it_happens": "W1", "fix": "F1"})
        self.assertEqual(normalized[1], {"mistake": "Plain string mistake", "why_it_happens": "", "fix": ""})
        self.assertEqual(normalized[2], {"mistake": "Alt", "why_it_happens": "Why", "fix": "Fix"})

        row = {
            "id": "read_1",
            "topic_id": "top_1",
            "title": "Test Topic",
            "overview": "Overview text",
            "sections_json": json.dumps([{"id": "s1", "heading": "S1", "content": "Body"}]),
            "diagrams_json": "[]",
            "markdown_content": "# Test",
            "key_definitions_json": "[]",
            "code_examples_json": "[]",
            "comparison_tables_json": "[]",
            "common_mistakes_json": json.dumps([{"mistake": "Bug", "why_it_happens": "Reason", "fix": "Fix"}]),
            "interview_questions_json": "[]",
            "summary": "Summary",
            "references_json": "[]",
            "updated_at": "2026-11-13T00:00:00Z",
        }
        formatted = _format_reading_row(row, "Test Topic")
        self.assertIsNotNone(formatted)
        self.assertEqual(formatted["mistakes"], [{"mistake": "Bug", "why_it_happens": "Reason", "fix": "Fix"}])
        self.assertEqual(formatted["common_mistakes"], formatted["mistakes"])

    def test_persistence_refresh_and_ownership_isolation(self):
        import os
        import tempfile
        from fastapi import HTTPException
        from backend import database as db_mod
        from backend import main as main_mod

        orig_db = os.environ.get("AETHER_DB_PATH")
        fd, tmp_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            os.environ["AETHER_DB_PATH"] = tmp_path
            db_mod.init_db()
            uid1 = "user_test_1"
            uid2 = "user_test_2"
            now = db_mod.utc_now()
            with db_mod.get_db(commit=True) as conn:
                for uid, email in [(uid1, "u1@example.com"), (uid2, "u2@example.com")]:
                    conn.execute(
                        "INSERT INTO users (id, name, email, password_hash, target_role, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (uid, uid, email, "hash", "Full Stack Developer", now, now),
                    )
                conn.execute(
                    "INSERT INTO roadmaps (id, user_id, title, target_role, description, skill_level, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    ("rm_1", uid1, "JS Roadmap", "Full Stack Developer", "Desc", "Intermediate", now, now),
                )
                conn.execute(
                    "INSERT INTO roadmap_phases (id, roadmap_id, user_id, phase_order, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    ("ph_1", "rm_1", uid1, 1, "Async JS", now, now),
                )
                conn.execute(
                    "INSERT INTO roadmap_topics (id, phase_id, roadmap_id, user_id, topic_order, title, description, subtopics_json, learning_objectives_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        "top_1",
                        "ph_1",
                        "rm_1",
                        uid1,
                        1,
                        "JavaScript Event Loop",
                        "Understand Call Stack and Queues",
                        json.dumps(["Call Stack", "Web APIs", "Microtask Queue", "Callback Queue"]),
                        json.dumps(["Trace async execution order"]),
                        now,
                        now,
                    ),
                )

            u1 = {"id": uid1, "email": "u1@example.com"}
            u2 = {"id": uid2, "email": "u2@example.com"}

            # 1. Generate & persist reading on first open
            ws1 = main_mod.get_topic_workspace("top_1", auto_prepare=True, current_user=u1)
            r1 = ws1["reading"]
            self.assertIsNotNone(r1)
            self.assertGreaterEqual(len(r1["diagrams"]), 1)
            self.assertGreaterEqual(len(r1["mistakes"]), 1)
            self.assertIsInstance(r1["mistakes"][0], dict)

            # 2. Reopen without auto_prepare (simulates refresh) and verify no duplicate rows
            ws2 = main_mod.get_topic_workspace("top_1", auto_prepare=False, current_user=u1)
            self.assertEqual(ws2["reading"]["id"], r1["id"])
            with db_mod.get_db() as conn:
                cnt = conn.execute("SELECT COUNT(*) AS c FROM topic_readings WHERE topic_id = ?", ("top_1",)).fetchone()["c"]
            self.assertEqual(cnt, 1)

            # 3. Cross-user ownership check
            with self.assertRaises(HTTPException) as ctx:
                main_mod.get_topic_workspace("top_1", auto_prepare=False, current_user=u2)
            self.assertEqual(ctx.exception.status_code, 404)
        finally:
            if orig_db is None:
                os.environ.pop("AETHER_DB_PATH", None)
            else:
                os.environ["AETHER_DB_PATH"] = orig_db
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


if __name__ == "__main__":
    unittest.main()
