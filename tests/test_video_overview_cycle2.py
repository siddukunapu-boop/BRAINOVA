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


def _write_silent_wav(path: Path, duration_sec: float = 8.0, sample_rate: int = 16000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    n_frames = int(duration_sec * sample_rate)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * n_frames)


class TestVideoOverviewCycle2(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp_dir = tempfile.TemporaryDirectory(prefix="brainova_c2_test_")
        cls.tmp_path = Path(cls.tmp_dir.name)
        os.environ["AETHER_DB_PATH"] = str(cls.tmp_path / "test_cycle2.db")

        import backend.database as db
        import backend.video_engine as ve

        db.DB_PATH = cls.tmp_path / "test_cycle2.db"
        db.init_db()
        ve.VIDEOS_DIR = cls.tmp_path / "videos"
        ve.AUDIO_DIR = cls.tmp_path / "audio"
        ve.VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
        ve.AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp_dir.cleanup()

    def test_01_multidomain_storyboard_and_visual_modes(self):
        from backend.ai_engine import generateVideoStoryboard

        domains = [
            (
                "biology_organelle",
                "Photosynthesis in Chloroplasts",
                "Chloroplasts convert solar energy into chemical energy. Light-dependent reactions occur on thylakoid membranes, generating ATP and NADPH. The Calvin cycle in the stroma fixes CO2 via RuBisCO.",
            ),
            (
                "cs_tree_algorithm",
                "B-Tree Indexing and Node Splitting",
                "A B-tree of order m keeps keys sorted inside internal nodes and leaf blocks. Key insertion locates the target leaf via binary search across separators. When a leaf overflows its capacity, node splitting promotes the median key to the parent node. Balanced tree height guarantees logarithmic lookup performance for database indexes.",
            ),
            (
                "economics_curve",
                "Supply and Demand Equilibrium",
                "Market equilibrium occurs where the downward-sloping demand curve intersects the upward-sloping supply curve. Price elasticity measures how sharply quantity demanded responds to price changes. A rightward shift in supply lowers equilibrium price while increasing total quantity traded. Excess demand above equilibrium creates upward pressure until markets clear.",
            ),
            (
                "history_timeline",
                "Industrial Revolution Timeline",
                "Beginning in Britain around 1760, mechanization transformed textile manufacturing and cottage industry. In 1776 James Watt's improved steam engine unlocked continuous factory power away from rivers. By 1830 the Liverpool and Manchester Railway connected industrial cities with steam locomotion. Urbanization reshaped labor, trade, and economic growth across Europe.",
            ),
        ]

        for expected_mode, title, text in domains:
            chunks = [{"chunk_id": f"chk_{expected_mode}", "source_id": "src_1", "source_title": title, "content": text}]
            sb = generateVideoStoryboard(
                chunks,
                {"topic": title, "language": "English", "duration": "3-5 minutes"},
                user_prefs={},
                source_ids=["src_1"],
            )
            scenes = sb.get("scenes") or []
            self.assertGreaterEqual(len(scenes), 2, f"Expected >=2 scenes for {expected_mode}")
            modes = {s.get("visual_mode") for s in scenes}
            self.assertIn(expected_mode, modes, f"Expected visual_mode {expected_mode} in {modes}")
            for sc in scenes:
                self.assertTrue(sc.get("educational_objective"))
                self.assertTrue(sc.get("spoken_text"))
                self.assertTrue(sc.get("source_citation"))

    def test_02_multilingual_strict_no_silent_fallback(self):
        from backend.ai_engine import generateVideoStoryboard
        from backend.studio_engine import StudioGenerationError
        from backend.video_engine import synthesize_educational_video

        chunks = [
            {
                "chunk_id": "chk_bio",
                "source_id": "src_bio",
                "source_title": "Photosynthesis",
                "content": "Chloroplasts absorb light in thylakoid membranes to produce ATP and NADPH for the Calvin cycle.",
            }
        ]
        for lang in ("Telugu", "Hindi", "Tamil", "Kannada", "Marathi"):
            with self.assertRaises(StudioGenerationError) as ctx:
                generateVideoStoryboard(
                    chunks,
                    {"topic": "Photosynthesis", "language": lang},
                    user_prefs={},
                    source_ids=["src_bio"],
                )
            self.assertEqual(ctx.exception.status_code, 422)
            self.assertEqual(ctx.exception.code, "llm_required_for_language")

        # Mocked LLM returns genuine Telugu storyboard
        mocked_telugu = {
            "title": "కిరణజన్య సంయోగక్రియ",
            "overview": "క్లోరోప్లాస్ట్‌లో కాంతి చర్యలు మరియు కాల్విన్ వలయం.",
            "scenes": [
                {
                    "scene_number": 1,
                    "title": "థైలకాయిడ్ కాంతి చర్య",
                    "visual_mode": "biology_organelle",
                    "educational_objective": "కాంతి శక్తి ATP గా మారడం",
                    "spoken_text": "క్లోరోప్లాస్ట్‌లోని థైలకాయిడ్ పొరలు కాంతిని గ్రహించి ATP మరియు NADPH ఉత్పత్తి చేస్తాయి.",
                    "narration": "క్లోరోప్లాస్ట్‌లోని థైలకాయిడ్ పొరలు కాంతిని గ్రహించి ATP మరియు NADPH ఉత్పత్తి చేస్తాయి.",
                    "key_points": ["థైలకాయిడ్ పొరలు", "ATP మరియు NADPH", "కాల్విన్ వలయం"],
                    "visual_prompt": "3D chloroplast cutaway",
                    "source_citation": "Photosynthesis",
                    "duration_seconds": 12,
                }
                for _ in range(4)
            ],
        }
        with patch("backend.ai_engine.call_llm_json", return_value=(mocked_telugu, "gemini")):
            sb_te = generateVideoStoryboard(
                chunks,
                {"topic": "Photosynthesis", "language": "Telugu"},
                user_prefs={"gemini_api_key": "mock-key"},
                source_ids=["src_bio"],
            )
        self.assertEqual(sb_te["language"], "Telugu")
        self.assertIn("థైలకాయిడ్", sb_te["scenes"][0]["spoken_text"])

        # Strict native voice check: when voice_supported=False, must raise RuntimeError (no English fallback)
        fake_wav = self.tmp_path / "audio" / "unsupported.wav"
        _write_silent_wav(fake_wav, duration_sec=4.0)
        with patch(
            "backend.video_engine.synthesize_podcast_audio",
            return_value={"file_path": str(fake_wav), "voice_supported": False, "engine": "unavailable"},
        ):
            with self.assertRaises(RuntimeError):
                synthesize_educational_video(
                    output_id="std_te_fail",
                    storyboard=sb_te,
                    language="Telugu",
                )

    def test_03_24fps_1080p_mp4_biology_and_cs_render(self):
        from backend.ai_engine import generateVideoStoryboard
        from backend.video_engine import synthesize_educational_video

        bio_chunks = [
            {
                "chunk_id": "c1",
                "source_id": "s1",
                "source_title": "Cell Biology",
                "content": "Chloroplasts have double membranes, stacked thylakoid grana, and stroma. Photosystem II and I drive electron transport to synthesize ATP and NADPH for the Calvin cycle.",
            }
        ]
        bio_sb = generateVideoStoryboard(
            bio_chunks, {"topic": "Chloroplast Photosynthesis", "language": "English"}, user_prefs={}, source_ids=["s1"]
        )
        bio_wav = self.tmp_path / "audio" / "bio_8s.wav"
        _write_silent_wav(bio_wav, duration_sec=8.0)

        with patch(
            "backend.video_engine.synthesize_podcast_audio",
            return_value={"file_path": str(bio_wav), "voice_supported": True, "engine": "mock_wav"},
        ):
            meta = synthesize_educational_video(
                output_id="std_bio_24fps",
                storyboard=bio_sb,
                language="English",
            )

        self.assertTrue(meta["video_ready"])
        self.assertEqual(meta["fps"], 24)
        self.assertEqual(meta["resolution"], "1920x1080")
        self.assertEqual(meta["video_codec"], "avc1")
        self.assertEqual(meta["audio_codec"], "mp4a")
        self.assertTrue(Path(meta["file_path"]).exists())
        self.assertGreater(Path(meta["file_path"]).stat().st_size, 100_000)
        print("BIO_24FPS_METRICS:", json.dumps(meta.get("render_metrics", {})))

    def test_04_async_studio_video_job_success_and_failure(self):
        import backend.database as db
        from backend.job_worker import execute_job_sync

        now = db.utc_now()
        uid = "usr_c2_async"
        src_id = "src_c2_async"
        out_ok = "std_c2_ok"
        job_ok = "job_c2_ok"
        out_fail = "std_c2_fail"
        job_fail = "job_c2_fail"

        with db.get_db(commit=True) as conn:
            conn.execute(
                "INSERT INTO users (id, name, email, password_hash, role, created_at, updated_at) VALUES (?, ?, ?, ?, 'student', ?, ?)",
                (uid, "Cycle2 Tester", "c2@brainova.test", "hash", now, now),
            )
            conn.execute(
                "INSERT INTO user_preferences (user_id, updated_at) VALUES (?, ?)",
                (uid, now),
            )
            conn.execute(
                "INSERT INTO sources (id, user_id, title, original_filename, file_path, file_type, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, 'notes', 'ready', ?, ?)",
                (src_id, uid, "B-Tree Lecture", "btree.txt", str(self.tmp_path / "btree.txt"), now, now),
            )
            conn.execute(
                "INSERT INTO source_chunks (id, source_id, user_id, chunk_index, content) VALUES (?, ?, ?, 0, ?)",
                (
                    "chk_c2_1",
                    src_id,
                    uid,
                    "A B-tree stores sorted keys inside multi-way nodes to minimize disk reads. Key insertion traverses from root to leaf and splits overflowing nodes by promoting the median key. Balanced search paths ensure O(log n) lookups across large datasets.",
                ),
            )
            for oid, jid, lang in ((out_ok, job_ok, "English"), (out_fail, job_fail, "Telugu")):
                conn.execute(
                    """
                    INSERT INTO studio_outputs (
                        id, user_id, tool_type, title, source_ids_json, config_json,
                        content_json, audio_file_path, video_file_path, language, duration_label, style_label,
                        status, is_user_edited, error_message, created_at, updated_at
                    ) VALUES (?, ?, 'video_overview', ?, ?, ?, ?, '', '', ?, '3-5 minutes', 'Concept Breakdown', 'queued', 0, '', ?, ?)
                    """,
                    (oid, uid, f"B-Tree ({lang})", json.dumps([src_id]), json.dumps({"language": lang, "topic": "B-Tree"}), json.dumps({"video": {"ready": False, "progress": 5}}), lang, now, now),
                )
                conn.execute(
                    """
                    INSERT INTO generation_jobs (
                        id, user_id, job_type, resource_type, roadmap_id, phase_id, topic_id,
                        studio_output_id, status, retry_count, max_retries, error_message, result_id,
                        created_at, started_at, completed_at
                    ) VALUES (?, ?, 'studio_video', 'video_overview', NULL, NULL, NULL, ?, 'queued', 0, 3, '', '', ?, '', '')
                    """,
                    (jid, uid, oid, now),
                )

        cs_wav = self.tmp_path / "audio" / "cs_6s.wav"
        _write_silent_wav(cs_wav, duration_sec=6.0)
        with patch(
            "backend.video_engine.synthesize_podcast_audio",
            return_value={"file_path": str(cs_wav), "voice_supported": True, "engine": "mock_wav"},
        ):
            res_ok = execute_job_sync(job_ok)

        self.assertIsNotNone(res_ok)
        self.assertEqual(res_ok["status"], "completed", res_ok.get("error_message"))
        self.assertEqual(res_ok["result_id"], out_ok)

        res_fail = execute_job_sync(job_fail)
        self.assertIsNotNone(res_fail)
        self.assertEqual(res_fail["status"], "failed")
        self.assertEqual(res_fail["retry_count"], 1)
        self.assertTrue(len(res_fail["error_message"]) > 5)

        with db.get_db() as conn:
            row_ok = conn.execute("SELECT status, video_file_path FROM studio_outputs WHERE id = ?", (out_ok,)).fetchone()
            row_fail = conn.execute("SELECT status, error_message FROM studio_outputs WHERE id = ?", (out_fail,)).fetchone()
        self.assertEqual(row_ok["status"], "completed")
        self.assertTrue(Path(row_ok["video_file_path"]).exists())
        self.assertEqual(row_fail["status"], "failed")
        self.assertTrue(len(row_fail["error_message"]) > 5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
