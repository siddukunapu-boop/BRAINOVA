"""
Regression & Cross-Domain Quality Tests for AI Studio Cycle 1 (7 Non-Video Tools).
Uses temporary SQLite databases and mocked LLM responses — zero live DB writes,
zero media modifications, and zero paid external API calls.
"""

import asyncio
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

import httpx

TEST_DB_DIR = tempfile.mkdtemp(prefix="studio_intel_test_")
os.environ["AETHER_DB_PATH"] = os.path.join(TEST_DB_DIR, "test_studio.db")
os.environ["BRAINOVA_MASTER_KEY_FILE"] = os.path.join(TEST_DB_DIR, ".test_master_key")

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from fastapi.testclient import TestClient  # noqa: E402
from backend import ai_engine, database, main  # noqa: E402
from backend.studio_engine import StudioGenerationError  # noqa: E402


# Reusable Cross-Domain Evaluation Corpus
CORPUS = {
    "biology": [
        {
            "source_id": "src_bio_1",
            "source_title": "Cellular Respiration Notes",
            "page_number": 12,
            "section_title": "Oxidative Phosphorylation",
            "content": (
                "Glycolysis converts glucose into two molecules of pyruvate in the cytoplasm, yielding 2 ATP net. "
                "The proton gradient across the inner mitochondrial membrane drives ATP synthase to phosphorylate ADP into ATP. "
                "Oxygen acts as the terminal electron acceptor in the electron transport chain, forming water. "
                "Unlike aerobic respiration, alcoholic fermentation in yeast decarboxylates pyruvate to acetaldehyde and reduces it with NADH to ethanol."
            ),
        }
    ],
    "computer_science": [
        {
            "source_id": "src_cs_1",
            "source_title": "Operating Systems Scheduling",
            "page_number": 5,
            "section_title": "CPU Scheduling",
            "content": (
                "Priority scheduling assigns each process a priority number and allocates the CPU to the highest-priority runnable process. "
                "Starvation occurs when low-priority processes wait indefinitely because higher-priority processes continually arrive. "
                "Aging prevents starvation by gradually increasing the priority of processes that wait in the ready queue for a long time. "
                "| Algorithm | Preemptive | Starvation Risk |\n"
                "| FCFS | No | Low |\n"
                "| Priority | Optional | High without aging |"
            ),
        }
    ],
    "economics": [
        {
            "source_id": "src_econ_1",
            "source_title": "Macroeconomics Policy",
            "page_number": 44,
            "section_title": "Central Bank Tools",
            "content": (
                "Central banks regulate the money supply and benchmark interest rates to stabilize inflation and employment. "
                "Open market operations involve buying or selling government bonds to expand or contract commercial bank reserves. "
                "Higher policy interest rates raise borrowing costs, which reduces aggregate demand and cools inflation. "
                "Reserve Ratio: 10% for large commercial banks.\n"
                "Target Inflation: 2% annually."
            ),
        }
    ],
    "history": [
        {
            "source_id": "src_hist_1",
            "source_title": "The First Industrial Revolution",
            "page_number": 19,
            "section_title": "Steam Power & Textiles",
            "content": (
                "James Watt improved the Newcomen steam engine in 1769 by adding a separate condenser, dramatically reducing coal consumption. "
                "Mechanized spinning frames and power looms shifted textile production from rural cottages into urban factories. "
                "Coal and iron production expanded rapidly to supply steam engines, railways, and industrial machinery. "
                "Whereas cottage industry relied on family labor at home, factory systems concentrated workers around centralized power sources."
            ),
        }
    ],
}

CS_BOILERPLATE_MARKERS = [
    "Idempotency",
    "Separation of Concerns",
    "Async Queue",
    "Concatenate raw user strings",
    "70%+ Mastery Threshold",
    "Schema Validated",
]


class TestStudioIntelligenceUnit(unittest.TestCase):
    def test_domain_neutrality_across_biology_economics_history_cs(self):
        """All 7 tools produce domain-appropriate, source-grounded offline outputs with zero CS boilerplate."""
        no_llm_prefs = {"ai_provider": "auto"}
        with patch.dict(os.environ, {}, clear=False):
            for subject, chunks in CORPUS.items():
                cfg = {"topic": chunks[0]["source_title"], "language": "English", "card_count": 6}
                slides = ai_engine.generateSlideDeck(chunks, cfg, user_prefs=no_llm_prefs)
                mind_map = ai_engine.generateMindMap(chunks, cfg, user_prefs=no_llm_prefs)
                guide = ai_engine.generateStudyGuide(chunks, cfg, user_prefs=no_llm_prefs)
                cards = ai_engine.generateFlashcards(chunks, cfg, user_prefs=no_llm_prefs)
                quiz = ai_engine.generateTopicQuiz(
                    topic_title=cfg["topic"],
                    source_passages=chunks,
                    question_count=8,
                    user_prefs=no_llm_prefs,
                )
                info = ai_engine.generateInfographicStructure(chunks, cfg, user_prefs=no_llm_prefs)
                table = ai_engine.extractStructuredTable(chunks, cfg, user_prefs=no_llm_prefs)

                self.assertGreaterEqual(len(slides["slides"]), 3)
                self.assertTrue(mind_map["root"]["children"])
                self.assertTrue(guide["sections"])
                self.assertGreaterEqual(len(cards["cards"]), 4)
                self.assertEqual(len(quiz["questions"]), 8)
                self.assertTrue(info["visual_sections"])
                self.assertTrue(table["rows"])

                if subject != "computer_science":
                    serialized = json.dumps([slides, mind_map, guide, cards, quiz, info, table])
                    for marker in CS_BOILERPLATE_MARKERS:
                        self.assertNotIn(
                            marker,
                            serialized,
                            f"CS boilerplate '{marker}' leaked into {subject} output!",
                        )

    def test_infographic_never_fabricates_mastery_percentages(self):
        info = ai_engine.generateInfographicStructure(
            CORPUS["history"],
            {"topic": "Industrial Revolution"},
            user_prefs={},
        )
        serialized = json.dumps(info)
        self.assertNotIn("70%+", serialized)
        self.assertNotIn("14/20 MCQ", serialized)

    def test_data_table_extracts_real_tables_and_key_values(self):
        cs_table = ai_engine.extractStructuredTable(CORPUS["computer_science"], {"topic": "Scheduling"}, user_prefs={})
        self.assertTrue(any("FCFS" in json.dumps(r) for r in cs_table["rows"]))
        econ_table = ai_engine.extractStructuredTable(CORPUS["economics"], {"topic": "Central Banks"}, user_prefs={})
        self.assertTrue(any("10%" in json.dumps(r) for r in econ_table["rows"]))

    def test_mind_map_relationships_reference_valid_node_ids(self):
        mm = ai_engine.generateMindMap(CORPUS["biology"], {"topic": "Cellular Respiration"}, user_prefs={})
        ids = set()

        def collect(node):
            ids.add(node["id"])
            for c in node.get("children", []):
                collect(c)

        collect(mm["root"])
        for rel in mm["relationships"]:
            self.assertIn(rel["from"], ids)
            self.assertIn(rel["to"], ids)

    def test_insufficient_evidence_raises_structured_error_when_source_ids_given(self):
        with self.assertRaises(StudioGenerationError) as ctx:
            ai_engine.generateSlideDeck(
                chunks=[],
                config={"topic": "Empty"},
                user_prefs={},
                source_ids=["src_missing"],
            )
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertEqual(ctx.exception.code, "insufficient_source_evidence")

    def test_mocked_llm_path_and_malformed_json_repair(self):
        """Mocked Gemini-style JSON succeeds; malformed/empty LLM JSON falls back safely."""
        mock_slide_resp = (
            {
                "title": "Biology: ATP Synthesis",
                "learning_objectives": ["Explain chemiosmosis"],
                "slides": [
                    {"title": "Intro", "subtitle": "Overview", "bullets": ["ATP synthase uses proton gradient."]},
                    {"title": "Electron Transport", "subtitle": "Mechanism", "bullets": ["Oxygen is terminal acceptor."]},
                    {"title": "Fermentation", "subtitle": "Anaerobic", "bullets": ["Pyruvate forms acetaldehyde then ethanol."]},
                ],
            },
            "gemini",
        )
        with patch("backend.ai_engine.call_llm_json", return_value=mock_slide_resp):
            res = ai_engine.generateSlideDeck(CORPUS["biology"], {"topic": "Respiration"}, user_prefs={})
            self.assertEqual(res["generation_provider"], "gemini")
            self.assertEqual(len(res["slides"]), 3)

        # Malformed LLM output conservatively falls back to local_structured_engine
        with patch("backend.ai_engine.call_llm_json", return_value=({"bad": "schema"}, "gemini")):
            res_fb = ai_engine.generateSlideDeck(CORPUS["biology"], {"topic": "Respiration"}, user_prefs={})
            self.assertEqual(res_fb["generation_provider"], "local_structured_engine")
            self.assertGreaterEqual(len(res_fb["slides"]), 2)


class TestStudioPersistenceAndRegeneration(unittest.TestCase):
    @classmethod
    def _req(cls, method: str, path: str, **kwargs):
        async def _do():
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=main.app),
                base_url="http://testserver",
                timeout=15.0,
            ) as client:
                return await client.request(method, path, **kwargs)
        return asyncio.run(_do())

    @classmethod
    def setUpClass(cls):
        database.init_db()
        from backend.email_service import set_email_sender_for_tests

        captured_otps = {}

        def _capture_email(to_email: str, _name: str, otp_code: str, _expires: int):
            captured_otps[to_email.lower()] = otp_code

        set_email_sender_for_tests(_capture_email)
        try:
            # Register User A & User B
            r_a = cls._req("POST", "/api/auth/signup", json={
                "name": "Audit User A",
                "email": "studio_a@example.com",
                "password": "Password123!",
                "target_role": "Student",
            })
            assert r_a.status_code == 200, r_a.text
            v_a = cls._req("POST", "/api/auth/verify-email", json={
                "pending_token": r_a.json()["pending_token"],
                "otp_code": captured_otps["studio_a@example.com"],
            })
            assert v_a.status_code == 200, v_a.text
            cls.headers_a = {"Authorization": f"Bearer {v_a.json()['token']}"}
            cls.user_a_id = v_a.json()["user"]["id"]

            r_b = cls._req("POST", "/api/auth/signup", json={
                "name": "Audit User B",
                "email": "studio_b@example.com",
                "password": "Password123!",
                "target_role": "Student",
            })
            assert r_b.status_code == 200, r_b.text
            v_b = cls._req("POST", "/api/auth/verify-email", json={
                "pending_token": r_b.json()["pending_token"],
                "otp_code": captured_otps["studio_b@example.com"],
            })
            assert v_b.status_code == 200, v_b.text
            cls.headers_b = {"Authorization": f"Bearer {v_b.json()['token']}"}
        finally:
            set_email_sender_for_tests(None)

        # Seed a ready Biology source for User A
        with database.get_db(commit=True) as conn:
            conn.execute(
                """
                INSERT INTO sources (id, user_id, title, file_type, original_filename, file_path, file_size_bytes, page_count, status, created_at, updated_at)
                VALUES (?, ?, ?, '.txt', 'bio.txt', '', 512, 1, 'ready', '2026-11-13T00:00:00Z', '2026-11-13T00:00:00Z')
                """,
                ("src_bio_test", cls.user_a_id, "Biology Respiration Source"),
            )
            conn.execute(
                """
                INSERT INTO source_chunks (id, source_id, user_id, chunk_index, page_number, section_title, content, token_count, created_at)
                VALUES (?, ?, ?, 0, 12, 'Oxidative Phosphorylation', ?, 60, '2026-11-13T00:00:00Z')
                """,
                ("chk_bio_1", "src_bio_test", cls.user_a_id, CORPUS["biology"][0]["content"]),
            )

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(TEST_DB_DIR, ignore_errors=True)

    def test_flashcards_regenerate_replaces_rows_transactionally_and_preserves_unrelated_decks(self):
        # Create unrelated Deck 1 and mark card 0 as 'known'
        deck1 = self._req(
            "POST",
            "/api/studio/generate",
            headers=self.headers_a,
            json={"tool_type": "flashcards", "title": "Deck 1", "source_ids": ["src_bio_test"], "config": {"card_count": 4}},
        ).json()["output"]
        deck1_card0_id = deck1["content"]["cards"][0]["id"]
        self._req("PUT", f"/api/flashcards/{deck1_card0_id}", headers=self.headers_a, json={"status": "known"})

        # Create Deck 2
        deck2 = self._req(
            "POST",
            "/api/studio/generate",
            headers=self.headers_a,
            json={"tool_type": "flashcards", "title": "Deck 2", "source_ids": ["src_bio_test"], "config": {"card_count": 4}},
        ).json()["output"]
        old_ids = {c["id"] for c in deck2["content"]["cards"]}

        # Failure during regeneration must roll back and keep old_ids intact
        with patch("backend.main.generateFlashcards", side_effect=RuntimeError("simulated failure")):
            fail_res = self._req("POST", f"/api/studio/outputs/{deck2['id']}/regenerate", headers=self.headers_a, json={"confirm_overwrite": True})
            self.assertEqual(fail_res.status_code, 500)

        after_fail = self._req("GET", f"/api/studio/outputs/{deck2['id']}", headers=self.headers_a).json()["output"]
        self.assertEqual({c["id"] for c in after_fail["content"]["cards"]}, old_ids)

        # Successful regeneration replaces Deck 2's rows and resets status='new'
        regen = self._req(
            "POST",
            f"/api/studio/outputs/{deck2['id']}/regenerate",
            headers=self.headers_a,
            json={"confirm_overwrite": True},
        )
        self.assertEqual(regen.status_code, 200)
        new_cards = regen.json()["output"]["content"]["cards"]
        new_ids = {c["id"] for c in new_cards}
        self.assertTrue(old_ids.isdisjoint(new_ids))
        self.assertTrue(all(c["status"] == "new" for c in new_cards))

        # Verify Deck 1 is untouched
        deck1_after = self._req("GET", f"/api/studio/outputs/{deck1['id']}", headers=self.headers_a).json()["output"]
        self.assertEqual(deck1_after["content"]["cards"][0]["status"], "known")

    def test_quiz_regenerate_preserves_practice_mode_and_strips_answer_key(self):
        gen = self._req(
            "POST",
            "/api/studio/generate",
            headers=self.headers_a,
            json={
                "tool_type": "quiz",
                "title": "Bio Quiz",
                "source_ids": ["src_bio_test"],
                "config": {"question_count": 6, "practice_mode": True},
            },
        )
        self.assertEqual(gen.status_code, 200)
        quiz = gen.json()["output"]
        self.assertTrue(quiz["content"]["practice_mode_allowed"])
        for q in quiz["content"]["questions"]:
            self.assertNotIn("correct_index", q)
            self.assertNotIn("explanation", q)

        regen = self._req(
            "POST",
            f"/api/studio/outputs/{quiz['id']}/regenerate",
            headers=self.headers_a,
            json={"confirm_overwrite": True},
        )
        self.assertEqual(regen.status_code, 200)
        regen_quiz = regen.json()["output"]
        self.assertTrue(regen_quiz["content"]["practice_mode_allowed"])
        for q in regen_quiz["content"]["questions"]:
            self.assertNotIn("correct_index", q)
            self.assertNotIn("explanation", q)

    def test_unauthorized_source_id_rejected(self):
        res = self._req(
            "POST",
            "/api/studio/generate",
            headers=self.headers_b,
            json={"tool_type": "slide_deck", "source_ids": ["src_bio_test"], "config": {}},
        )
        self.assertEqual(res.status_code, 404)


if __name__ == "__main__":
    unittest.main()

