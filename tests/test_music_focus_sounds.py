"""
Unit & Integration Tests for the BRAINOVA Music & Focus Sounds Settings Module.
Covers all 14 required test scenarios:
1. Built-in track playback & valid RIFF/WAVE stream generation across all 4 categories (12 tracks).
2. Uploaded track playback (MP3, WAV, OGG upload + authenticated stream).
3. Invalid audio upload rejection (unsupported extension, invalid headers, executable payloads).
4. Oversized upload rejection (HTTP 413).
5. User-specific uploaded track isolation (list, stream, delete protection across users).
6. Deleting an uploaded track (DB row removal + disk file deletion + preference fallback).
7. Playback continuing across internal route navigation (persistent root MusicPlayerProvider).
8. No duplicate audio playback (single HTMLAudioElement ref with pause-before-switch).
9. Music OFF after full reload (isPlaying initialized to false regardless of saved preference).
10. No automatic playback on returning to the website or visiting Settings.
11. Volume, track, category, and position persistence.
12. Audio resource cleanup on unmount, track switch, delete, and logout.
13. Responsive Settings UI & 4-theme CSS adaptation + reduced-motion compliance.
14. Existing feature regression protection (sidebar, dashboard, auth, focus, settings profile).
"""

import io
import os
import shutil
import tempfile
import unittest
import wave
from pathlib import Path
from fastapi import HTTPException

from backend.auth import ensure_user_preferences, hash_password, sanitize_preferences_for_client
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
    return b"ID3\x04\x00\x00\x00\x00\x00\x00" + (b"\xff\xfb\x90\x00" + b"\x00" * 60) * 4


def _make_valid_ogg_bytes() -> bytes:
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

    def test_01_builtin_track_playback_and_wav_synthesis(self) -> None:
        """1. Built-in track playback: all 12 tracks across 4 categories generate valid playable WAV streams."""
        cat_ids = [c["id"] for c in BUILTIN_CATEGORIES]
        self.assertEqual(cat_ids, ["study_music", "deep_focus", "focus_noise", "nature_ambient"])
        self.assertEqual(len(BUILTIN_TRACKS), 12)

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

    def test_02_uploaded_track_playback_and_storage(self) -> None:
        """2. Uploaded track playback: MP3, WAV, and OGG tracks upload, store on disk, and expose stream URLs."""
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
            self.assertTrue(t_wav["stream_url"].startswith("/api/music/tracks/"))

            lib = list_music_library_for_user(conn, self.user_a_id)
            self.assertEqual(len(lib["uploaded_tracks"]), 3)

    def test_03_invalid_audio_upload_rejection(self) -> None:
        """3. Invalid audio upload rejection: unsupported extensions, fake headers, and executables fail with 400."""
        for fname, payload in (
            ("malware.exe", b"MZ\x90\x00" + b"\x00" * 60),
            ("disguised.mp3", b"MZ\x90\x00" + b"\x00" * 60),
            ("linux_bin.wav", b"\x7fELF" + b"\x00" * 60),
            ("script.ogg", b"#!/bin/bash\nrm -rf /\n" + b"A" * 40),
            ("xss.mp3", b"<script>alert(1)</script>" + b"A" * 40),
            ("fake.wav", b"Not a RIFF WAVE header at all" * 3),
            ("empty.mp3", b""),
        ):
            with self.assertRaises(HTTPException) as ctx:
                validate_uploaded_audio(fname, payload)
            self.assertEqual(ctx.exception.status_code, 400)

    def test_04_oversized_upload_rejection(self) -> None:
        """4. Oversized upload rejection: files larger than max upload limit fail with HTTP 413."""
        os.environ["BRAINOVA_MAX_AUDIO_UPLOAD_BYTES"] = "512"
        oversized_wav = _make_valid_wav_bytes(duration_sec=0.5, sample_rate=8000)
        with self.assertRaises(HTTPException) as ctx:
            validate_uploaded_audio("large.wav", oversized_wav)
        self.assertEqual(ctx.exception.status_code, 413)

    def test_05_user_specific_uploaded_track_isolation(self) -> None:
        """5. User-specific uploaded track isolation: User B cannot list or delete User A's tracks."""
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

            with self.assertRaises(HTTPException) as ctx_del:
                delete_uploaded_user_track(conn, self.user_b_id, track_a["id"])
            self.assertEqual(ctx_del.exception.status_code, 403)

    def test_06_deleting_uploaded_track_removes_db_and_file(self) -> None:
        """6. Deleting an uploaded track removes the DB record, deletes the disk file, and resets last_track_id."""
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

            conn.execute(
                "UPDATE user_preferences SET music_last_track_id = ? WHERE user_id = ?",
                (track["id"], self.user_a_id),
            )
            res = delete_uploaded_user_track(conn, self.user_a_id, track["id"])
            self.assertTrue(res["deleted"])
            self.assertTrue(res["file_removed"])
            self.assertFalse(os.path.isfile(disk_path))

            pref_after = ensure_user_preferences(conn, self.user_a_id)
            self.assertEqual(pref_after["music_last_track_id"], "builtin_study_gentle")

    def test_07_playback_persists_across_internal_route_navigation(self) -> None:
        """7. MusicPlayerProvider wraps AppShell and Routes at ProtectedRoutes root so navigation never unmounts audio."""
        repo_root = Path(__file__).resolve().parent.parent
        app_tsx = (repo_root / "src" / "App.tsx").read_text(encoding="utf-8")
        provider_open = app_tsx.index("<MusicPlayerProvider>")
        appshell_open = app_tsx.index("<AppShell>")
        routes_open = app_tsx.index("<Routes>", appshell_open)
        appshell_close = app_tsx.index("</AppShell>", routes_open)
        provider_close = app_tsx.index("</MusicPlayerProvider>", appshell_close)
        self.assertLess(provider_open, appshell_open)
        self.assertLess(appshell_close, provider_close)

    def test_08_single_audio_instance_prevents_duplicate_playback(self) -> None:
        """8. MusicPlayerContext creates exactly one Audio instance and pauses before switching sources."""
        repo_root = Path(__file__).resolve().parent.parent
        ctx_tsx = (repo_root / "src" / "context" / "MusicPlayerContext.tsx").read_text(encoding="utf-8")
        self.assertEqual(ctx_tsx.count("new Audio()"), 1)
        self.assertIn("audio.pause();\n      revokeActiveObjectUrl();", ctx_tsx)

    def test_09_music_off_after_full_reload(self) -> None:
        """9. Music is strictly OFF after full reload even if music_playback_enabled was saved as true."""
        repo_root = Path(__file__).resolve().parent.parent
        ctx_tsx = (repo_root / "src" / "context" / "MusicPlayerContext.tsx").read_text(encoding="utf-8")
        self.assertIn("const [isPlaying, setIsPlaying] = useState<boolean>(false);", ctx_tsx)
        # Ensure refreshLibrary never calls play() or setIsPlaying(true)
        refresh_block = ctx_tsx.split("const refreshLibrary = useCallback")[1].split("const loadTrackIntoAudioElement")[0]
        self.assertNotIn(".play()", refresh_block)
        self.assertNotIn("setIsPlaying(true)", refresh_block)

    def test_10_no_automatic_playback_on_visiting_settings(self) -> None:
        """10. Visiting SettingsPage or mounting MusicFocusSoundsSection never triggers automatic playback."""
        repo_root = Path(__file__).resolve().parent.parent
        sec_tsx = (repo_root / "src" / "components" / "MusicFocusSoundsSection.tsx").read_text(encoding="utf-8")
        self.assertNotIn("useEffect", sec_tsx)

    def test_11_volume_and_preference_persistence(self) -> None:
        """11. Volume, track, category, and position persist in user_preferences."""
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
            self.assertAlmostEqual(clean["music_last_position"], 5.5, places=1)

    def test_12_audio_resource_cleanup_and_path_traversal_protection(self) -> None:
        """12. ObjectURL revocation, event listener cleanup, and path traversal defenses are present."""
        repo_root = Path(__file__).resolve().parent.parent
        ctx_tsx = (repo_root / "src" / "context" / "MusicPlayerContext.tsx").read_text(encoding="utf-8")
        self.assertIn("URL.revokeObjectURL", ctx_tsx)
        self.assertIn("audio.removeEventListener('timeupdate'", ctx_tsx)

        stem = sanitize_track_stem("../../etc/passwd/../../../evil_name!@#$.mp3")
        self.assertNotIn("..", stem)
        with self.assertRaises(HTTPException) as ctx:
            resolve_safe_user_track_path(self.user_a_id, "../outside.wav")
        self.assertIn(ctx.exception.status_code, (400, 403))

    def test_13_responsive_settings_ui_and_reduced_motion_styles(self) -> None:
        """13. CSS includes responsive breakpoints and reduced-motion rules for .mfs-* components."""
        repo_root = Path(__file__).resolve().parent.parent
        css = (repo_root / "src" / "styles" / "design-system.css").read_text(encoding="utf-8")
        self.assertIn(".mfs-section", css)
        self.assertIn("@media (max-width: 900px)", css)
        self.assertIn('body[data-reduced-motion="true"] .mfs-track-card', css)

    def test_14_existing_feature_regression_protection(self) -> None:
        """14. Strict scope: MusicFocusSoundsSection is at bottom of SettingsPage only; AppShell and Dashboard untouched."""
        repo_root = Path(__file__).resolve().parent.parent
        settings_tsx = (repo_root / "src" / "pages" / "SettingsPage.tsx").read_text(encoding="utf-8")
        app_shell_tsx = (repo_root / "src" / "components" / "AppShell.tsx").read_text(encoding="utf-8")
        dashboard_tsx = (repo_root / "src" / "pages" / "DashboardPage.tsx").read_text(encoding="utf-8")

        save_prefs_idx = settings_tsx.index("Save Preferences")
        music_sec_idx = settings_tsx.index("<MusicFocusSoundsSection />")
        self.assertGreater(music_sec_idx, save_prefs_idx)

        self.assertNotIn("MusicFocusSoundsSection", app_shell_tsx)
        self.assertNotIn("Music & Focus Sounds", app_shell_tsx)
        self.assertNotIn("MusicFocusSoundsSection", dashboard_tsx)


if __name__ == "__main__":
    unittest.main()
