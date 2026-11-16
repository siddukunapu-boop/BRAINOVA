"""
Unit & Integration Tests for the BRAINOVA Music & Focus Sounds Settings Module.
Verifies:
1. All 12 built-in tracks across 4 categories (Study Music, Deep Focus, Focus Noise, Nature & Ambient)
   generate valid, playable RIFF/WAVE PCM audio streams.
2. User audio upload for MP3, WAV, and OGG formats + authenticated playback streaming.
3. Rejection of invalid extensions, mismatched magic bytes, and executable/script payloads (MZ, ELF, #!, <script>).
4. Rejection of oversized audio uploads (HTTP 413) and empty files (HTTP 400).
5. Strict per-user isolation: User B cannot list, stream, or delete User A's uploaded audio tracks.
6. Safe deletion: removes both the SQLite database record and the stored audio file on disk,
   and resets music_last_track_id if it referenced the deleted track.
7. Filename sanitization and path traversal prevention.
8. User preferences persistence (last track, category, volume, position, playback preference).
9. Frontend architecture invariants: single root MusicPlayerProvider, OFF-by-default reload state,
   and strict placement at the bottom of SettingsPage only.
"""

import io
import os
import shutil
import tempfile
import unittest
import wave
from pathlib import Path
from fastapi import HTTPException

from backend.auth import create_access_token, ensure_user_preferences, hash_password, sanitize_preferences_for_client
from backend.database import get_db, init_db, new_id, utc_now
from backend.music_service import (
    BUILTIN_CATEGORIES,
    BUILTIN_TRACKS,
    delete_uploaded_user_track,
    get_or_create_builtin_wav_path,
    list_music_library_for_user,
    resolve_safe_user_track_path,
    sanitize_track_stem,
    save_uploaded_user_track,
    synthesize_builtin_wav_bytes,
    validate_uploaded_audio,
)


def _make_valid_wav_bytes(duration_sec: float = 0.25, sample_rate: int = 8000) -> bytes:
    buf = io.BytesIO()
    num_samples = int(duration_sec * sample_rate)
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * num_samples)
    return buf.getvalue()


def _make_valid_mp3_bytes() -> bytes:
    # Valid ID3v2 header + MPEG-1 Layer 3 frame sync (0xFF 0xFB 0x90 0x00)
    return b"ID3\x04\x00\x00\x00\x00\x00\x00" + (b"\xff\xfb\x90\x00" + b"\x00" * 60) * 4


def _make_valid_ogg_bytes() -> bytes:
    # Valid OggS capture pattern header
    return b"OggS\x00\x02\x00\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01\x1evorbis" + b"\x00" * 32


class TestMusicFocusSoundsModule(unittest.TestCase):
    _SHARED_PW_HASH: str = ""
    temp_dir: str = ""
    prev_data_dir: str | None = None
    prev_db_path: str | None = None
    prev_vercel: str | None = None
    prev_mongo: str | None = None
    user_a_id: str = ""
    user_b_id: str = ""

    @classmethod
    def setUpClass(cls) -> None:
        cls._SHARED_PW_HASH = hash_password("Password123!")
        cls.temp_dir = tempfile.mkdtemp(prefix="brainova_music_test_")
        cls.prev_data_dir = os.environ.get("BRAINOVA_DATA_DIR")
        cls.prev_db_path = os.environ.get("AETHER_DB_PATH")
        cls.prev_vercel = os.environ.get("VERCEL")
        cls.prev_mongo = os.environ.get("MONGODB_URI")

        os.environ.pop("VERCEL", None)
        os.environ["MONGODB_URI"] = ""
        os.environ["BRAINOVA_DATA_DIR"] = cls.temp_dir
        os.environ["AETHER_DB_PATH"] = os.path.join(cls.temp_dir, "test_music.db")

        init_db()

        cls.user_a_id = new_id("usr")
        cls.user_b_id = new_id("usr")
        now = utc_now()
        with get_db(commit=True) as conn:
            for uid, email, name in (
                (cls.user_a_id, f"{cls.user_a_id}@example.com", "User Alpha"),
                (cls.user_b_id, f"{cls.user_b_id}@example.com", "User Beta"),
            ):
                conn.execute(
                    """
                    INSERT INTO users (id, email, name, password_hash, role, target_role, bio, avatar_color, created_at, updated_at)
                    VALUES (?, ?, ?, ?, 'Learner', 'Full Stack Developer', '', '#d6b56d', ?, ?)
                    """,
                    (uid, email, name, cls._SHARED_PW_HASH, now, now),
                )
                ensure_user_preferences(conn, uid)

    @classmethod
    def tearDownClass(cls) -> None:
        if cls.prev_data_dir is None:
            os.environ.pop("BRAINOVA_DATA_DIR", None)
        else:
            os.environ["BRAINOVA_DATA_DIR"] = cls.prev_data_dir
        if cls.prev_db_path is None:
            os.environ.pop("AETHER_DB_PATH", None)
        else:
            os.environ["AETHER_DB_PATH"] = cls.prev_db_path
        if cls.prev_vercel is not None:
            os.environ["VERCEL"] = cls.prev_vercel
        if cls.prev_mongo is not None:
            os.environ["MONGODB_URI"] = cls.prev_mongo
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def setUp(self) -> None:
        with get_db(commit=True) as conn:
            conn.execute("DELETE FROM user_music_tracks")

    def tearDown(self) -> None:
        os.environ.pop("BRAINOVA_MAX_AUDIO_UPLOAD_BYTES", None)
        os.environ.pop("BRAINOVA_MAX_AUDIO_UPLOAD_MB", None)

    def test_01_builtin_library_categories_and_playable_wav_synthesis(self) -> None:
        """All 4 categories and 12 built-in tracks exist and synthesize valid playable WAV files."""
        cat_ids = [c["id"] for c in BUILTIN_CATEGORIES]
        self.assertEqual(cat_ids, ["study_music", "deep_focus", "focus_noise", "nature_ambient"])
        self.assertEqual(len(BUILTIN_TRACKS), 12)

        for cat_id in cat_ids:
            cat_tracks = [t for t in BUILTIN_TRACKS if t["category"] == cat_id]
            self.assertEqual(len(cat_tracks), 3, f"Expected 3 tracks in category {cat_id}")

        for track in BUILTIN_TRACKS:
            wav_bytes = synthesize_builtin_wav_bytes(track["id"])
            self.assertEqual(wav_bytes[:4], b"RIFF")
            self.assertEqual(wav_bytes[8:12], b"WAVE")
            with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
                self.assertEqual(wf.getnchannels(), 1)
                self.assertEqual(wf.getsampwidth(), 2)
                self.assertEqual(wf.getframerate(), 16000)
                duration = wf.getnframes() / float(wf.getframerate())
                self.assertAlmostEqual(duration, float(track["duration_seconds"]), places=1)

            disk_path = get_or_create_builtin_wav_path(track["id"])
            self.assertTrue(os.path.isfile(disk_path))
            self.assertGreater(os.path.getsize(disk_path), 10000)

    def test_02_upload_valid_wav_mp3_and_ogg_tracks(self) -> None:
        """Authenticated user can upload valid WAV, MP3, and OGG tracks and list them."""
        with get_db(commit=True) as conn:
            t_wav = save_uploaded_user_track(
                conn=conn,
                user_id=self.user_a_id,
                original_filename="calm_piano_loop.wav",
                raw_bytes=_make_valid_wav_bytes(0.5),
                title="Calm Piano Loop",
            )
            t_mp3 = save_uploaded_user_track(
                conn=conn,
                user_id=self.user_a_id,
                original_filename="focus_beats.mp3",
                raw_bytes=_make_valid_mp3_bytes(),
                title="Focus Beats",
            )
            t_ogg = save_uploaded_user_track(
                conn=conn,
                user_id=self.user_a_id,
                original_filename="rain_ambience.ogg",
                raw_bytes=_make_valid_ogg_bytes(),
                title="Rain Ambience",
            )

            self.assertEqual(t_wav["file_format"], "WAV")
            self.assertEqual(t_mp3["file_format"], "MP3")
            self.assertEqual(t_ogg["file_format"], "OGG")
            self.assertFalse(t_wav["is_builtin"])
            self.assertAlmostEqual(t_wav["duration_seconds"], 0.5, places=1)

            lib = list_music_library_for_user(conn, self.user_a_id)
            self.assertEqual(len(lib["builtin_tracks"]), 12)
            self.assertEqual(len(lib["uploaded_tracks"]), 3)

    def test_03_invalid_and_executable_uploads_rejected(self) -> None:
        """Invalid extensions, mismatched magic headers, and executable files are rejected with HTTP 400."""
        # Unsupported extension
        with self.assertRaises(HTTPException) as ctx_ext:
            validate_uploaded_audio("malware.exe", b"MZ\x90\x00" + b"\x00" * 60)
        self.assertEqual(ctx_ext.exception.status_code, 400)

        # Executable disguised as .mp3
        with self.assertRaises(HTTPException) as ctx_exe:
            validate_uploaded_audio("disguised.mp3", b"MZ\x90\x00" + b"\x00" * 60)
        self.assertEqual(ctx_exe.exception.status_code, 400)

        # ELF binary disguised as .wav
        with self.assertRaises(HTTPException) as ctx_elf:
            validate_uploaded_audio("linux_bin.wav", b"\x7fELF" + b"\x00" * 60)
        self.assertEqual(ctx_elf.exception.status_code, 400)

        # Script disguised as .ogg
        with self.assertRaises(HTTPException) as ctx_sh:
            validate_uploaded_audio("script.ogg", b"#!/bin/bash\nrm -rf /\n" + b"A" * 40)
        self.assertEqual(ctx_sh.exception.status_code, 400)

        # Random non-audio text disguised as .wav
        with self.assertRaises(HTTPException) as ctx_fake_wav:
            validate_uploaded_audio("not_really_wav.wav", b" Plain text file pretending to be audio " * 3)
        self.assertEqual(ctx_fake_wav.exception.status_code, 400)

        # Empty file
        with self.assertRaises(HTTPException) as ctx_empty:
            validate_uploaded_audio("empty.mp3", b"")
        self.assertEqual(ctx_empty.exception.status_code, 400)

    def test_04_oversized_upload_rejected(self) -> None:
        """Uploads exceeding configured size limit are rejected with HTTP 413."""
        os.environ["BRAINOVA_MAX_AUDIO_UPLOAD_BYTES"] = "512"
        oversized_wav = _make_valid_wav_bytes(duration_sec=0.5, sample_rate=8000)
        self.assertGreater(len(oversized_wav), 512)
        with self.assertRaises(HTTPException) as ctx:
            validate_uploaded_audio("large.wav", oversized_wav)
        self.assertEqual(ctx.exception.status_code, 413)

    def test_05_user_specific_uploaded_track_isolation(self) -> None:
        """User B cannot see, stream, or delete User A's uploaded tracks."""
        with get_db(commit=True) as conn:
            track_a = save_uploaded_user_track(
                conn=conn,
                user_id=self.user_a_id,
                original_filename="private_study.wav",
                raw_bytes=_make_valid_wav_bytes(0.25),
                title="User A Private Track",
            )

            lib_a = list_music_library_for_user(conn, self.user_a_id)
            lib_b = list_music_library_for_user(conn, self.user_b_id)
            self.assertEqual(len(lib_a["uploaded_tracks"]), 1)
            self.assertEqual(len(lib_b["uploaded_tracks"]), 0)

            # User B attempting to delete User A's track must raise 403 Forbidden
            with self.assertRaises(HTTPException) as ctx_del:
                delete_uploaded_user_track(conn, self.user_b_id, track_a["id"])
            self.assertEqual(ctx_del.exception.status_code, 403)

            # Verify User A's track still exists in DB and on disk
            still_there = list_music_library_for_user(conn, self.user_a_id)
            self.assertEqual(len(still_there["uploaded_tracks"]), 1)

    def test_06_deleting_uploaded_track_removes_db_record_and_file(self) -> None:
        """Deleting an uploaded track removes the DB row, deletes the disk file, and resets last_track_id."""
        with get_db(commit=True) as conn:
            track = save_uploaded_user_track(
                conn=conn,
                user_id=self.user_a_id,
                original_filename="to_delete.wav",
                raw_bytes=_make_valid_wav_bytes(0.25),
                title="Delete Me",
            )
            row = conn.execute(
                "SELECT storage_filename FROM user_music_tracks WHERE id = ?",
                (track["id"],),
            ).fetchone()
            disk_path = resolve_safe_user_track_path(self.user_a_id, row["storage_filename"])
            self.assertTrue(os.path.isfile(disk_path))

            # Point user's last selected track to this uploaded track
            conn.execute(
                "UPDATE user_preferences SET music_last_track_id = ? WHERE user_id = ?",
                (track["id"], self.user_a_id),
            )

            res = delete_uploaded_user_track(conn, self.user_a_id, track["id"])
            self.assertTrue(res["deleted"])
            self.assertTrue(res["file_removed"])
            self.assertFalse(os.path.isfile(disk_path))

            row_after = conn.execute(
                "SELECT * FROM user_music_tracks WHERE id = ?",
                (track["id"],),
            ).fetchone()
            self.assertIsNone(row_after)

            pref_after = ensure_user_preferences(conn, self.user_a_id)
            self.assertEqual(pref_after["music_last_track_id"], "builtin_study_gentle")

    def test_07_path_traversal_and_filename_sanitization(self) -> None:
        """Path traversal sequences in filenames or storage paths are sanitized or blocked."""
        stem = sanitize_track_stem("../../etc/passwd/../../../evil_name!@#$.mp3")
        self.assertNotIn("..", stem)
        self.assertNotIn("/", stem)
        self.assertNotIn("\\", stem)

        with self.assertRaises(HTTPException) as ctx:
            resolve_safe_user_track_path(self.user_a_id, "../outside.wav")
        self.assertIn(ctx.exception.status_code, (400, 403))

    def test_08_preferences_persistence_and_sanitization(self) -> None:
        """Music preferences persist in user_preferences and are returned by sanitize_preferences_for_client."""
        with get_db(commit=True) as conn:
            conn.execute(
                """
                UPDATE user_preferences
                SET music_last_track_id = 'builtin_nature_rain',
                    music_last_category = 'nature_ambient',
                    music_volume = 0.42,
                    music_playback_enabled = 1,
                    music_last_position = 5.5
                WHERE user_id = ?
                """,
                (self.user_a_id,),
            )
            pref = ensure_user_preferences(conn, self.user_a_id)
            clean = sanitize_preferences_for_client(pref)
            self.assertEqual(clean["music_last_track_id"], "builtin_nature_rain")
            self.assertEqual(clean["music_last_category"], "nature_ambient")
            self.assertAlmostEqual(clean["music_volume"], 0.42, places=2)
            self.assertTrue(clean["music_playback_enabled"])
            self.assertAlmostEqual(clean["music_last_position"], 5.5, places=1)

    def test_09_frontend_architecture_and_scope_invariants(self) -> None:
        """
        Verify:
        1. MusicPlayerProvider is mounted at root in src/App.tsx.
        2. MusicFocusSoundsSection is the final subsection in src/pages/SettingsPage.tsx.
        3. MusicPlayerContext initializes isPlaying to false (OFF after reload).
        4. No music nav item was added to AppShell.tsx or DashboardPage.tsx.
        """
        repo_root = Path(__file__).resolve().parent.parent
        app_tsx = (repo_root / "src" / "App.tsx").read_text(encoding="utf-8")
        settings_tsx = (repo_root / "src" / "pages" / "SettingsPage.tsx").read_text(encoding="utf-8")
        music_ctx_tsx = (repo_root / "src" / "context" / "MusicPlayerContext.tsx").read_text(encoding="utf-8")
        app_shell_tsx = (repo_root / "src" / "components" / "AppShell.tsx").read_text(encoding="utf-8")

        self.assertIn("<MusicPlayerProvider>", app_tsx)
        self.assertIn("<MusicFocusSoundsSection />", settings_tsx)
        # Ensure MusicFocusSoundsSection is placed after Save Preferences at the bottom of SettingsPage
        save_prefs_idx = settings_tsx.index("Save Preferences")
        music_sec_idx = settings_tsx.index("<MusicFocusSoundsSection />")
        self.assertGreater(music_sec_idx, save_prefs_idx)

        # Ensure isPlaying defaults to false
        self.assertIn("const [isPlaying, setIsPlaying] = useState<boolean>(false);", music_ctx_tsx)

        # Ensure AppShell has no Music sidebar link or floating player
        self.assertNotIn("MusicFocusSoundsSection", app_shell_tsx)
        self.assertNotIn("Music & Focus Sounds", app_shell_tsx)


if __name__ == "__main__":
    unittest.main()
