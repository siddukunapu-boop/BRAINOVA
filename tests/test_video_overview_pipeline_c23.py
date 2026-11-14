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


class TestVideoOverviewPipelineCycle23(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp_dir = tempfile.TemporaryDirectory(prefix="brainova_c23_test_")
        cls.tmp_path = Path(cls.tmp_dir.name)
        os.environ["AETHER_DB_PATH"] = str(cls.tmp_path / "test_c23.db")

        import backend.database as db
        import backend.video_engine as ve

        db.DB_PATH = cls.tmp_path / "test_c23.db"
        db.init_db()
        ve.VIDEOS_DIR = cls.tmp_path / "videos"
        ve.AUDIO_DIR = cls.tmp_path / "audio"
        ve.VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
        ve.AUDIO_DIR.mkdir(parents=True, exist_ok=True)

        now = db.utc_now()
        cls.uid = "usr_c23"
        with db.get_db(commit=True) as conn:
            conn.execute(
                "INSERT INTO users (id, name, email, password_hash, role, created_at, updated_at) VALUES (?, ?, ?, ?, 'student', ?, ?)",
                (cls.uid, "Pipeline Tester", "c23@brainova.test", "hash", now, now),
            )
            conn.execute("INSERT INTO user_preferences (user_id, updated_at) VALUES (?, ?)", (cls.uid, now))

    @classmethod
    def tearDownClass(cls):
        cls.tmp_dir.cleanup()

    def _enqueue_video_job(self, tag: str, topic: str, chunk_rows: list) -> tuple[str, str]:
        import backend.database as db

        now = db.utc_now()
        src_id = f"src_{tag}"
        oid = f"std_{tag}"
        jid = f"job_{tag}"
        with db.get_db(commit=True) as conn:
            conn.execute(
                "INSERT INTO sources (id, user_id, title, original_filename, file_path, file_type, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, 'notes', 'ready', ?, ?)",
                (src_id, self.uid, topic, f"{tag}.txt", str(self.tmp_path / f"{tag}.txt"), now, now),
            )
            for idx, (sec, pg, txt) in enumerate(chunk_rows):
                conn.execute(
                    "INSERT INTO source_chunks (id, source_id, user_id, chunk_index, page_number, section_title, content) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (f"chk_{tag}_{idx}", src_id, self.uid, idx, pg, sec, txt),
                )
            conn.execute(
                """
                INSERT INTO studio_outputs (
                    id, user_id, tool_type, title, source_ids_json, config_json,
                    content_json, audio_file_path, video_file_path, language, duration_label, style_label,
                    status, is_user_edited, error_message, created_at, updated_at
                ) VALUES (?, ?, 'video_overview', ?, ?, ?, ?, '', '', 'English', 'Adaptive', 'Visual', 'queued', 0, '', ?, ?)
                """,
                (oid, self.uid, topic, json.dumps([src_id]), json.dumps({"language": "English", "topic": topic}), json.dumps({"video": {"ready": False, "progress": 5}}), now, now),
            )
            conn.execute(
                """
                INSERT INTO generation_jobs (
                    id, user_id, job_type, resource_type, roadmap_id, phase_id, topic_id,
                    studio_output_id, status, retry_count, max_retries, error_message, result_id,
                    created_at, started_at, completed_at
                ) VALUES (?, ?, 'studio_video', 'video_overview', NULL, NULL, NULL, ?, 'queued', 0, 3, '', '', ?, '', '')
                """,
                (jid, self.uid, oid, now),
            )
        return oid, jid

    def test_01_simple_2_scene_and_complex_12_scene_pipeline(self):
        import backend.database as db
        from backend.job_worker import execute_job_sync

        oid_s, jid_s = self._enqueue_video_job(
            "simple2",
            "Ohm's Law",
            [
                (
                    "Basics",
                    1,
                    "Ohm's law states that electrical current through a conductor is directly proportional to voltage. "
                    "The fundamental equation V = I * R relates voltage, current, and resistance in linear circuits.",
                )
            ],
        )
        wav_s = self.tmp_path / "audio" / "simple2.wav"
        _write_silent_wav(wav_s, duration_sec=8.0)
        with patch(
            "backend.video_engine.synthesize_podcast_audio",
            return_value={"file_path": str(wav_s), "duration_seconds": 8, "voice_supported": True, "engine": "mock"},
        ):
            res_s = execute_job_sync(jid_s)
        self.assertEqual(res_s["status"], "completed", res_s.get("error_message"))

        with db.get_db() as conn:
            row_s = conn.execute("SELECT status, content_json, video_file_path FROM studio_outputs WHERE id = ?", (oid_s,)).fetchone()
        cs = json.loads(row_s["content_json"])
        self.assertEqual(len(cs["scenes"]), 2)
        self.assertEqual([s["scene_number"] for s in cs["scenes"]], [1, 2])
        self.assertTrue(Path(row_s["video_file_path"]).exists())

        oid_c, jid_c = self._enqueue_video_job(
            "complex12",
            "Photosynthesis Mastery",
            [
                ("1. Structure", 1, "Chloroplasts contain double outer membranes enclosing stacked thylakoid grana and fluid stroma. Chlorophyll pigments embedded in photosystem II absorb photons at 680 nanometers."),
                ("2. Light Reactions", 2, "Photolysis splits water molecules in the thylakoid lumen, releasing oxygen and protons; then plastoquinone and cytochrome b6f pump protons across the membrane; finally ATP synthase rotates to produce ATP. Photosystem I re-energizes electrons to reduce NADP+ into NADPH in the stroma."),
                ("3. Calvin Cycle", 3, "Carbon fixation attaches CO2 to RuBP via the enzyme RuBisCO inside the stroma. The overall photosynthetic stoichiometry equation 6CO2 + 6H2O = C6H12O6 + 6O2 summarizes net glucose synthesis. Regeneration of RuBP consumes ATP so the Calvin cycle continues fixing carbon."),
                ("4. Diversity", 4, "Comparing C3 versus C4 and CAM plants reveals distinct adaptations against photorespiration in arid climates. Historically, Jan Ingenhousz in 1779 and Melvin Calvin in the 20th century mapped the timeline of carbon fixation. Global spatial distribution maps show tropical C4 grasslands dominating warm high-irradiance regions."),
            ],
        )
        wav_c = self.tmp_path / "audio" / "complex12.wav"
        _write_silent_wav(wav_c, duration_sec=48.0)
        with patch(
            "backend.video_engine.synthesize_podcast_audio",
            return_value={"file_path": str(wav_c), "duration_seconds": 48, "voice_supported": True, "engine": "mock"},
        ):
            res_c = execute_job_sync(jid_c)
        self.assertEqual(res_c["status"], "completed", res_c.get("error_message"))

        with db.get_db() as conn:
            row_c = conn.execute("SELECT status, content_json, video_file_path FROM studio_outputs WHERE id = ?", (oid_c,)).fetchone()
        cc = json.loads(row_c["content_json"])
        self.assertEqual(len(cc["scenes"]), 12)
        self.assertEqual([s["scene_number"] for s in cc["scenes"]], list(range(1, 13)))
        self.assertEqual(len(cc["video"]["slide_frames"]), 12)
        self.assertTrue(Path(row_c["video_file_path"]).exists())

    def test_02_56_scene_three_batch_automatic_orchestration(self):
        import backend.database as db
        from backend.job_worker import execute_job_sync

        mega_rows = [
            (
                f"Section {i}",
                i,
                f"Module{i}Token defines principle number {i} in quantitative systems analysis. "
                f"It governs stability parameter alpha{i} across distributed workloads.",
            )
            for i in range(1, 29)
        ]
        oid, jid = self._enqueue_video_job("mega56", "Comprehensive Systems Textbook", mega_rows)
        wav_56 = self.tmp_path / "audio" / "mega56.wav"
        _write_silent_wav(wav_56, duration_sec=56.0)

        with patch(
            "backend.video_engine.synthesize_podcast_audio",
            return_value={"file_path": str(wav_56), "duration_seconds": 56, "voice_supported": True, "engine": "mock"},
        ):
            res = execute_job_sync(jid)

        self.assertEqual(res["status"], "completed", res.get("error_message"))
        with db.get_db() as conn:
            row = conn.execute("SELECT status, content_json, video_file_path FROM studio_outputs WHERE id = ?", (oid,)).fetchone()
        self.assertEqual(row["status"], "completed")
        self.assertTrue(Path(row["video_file_path"]).exists())

        content = json.loads(row["content_json"])
        self.assertEqual(content["completed_batch_offsets"], [0, 24, 48])
        self.assertFalse(content["has_more_batches"])
        self.assertTrue(content["storyboard_complete"])
        self.assertEqual(len(content["scenes"]), 56)
        self.assertEqual([s["scene_number"] for s in content["scenes"]], list(range(1, 57)))
        self.assertEqual(content["planning_metrics"]["coverage_ratio"], 1.0)
        self.assertTrue(content["video"]["video_ready"])
        self.assertEqual(len(content["video"]["slide_frames"]), 56)
        self.assertGreaterEqual(content["video"]["duration_seconds"], 55)
        print("MEGA56_METRICS:", json.dumps(content["video"]["render_metrics"]))

    def test_03_interrupted_resume_and_duplicate_prevention(self):
        import backend.database as db
        from backend.ai_engine import generateVideoStoryboard
        from backend.job_worker import execute_job_sync

        mega_rows = [
            (
                f"Section {i}",
                i,
                f"ResumeMod{i}Token defines principle number {i} in quantitative systems analysis. "
                f"It governs stability parameter beta{i} across distributed workloads.",
            )
            for i in range(1, 29)
        ]
        oid, jid = self._enqueue_video_job("resume56", "Resumable Systems Textbook", mega_rows)

        # Simulate Batch 1 already completed + WAV audio checkpoint already synthesized before interruption
        with db.get_db() as conn:
            from backend.doc_processor import retrieve_relevant_chunks
            chunks = retrieve_relevant_chunks(conn, self.uid, [f"src_resume56"], "Resumable Systems Textbook", top_k=60)
        batch1 = generateVideoStoryboard(chunks, {"language": "English", "topic": "Resumable Systems Textbook", "batch_offset": 0}, {}, source_ids=["src_resume56"])
        for idx, sc in enumerate(batch1["scenes"], start=1):
            sc["global_scene_number"] = idx
            sc["scene_number"] = idx

        saved_wav = self.tmp_path / "audio" / "resume56.wav"
        _write_silent_wav(saved_wav, duration_sec=56.0)

        interrupted_content = {
            **batch1,
            "completed_batch_offsets": [0],
            "has_more_batches": True,
            "next_batch_offset": 24,
            "storyboard_complete": False,
        }
        with db.get_db(commit=True) as conn:
            conn.execute(
                "UPDATE studio_outputs SET status = 'failed', content_json = ?, audio_file_path = ?, error_message = 'Simulated power loss' WHERE id = ?",
                (json.dumps(interrupted_content), str(saved_wav), oid),
            )
            conn.execute("UPDATE generation_jobs SET status = 'queued', retry_count = 1 WHERE id = ?", (jid,))

        seen_offsets = []
        orig_gen = generateVideoStoryboard

        def _spy_gen(ch, cfg, **kw):
            off = int(cfg.get("batch_offset") or 0)
            seen_offsets.append(off)
            if off == 0:
                raise AssertionError("Duplicate batch_offset=0 should NOT be regenerated on resume!")
            return orig_gen(ch, cfg, **kw)

        with patch("backend.job_worker.generateVideoStoryboard", side_effect=_spy_gen), \
             patch("backend.video_engine.synthesize_podcast_audio", side_effect=AssertionError("Should reuse saved WAV checkpoint!")):
            res = execute_job_sync(jid)

        self.assertEqual(res["status"], "completed", res.get("error_message"))
        self.assertEqual(seen_offsets, [24, 48])

        with db.get_db() as conn:
            row = conn.execute("SELECT status, content_json, video_file_path FROM studio_outputs WHERE id = ?", (oid,)).fetchone()
        c = json.loads(row["content_json"])
        self.assertEqual(c["completed_batch_offsets"], [0, 24, 48])
        self.assertEqual(len(c["scenes"]), 56)
        self.assertEqual([s["scene_number"] for s in c["scenes"]], list(range(1, 57)))
        self.assertTrue(Path(row["video_file_path"]).exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)

