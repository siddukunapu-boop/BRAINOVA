import json
import os
import sys
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def _write_silent_wav(path: Path, duration_sec: float = 12.0, sample_rate: int = 16000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    n_frames = int(duration_sec * sample_rate)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * n_frames)


class TestVideoOverviewAdaptiveCycle21(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp_dir = tempfile.TemporaryDirectory(prefix="brainova_c21_test_")
        cls.tmp_path = Path(cls.tmp_dir.name)
        os.environ["AETHER_DB_PATH"] = str(cls.tmp_path / "test_c21.db")

        import backend.database as db
        import backend.video_engine as ve

        db.DB_PATH = cls.tmp_path / "test_c21.db"
        db.init_db()
        ve.VIDEOS_DIR = cls.tmp_path / "videos"
        ve.AUDIO_DIR = cls.tmp_path / "audio"
        ve.VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
        ve.AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp_dir.cleanup()

    def test_01_adaptive_scene_counts_by_complexity_and_coverage(self):
        from backend.ai_engine import generateVideoStoryboard

        simple_chunks = [
            {
                "chunk_id": "s1",
                "source_id": "src_s",
                "source_title": "Ohms Law",
                "section_title": "Basics",
                "page_number": 1,
                "content": (
                    "Ohm's law states that electrical current through a conductor is directly proportional to voltage. "
                    "The fundamental equation V = I * R relates voltage, current, and resistance in linear circuits."
                ),
            }
        ]

        moderate_chunks = [
            {
                "chunk_id": "m1",
                "source_id": "src_m",
                "source_title": "Microeconomics",
                "section_title": "Market Demand",
                "page_number": 1,
                "content": (
                    "The law of demand states that higher prices reduce quantity demanded, holding income constant. "
                    "Price elasticity of demand measures percentage change in quantity divided by percentage change in price."
                ),
            },
            {
                "chunk_id": "m2",
                "source_id": "src_m",
                "source_title": "Microeconomics",
                "section_title": "Market Equilibrium",
                "page_number": 2,
                "content": (
                    "Supply curves slope upward because higher prices incentivize greater firm output. "
                    "Market equilibrium occurs where quantity supplied equals quantity demanded without shortage or surplus. "
                    "Comparing price ceilings versus price floors shows deadweight loss differences across interventions."
                ),
            },
        ]

        complex_chunks = [
            {
                "chunk_id": "c1",
                "source_id": "src_c",
                "source_title": "Comprehensive Photosynthesis",
                "section_title": "1. Organelle Architecture",
                "page_number": 1,
                "content": (
                    "Chloroplasts contain double outer membranes enclosing stacked thylakoid grana and fluid stroma. "
                    "Chlorophyll pigments embedded in photosystem II absorb photons at 680 nanometers."
                ),
            },
            {
                "chunk_id": "c2",
                "source_id": "src_c",
                "source_title": "Comprehensive Photosynthesis",
                "section_title": "2. Light Reactions Mechanism",
                "page_number": 2,
                "content": (
                    "Photolysis splits water molecules in the thylakoid lumen, releasing oxygen and protons; then plastoquinone and cytochrome b6f pump protons across the membrane; finally ATP synthase rotates to produce ATP. "
                    "Photosystem I re-energizes electrons to reduce NADP+ into NADPH in the stroma."
                ),
            },
            {
                "chunk_id": "c3",
                "source_id": "src_c",
                "source_title": "Comprehensive Photosynthesis",
                "section_title": "3. Calvin Cycle & Stoichiometry",
                "page_number": 3,
                "content": (
                    "Carbon fixation attaches CO2 to RuBP via the enzyme RuBisCO inside the stroma. "
                    "The overall photosynthetic stoichiometry equation 6CO2 + 6H2O = C6H12O6 + 6O2 summarizes net glucose synthesis. "
                    "Regeneration of RuBP consumes ATP so the Calvin cycle continues fixing carbon."
                ),
            },
            {
                "chunk_id": "c4",
                "source_id": "src_c",
                "source_title": "Comprehensive Photosynthesis",
                "section_title": "4. Evolution, Geography & Pathways",
                "page_number": 4,
                "content": (
                    "Comparing C3 versus C4 and CAM plants reveals distinct adaptations against photorespiration in arid climates. "
                    "Historically, Jan Ingenhousz in 1779 and Melvin Calvin in the 20th century mapped the timeline of carbon fixation. "
                    "Global spatial distribution maps show tropical C4 grasslands dominating warm high-irradiance regions."
                ),
            },
        ]

        sb_simple = generateVideoStoryboard(simple_chunks, {"topic": "Ohm's Law", "language": "English"}, {}, source_ids=["src_s"])
        sb_mod = generateVideoStoryboard(moderate_chunks, {"topic": "Supply & Demand", "language": "English"}, {}, source_ids=["src_m"])
        sb_comp = generateVideoStoryboard(complex_chunks, {"topic": "Photosynthesis Mastery", "language": "English"}, {}, source_ids=["src_c"])

        n_simple = len(sb_simple["scenes"])
        n_mod = len(sb_mod["scenes"])
        n_comp = len(sb_comp["scenes"])

        print(f"ADAPTIVE_SCENE_COUNTS: simple={n_simple}, moderate={n_mod}, complex={n_comp}")
        print("COMPLEX_METRICS:", json.dumps(sb_comp["planning_metrics"]))

        self.assertEqual(sb_simple["planning_metrics"]["complexity_tier"], "simple")
        self.assertEqual(sb_mod["planning_metrics"]["complexity_tier"], "moderate")
        self.assertEqual(sb_comp["planning_metrics"]["complexity_tier"], "complex")

        self.assertLess(n_simple, n_mod)
        self.assertLess(n_mod, n_comp)
        self.assertGreater(n_comp, 10, "Complex topic must exceed old 10-scene cap")
        self.assertEqual(sb_comp["planning_metrics"]["coverage_ratio"], 1.0)
        self.assertGreaterEqual(sb_comp["planning_metrics"]["mechanism_steps_decomposed"], 2)

        modes = {s["visual_mode"] for s in sb_comp["scenes"]}
        self.assertGreaterEqual(len(modes), 4, f"Expected diverse visual modes, got {modes}")
        self.assertIn("equation_derivation", modes)
        self.assertIn("comparison_matrix", modes)

    def test_02_render_12_scenes_all_visual_modes_and_narration_sync(self):
        from backend.video_engine import synthesize_educational_video

        visual_modes = [
            "biology_organelle",
            "cs_tree_algorithm",
            "economics_curve",
            "history_timeline",
            "equation_derivation",
            "comparison_matrix",
            "geo_concept_map",
            "diagram_flow",
            "biology_organelle",
            "equation_derivation",
            "comparison_matrix",
            "diagram_flow",
        ]
        scenes = []
        for i, vm in enumerate(visual_modes, start=1):
            # Vary spoken length intentionally to verify proportional narration duration sync
            words = " ".join([f"concept{i}"] * (8 if i % 2 == 1 else 28))
            scenes.append(
                {
                    "scene_number": i,
                    "title": f"Scene {i}: {vm}",
                    "visual_mode": vm,
                    "educational_objective": f"Demonstrate {vm}",
                    "source_citation": f"Source p.{i}",
                    "narration": f"Explaining {vm}: {words[:140]}",
                    "spoken_text": f"Explaining {vm}: {words}",
                    "on_screen_text": f"Mode: {vm}",
                    "key_points": [f"Point A for {vm}", f"Point B for {vm}"],
                    "diagram_nodes": [f"Node 1 ({vm})", "Node 2", "Node 3", "Node 4"],
                }
            )

        wav_file = self.tmp_path / "audio" / "c21_12scenes.wav"
        _write_silent_wav(wav_file, duration_sec=48.0)

        with patch(
            "backend.video_engine.synthesize_podcast_audio",
            return_value={"file_path": str(wav_file), "duration_seconds": 48, "voice_supported": True, "engine": "mock_wav"},
        ):
            meta = synthesize_educational_video(
                output_id="std_c21_12scenes",
                storyboard={"title": "12-Scene Adaptive Showcase", "scenes": scenes},
                language="English",
            )

        self.assertTrue(meta["video_ready"])
        self.assertEqual(meta["fps"], 24)
        self.assertEqual(meta["resolution"], "1920x1080")
        self.assertEqual(len(meta["slide_frames"]), 12, "All 12 scenes must be rendered without [:10] truncation")
        # Verify proportional duration sync (longer narration scenes get more seconds than short ones)
        durs = [f["duration_sec"] for f in meta["slide_frames"]]
        self.assertNotEqual(min(durs), max(durs), "Scene durations should track narration length, not be uniform")
        self.assertTrue(Path(meta["file_path"]).exists())
        print("RENDER_12SCENES_METRICS:", json.dumps(meta["render_metrics"]))

    def test_03_job_resumes_from_saved_storyboard_and_audio_checkpoint(self):
        import backend.database as db
        from backend.job_worker import execute_job_sync

        now = db.utc_now()
        uid = "usr_c21_resume"
        oid = "std_c21_resume"
        jid = "job_c21_resume"
        saved_wav = self.tmp_path / "audio" / "resumed_ckpt.wav"
        _write_silent_wav(saved_wav, duration_sec=8.0)

        saved_storyboard = {
            "title": "Resumable Adaptive Video",
            "language": "English",
            "scenes": [
                {
                    "scene_number": 1,
                    "title": "1. Saved Checkpoint Scene",
                    "visual_mode": "equation_derivation",
                    "educational_objective": "Verify resume checkpoint",
                    "source_citation": "Checkpoint p.1",
                    "narration": "Resuming rendering from saved storyboard and WAV audio checkpoint.",
                    "spoken_text": "Resuming rendering from saved storyboard and WAV audio checkpoint.",
                    "on_screen_text": "Resumed Checkpoint",
                    "key_points": ["Storyboard preserved", "WAV audio reused"],
                    "diagram_nodes": ["1. Saved Plan", "2. Saved WAV", "3. Resume Render", "4. Complete MP4"],
                },
                {
                    "scene_number": 2,
                    "title": "2. Verification Scene",
                    "visual_mode": "comparison_matrix",
                    "educational_objective": "Complete MP4 after retry",
                    "source_citation": "Checkpoint p.2",
                    "narration": "Completing the MP4 output without regenerating storyboard or TTS.",
                    "spoken_text": "Completing the MP4 output without regenerating storyboard or TTS.",
                    "on_screen_text": "MP4 Completed",
                    "key_points": ["No duplicate TTS", "MP4 validated"],
                    "diagram_nodes": ["Fresh Run", "Resumed Run", "Audio Reused", "Success"],
                },
            ],
        }

        with db.get_db(commit=True) as conn:
            conn.execute(
                "INSERT INTO users (id, name, email, password_hash, role, created_at, updated_at) VALUES (?, ?, ?, ?, 'student', ?, ?)",
                (uid, "Resume Tester", "resume@brainova.test", "hash", now, now),
            )
            conn.execute("INSERT INTO user_preferences (user_id, updated_at) VALUES (?, ?)", (uid, now))
            conn.execute(
                """
                INSERT INTO studio_outputs (
                    id, user_id, tool_type, title, source_ids_json, config_json,
                    content_json, audio_file_path, video_file_path, language, duration_label, style_label,
                    status, is_user_edited, error_message, created_at, updated_at
                ) VALUES (?, ?, 'video_overview', 'Resumable Adaptive Video', '[]', ?, ?, ?, '', 'English', 'Adaptive', 'Visual', 'failed', 0, 'Prior render interrupted', ?, ?)
                """,
                (oid, uid, json.dumps({"language": "English"}), json.dumps(saved_storyboard), str(saved_wav), now, now),
            )
            conn.execute(
                """
                INSERT INTO generation_jobs (
                    id, user_id, job_type, resource_type, roadmap_id, phase_id, topic_id,
                    studio_output_id, status, retry_count, max_retries, error_message, result_id,
                    created_at, started_at, completed_at
                ) VALUES (?, ?, 'studio_video', 'video_overview', NULL, NULL, NULL, ?, 'queued', 1, 3, 'Prior render interrupted', '', ?, '', '')
                """,
                (jid, uid, oid, now),
            )

        with patch("backend.job_worker.generateVideoStoryboard", side_effect=AssertionError("Should reuse saved storyboard!")), \
             patch("backend.video_engine.synthesize_podcast_audio", side_effect=AssertionError("Should reuse saved WAV checkpoint!")):
            res = execute_job_sync(jid)

        self.assertIsNotNone(res)
        self.assertEqual(res["status"], "completed", res.get("error_message"))
        with db.get_db() as conn:
            row = conn.execute("SELECT status, video_file_path FROM studio_outputs WHERE id = ?", (oid,)).fetchone()
        self.assertEqual(row["status"], "completed")
        self.assertTrue(Path(row["video_file_path"]).exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)

