import json
import os
import sys
import tempfile
import threading
import time
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def _write_silent_wav(path: Path, duration_sec: float, sample_rate: int = 16000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * int(duration_sec * sample_rate))


class TestVideoOverviewPerfAndRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp_dir = tempfile.TemporaryDirectory(prefix="brainova_perf_reg_")
        cls.tmp_path = Path(cls.tmp_dir.name)
        os.environ["AETHER_DB_PATH"] = str(cls.tmp_path / "perf_reg.db")

        import backend.database as db
        import backend.video_engine as ve

        db.DB_PATH = cls.tmp_path / "perf_reg.db"
        db.init_db()
        ve.VIDEOS_DIR = cls.tmp_path / "videos"
        ve.AUDIO_DIR = cls.tmp_path / "audio"
        ve.VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
        ve.AUDIO_DIR.mkdir(parents=True, exist_ok=True)

        now = db.utc_now()
        cls.uid = "usr_perf"
        with db.get_db(commit=True) as conn:
            conn.execute(
                "INSERT INTO users (id, name, email, password_hash, role, created_at, updated_at) VALUES (?, ?, ?, ?, 'student', ?, ?)",
                (cls.uid, "Perf Tester", "perf@brainova.test", "hash", now, now),
            )
            conn.execute("INSERT INTO user_preferences (user_id, updated_at) VALUES (?, ?)", (cls.uid, now))

    @classmethod
    def tearDownClass(cls):
        cls.tmp_dir.cleanup()

    def _enqueue(self, tag: str, topic: str, chunk_rows: list) -> tuple[str, str]:
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

    def test_01_benchmarks_2_12_37_56_scenes(self):
        import backend.database as db
        from backend.job_worker import execute_job_sync
        from backend.video_engine import validate_mp4_media_file

        cases = [
            (
                "b_2",
                "Ohm's Law",
                [("Basics", 1, "Ohm's law states that electrical current through a conductor is directly proportional to voltage. The fundamental equation V = I * R relates voltage, current, and resistance.")],
                8.0,
                2,
            ),
            (
                "b_12",
                "Photosynthesis Mastery",
                [
                    ("1. Structure", 1, "Chloroplasts contain double outer membranes enclosing stacked thylakoid grana and fluid stroma. Chlorophyll pigments in photosystem II absorb photons at 680 nanometers."),
                    ("2. Light Reactions", 2, "Photolysis splits water molecules in the thylakoid lumen, releasing oxygen and protons; then plastoquinone and cytochrome b6f pump protons across the membrane; finally ATP synthase rotates to produce ATP. Photosystem I reduces NADP+ into NADPH."),
                    ("3. Calvin Cycle", 3, "Carbon fixation attaches CO2 to RuBP via RuBisCO inside the stroma. The overall photosynthetic stoichiometry equation 6CO2 + 6H2O = C6H12O6 + 6O2 summarizes glucose synthesis. Regeneration of RuBP consumes ATP."),
                    ("4. Diversity", 4, "Comparing C3 versus C4 and CAM plants reveals adaptations against photorespiration. Historically, Ingenhousz in 1779 and Calvin in the 20th century mapped the timeline. Global distribution maps show C4 grasslands."),
                ],
                24.0,
                12,
            ),
            (
                "b_37",
                "Systems Engineering 37",
                [
                    (
                        f"Section {i}",
                        i,
                        f"ModuleAlpha{i} defines core principle {i} for distributed consensus. "
                        + (f"ModuleBeta{i} compares throughput versus latency in partition {i}." if i <= 18 else ""),
                    )
                    for i in range(1, 20)
                ],
                74.0,
                37,
            ),
            (
                "b_56",
                "Systems Textbook 56",
                [
                    (
                        f"Section {i}",
                        i,
                        f"ModFiftySix{i} defines principle {i} in quantitative analysis. "
                        f"ParamFiftySix{i} governs stability across distributed nodes.",
                    )
                    for i in range(1, 29)
                ],
                56.0,
                56,
            ),
        ]

        results = []
        for tag, topic, rows, wav_dur, expected_scenes in cases:
            oid, jid = self._enqueue(tag, topic, rows)
            wav_p = self.tmp_path / "audio" / f"{tag}.wav"
            _write_silent_wav(wav_p, duration_sec=wav_dur)
            t0 = time.perf_counter()
            with patch(
                "backend.video_engine.synthesize_podcast_audio",
                return_value={"file_path": str(wav_p), "duration_seconds": int(wav_dur), "voice_supported": True, "engine": "mock"},
            ):
                res = execute_job_sync(jid)
            elapsed = round(time.perf_counter() - t0, 2)
            self.assertEqual(res["status"], "completed", res.get("error_message"))

            with db.get_db() as conn:
                row = conn.execute("SELECT content_json, video_file_path FROM studio_outputs WHERE id = ?", (oid,)).fetchone()
            c = json.loads(row["content_json"])
            mp4_path = row["video_file_path"]
            val = validate_mp4_media_file(mp4_path)
            self.assertTrue(val["valid"], val)
            self.assertEqual(len(c["scenes"]), expected_scenes)
            self.assertEqual(c["video"]["fps"], 24)
            self.assertEqual(c["video"]["resolution"], "1920x1080")
            results.append({
                "case": tag,
                "scenes": len(c["scenes"]),
                "total_sec": elapsed,
                "render_metrics": c["video"]["render_metrics"],
                "mp4_duration": val["duration_seconds"],
                "size_bytes": os.path.getsize(mp4_path),
            })
        print("BENCHMARK_SUMMARY:", json.dumps(results))

    def test_02_concurrent_jobs_and_failure_modes(self):
        import backend.database as db
        from backend.job_worker import execute_job_sync
        from backend.video_engine import validate_mp4_media_file

        # 1. Corrupt / incomplete MP4 rejected by validator
        bad_mp4 = self.tmp_path / "videos" / "corrupt.mp4"
        bad_mp4.write_bytes(b"not-a-valid-mp4-container")
        bad_val = validate_mp4_media_file(str(bad_mp4))
        self.assertFalse(bad_val["valid"])

        # 2. Missing audio / unsupported voice fails cleanly without marking completed
        oid_noaud, jid_noaud = self._enqueue("noaud", "Missing Audio", [("S1", 1, "Concept one defines voltage. Concept two defines current.")])
        with patch(
            "backend.video_engine.synthesize_podcast_audio",
            return_value={"file_path": "", "voice_supported": False, "error": "No native voice"},
        ):
            res_noaud = execute_job_sync(jid_noaud)
        self.assertEqual(res_noaud["status"], "failed")
        with db.get_db() as conn:
            r = conn.execute("SELECT status, video_file_path FROM studio_outputs WHERE id = ?", (oid_noaud,)).fetchone()
        self.assertEqual(r["status"], "failed")
        self.assertEqual(r["video_file_path"], "")

        # 3. Encoder subprocess failure fails cleanly
        oid_encfail, jid_encfail = self._enqueue("encfail", "Encoder Failure", [("S1", 1, "Concept A explains heat. Concept B explains work.")])
        wav_ef = self.tmp_path / "audio" / "ef.wav"
        _write_silent_wav(wav_ef, 8.0)
        with patch("backend.video_engine.synthesize_podcast_audio", return_value={"file_path": str(wav_ef), "duration_seconds": 8, "voice_supported": True}), \
             patch("backend.video_engine.subprocess.Popen", side_effect=RuntimeError("Simulated encoder crash")):
            res_ef = execute_job_sync(jid_encfail)
        self.assertEqual(res_ef["status"], "failed")

        # 4. Two concurrent generation jobs complete independently without corrupting each other
        oid1, jid1 = self._enqueue("conc1", "Concurrent One", [("S1", 1, "Alpha concept explains hashing. Beta concept explains trees.")])
        oid2, jid2 = self._enqueue("conc2", "Concurrent Two", [("S1", 1, "Gamma concept explains queues. Delta concept explains stacks.")])
        wav1 = self.tmp_path / "audio" / "conc1.wav"
        wav2 = self.tmp_path / "audio" / "conc2.wav"
        _write_silent_wav(wav1, 8.0)
        _write_silent_wav(wav2, 8.0)

        def _mock_tts(output_id, **kw):
            p = wav1 if "conc1" in output_id else wav2
            return {"file_path": str(p), "duration_seconds": 8, "voice_supported": True, "engine": "mock"}

        out_map = {}
        with patch("backend.video_engine.synthesize_podcast_audio", side_effect=_mock_tts):
            t1 = threading.Thread(target=lambda: out_map.__setitem__(jid1, execute_job_sync(jid1)))
            t2 = threading.Thread(target=lambda: out_map.__setitem__(jid2, execute_job_sync(jid2)))
            t1.start(); t2.start()
            t1.join(); t2.join()

        self.assertEqual(out_map[jid1]["status"], "completed")
        self.assertEqual(out_map[jid2]["status"], "completed")


if __name__ == "__main__":
    unittest.main(verbosity=2)

