import asyncio
import importlib
import json
import os
import tempfile
import unittest
from unittest.mock import patch

import httpx


class TestRenderStorageAndHealth(unittest.TestCase):
    def test_default_local_data_dir_unchanged(self):
        import backend.database as db

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("BRAINOVA_DATA_DIR", None)
            os.environ.pop("AETHER_DB_PATH", None)
            reloaded = importlib.reload(db)
            expected_data_dir = os.path.join(reloaded.BASE_DIR, "data")
            self.assertEqual(reloaded.resolve_data_dir(), expected_data_dir)
            self.assertEqual(reloaded.DATA_DIR, expected_data_dir)
            self.assertEqual(reloaded.UPLOADS_DIR, os.path.join(expected_data_dir, "uploads"))
            self.assertEqual(reloaded.AUDIO_DIR, os.path.join(expected_data_dir, "audio"))
            self.assertEqual(reloaded.VIDEOS_DIR, os.path.join(expected_data_dir, "videos"))
            self.assertEqual(reloaded.MENTOR_IMAGES_DIR, os.path.join(expected_data_dir, "mentor_images"))
            self.assertEqual(reloaded.get_db_path(), os.path.join(expected_data_dir, "aetherlearn.db"))

    def test_brainova_data_dir_overrides_and_creates_directories(self):
        import backend.database as db

        with tempfile.TemporaryDirectory() as tmpdir:
            custom_root = os.path.join(tmpdir, "persistent_disk")
            with patch.dict(os.environ, {"BRAINOVA_DATA_DIR": custom_root}, clear=False):
                os.environ.pop("AETHER_DB_PATH", None)
                reloaded = importlib.reload(db)
                self.assertEqual(reloaded.DATA_DIR, os.path.abspath(custom_root))
                self.assertEqual(reloaded.UPLOADS_DIR, os.path.join(os.path.abspath(custom_root), "uploads"))
                self.assertEqual(reloaded.AUDIO_DIR, os.path.join(os.path.abspath(custom_root), "audio"))
                self.assertEqual(reloaded.VIDEOS_DIR, os.path.join(os.path.abspath(custom_root), "videos"))
                self.assertEqual(
                    reloaded.MENTOR_IMAGES_DIR,
                    os.path.join(os.path.abspath(custom_root), "mentor_images"),
                )
                self.assertEqual(
                    reloaded.get_db_path(),
                    os.path.join(os.path.abspath(custom_root), "aetherlearn.db"),
                )
                for path in (
                    reloaded.DATA_DIR,
                    reloaded.UPLOADS_DIR,
                    reloaded.AUDIO_DIR,
                    reloaded.VIDEOS_DIR,
                    reloaded.MENTOR_IMAGES_DIR,
                ):
                    self.assertTrue(os.path.isdir(path), f"Expected directory to exist: {path}")

        # Restore module state for subsequent tests
        importlib.reload(db)

    def test_explicit_aether_db_path_precedence_and_parent_creation(self):
        import backend.database as db

        with tempfile.TemporaryDirectory() as tmpdir:
            custom_root = os.path.join(tmpdir, "disk_root")
            explicit_db = os.path.join(tmpdir, "nested", "db_dir", "custom.db")
            with patch.dict(
                os.environ,
                {"BRAINOVA_DATA_DIR": custom_root, "AETHER_DB_PATH": explicit_db},
                clear=False,
            ):
                reloaded = importlib.reload(db)
                self.assertEqual(reloaded.DATA_DIR, os.path.abspath(custom_root))
                self.assertEqual(reloaded.get_db_path(), os.path.abspath(explicit_db))
                with reloaded.get_db(commit=False) as conn:
                    row = conn.execute("SELECT 1 AS ok").fetchone()
                    self.assertEqual(row["ok"], 1)
                self.assertTrue(os.path.isdir(os.path.dirname(explicit_db)))

        importlib.reload(db)

    def test_render_var_data_resolution(self):
        import backend.database as db

        created = []
        with patch("os.makedirs", side_effect=lambda p, exist_ok=False: created.append(p)):
            with patch.dict(
                os.environ,
                {
                    "BRAINOVA_DATA_DIR": "/var/data",
                    "AETHER_DB_PATH": "/var/data/aetherlearn.db",
                },
                clear=False,
            ):
                reloaded = importlib.reload(db)
                expected_root = os.path.abspath("/var/data")
                self.assertEqual(reloaded.DATA_DIR, expected_root)
                self.assertEqual(reloaded.UPLOADS_DIR, os.path.join(expected_root, "uploads"))
                self.assertEqual(reloaded.AUDIO_DIR, os.path.join(expected_root, "audio"))
                self.assertEqual(reloaded.VIDEOS_DIR, os.path.join(expected_root, "videos"))
                self.assertEqual(reloaded.MENTOR_IMAGES_DIR, os.path.join(expected_root, "mentor_images"))
                self.assertEqual(reloaded.get_db_path(), os.path.abspath("/var/data/aetherlearn.db"))
                self.assertIn(expected_root, created)
                self.assertIn(reloaded.UPLOADS_DIR, created)
                self.assertIn(reloaded.AUDIO_DIR, created)
                self.assertIn(reloaded.VIDEOS_DIR, created)
                self.assertIn(reloaded.MENTOR_IMAGES_DIR, created)

        importlib.reload(db)

    def test_health_endpoint_healthy_and_unhealthy(self):
        import backend.main as main_mod

        fd, test_db = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            with patch.dict(
                os.environ,
                {"AETHER_DB_PATH": test_db, "BRAINOVA_DISABLE_SCHEDULER": "1"},
                clear=False,
            ):
                resp = main_mod.health_check()
                self.assertEqual(resp.status_code, 200)
                self.assertEqual(json.loads(resp.body.decode("utf-8")), {"status": "ok", "database": "ok"})

                with patch.object(main_mod, "get_db", side_effect=RuntimeError("secret_internal_path /var/data/db")):
                    bad_resp = main_mod.health_check()
                self.assertEqual(bad_resp.status_code, 503)
                raw_text = bad_resp.body.decode("utf-8")
                body = json.loads(raw_text)
                self.assertEqual(body, {"status": "unhealthy", "database": "unavailable"})
                self.assertNotIn("secret_internal_path", raw_text)
                self.assertNotIn("/var/data", raw_text)
        finally:
            for suffix in ("", "-wal", "-shm"):
                p = test_db + suffix
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except OSError:
                        pass

    def test_cors_reads_aether_cors_origins_and_preserves_default(self):
        import backend.main as main_mod

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AETHER_CORS_ORIGINS", None)
            defaults = main_mod.get_cors_origins()
            self.assertIn("http://127.0.0.1:8000", defaults)
            self.assertIn("http://localhost:5173", defaults)

        with patch.dict(
            os.environ,
            {"AETHER_CORS_ORIGINS": "https://brainova-os.vercel.app/, https://app.brainova.ai"},
            clear=False,
        ):
            custom = main_mod.get_cors_origins()
            self.assertEqual(custom, ["https://brainova-os.vercel.app", "https://app.brainova.ai"])

    def test_shutdown_lifecycle_is_safe_and_non_blocking(self):
        import backend.main as main_mod

        with patch.object(main_mod, "stop_tech_pulse_scheduler") as mock_stop, patch.object(
            main_mod, "shutdown_job_executor"
        ) as mock_shutdown:
            main_mod.on_shutdown()
            mock_stop.assert_called_once()
            mock_shutdown.assert_called_once_with(wait=False)


if __name__ == "__main__":
    unittest.main()
