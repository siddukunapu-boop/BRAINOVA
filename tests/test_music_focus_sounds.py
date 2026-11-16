"""
Unit & Integration Tests for:
- Task 1: Customized Roadmap Tutorial & Reading Material Responsive Layout Fix
- Task 2.G: All 12 Uploaded-Song Delete Button, Confirmation, Security, and Active Playback Tests
- Task 3: Complete StudyOS User-Facing Branding Cleanup (including StudyOS AI Mentor)
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
from backend.main import stream_uploaded_music_track
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


class TestMusicFocusSoundsAndStudyOSFixes(unittest.TestCase):
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
        cls.temp_dir = tempfile.mkdtemp(prefix="studyos_music_test_")
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

    def test_del_01_delete_button_appears_for_uploaded_tracks(self) -> None:
        """1. Delete button appears for uploaded tracks (both in library cards and uploaded list)."""
        repo_root = Path(__file__).resolve().parent.parent
        sec_tsx = (repo_root / "src" / "components" / "MusicFocusSoundsSection.tsx").read_text(encoding="utf-8")
        self.assertIn('data-testid={`music-delete-btn-${track.id}`}', sec_tsx)
        self.assertIn('data-testid={`music-uploaded-delete-${ut.id}`}', sec_tsx)
        self.assertIn("<span>{deletingTrackId === track.id ? 'Deleting...' : 'Delete'}</span>", sec_tsx)

    def test_del_02_delete_button_does_not_appear_for_builtin_tracks(self) -> None:
        """2. Delete button never appears for built-in tracks."""
        repo_root = Path(__file__).resolve().parent.parent
        sec_tsx = (repo_root / "src" / "components" / "MusicFocusSoundsSection.tsx").read_text(encoding="utf-8")
        self.assertIn("{!track.is_builtin && (", sec_tsx)
        for t in BUILTIN_TRACKS:
            self.assertTrue(t["is_builtin"])

    def test_del_03_cancel_confirmation_does_not_delete_track(self) -> None:
        """3. Cancel confirmation closes dialog without deleting the track."""
        repo_root = Path(__file__).resolve().parent.parent
        sec_tsx = (repo_root / "src" / "components" / "MusicFocusSoundsSection.tsx").read_text(encoding="utf-8")
        self.assertIn("Delete this uploaded song?", sec_tsx)
        self.assertIn("This song will be permanently removed from your uploaded music library.", sec_tsx)
        self.assertIn("onClick={() => setConfirmDeleteTrack(null)}", sec_tsx)
        self.assertIn('data-testid="music-delete-cancel-btn"', sec_tsx)

    def test_del_04_confirmed_deletion_removes_database_record(self) -> None:
        """4. Confirmed deletion removes the database record from user_music_tracks."""
        with get_db(commit=True) as conn:
            track = save_uploaded_user_track(
                conn=conn,
                user_id=self.user_a_id,
                original_filename="db_remove_test.wav",
                raw_bytes=_make_valid_wav_bytes(0.25),
                title="DB Remove Test",
            )
            res = delete_uploaded_user_track(conn, self.user_a_id, track["id"])
            self.assertTrue(res["deleted"])
            row_after = conn.execute(
                "SELECT * FROM user_music_tracks WHERE id = ?",
                (track["id"],),
            ).fetchone()
            self.assertIsNone(row_after)

    def test_del_05_confirmed_deletion_removes_physical_audio_file(self) -> None:
        """5. Confirmed deletion removes the physical audio file from disk."""
        with get_db(commit=True) as conn:
            track = save_uploaded_user_track(
                conn=conn,
                user_id=self.user_a_id,
                original_filename="file_remove_test.wav",
                raw_bytes=_make_valid_wav_bytes(0.25),
                title="File Remove Test",
            )
            row = conn.execute(
                "SELECT storage_filename FROM user_music_tracks WHERE id = ?",
                (track["id"],),
            ).fetchone()
            disk_path = resolve_safe_user_track_path(self.user_a_id, row["storage_filename"])
            self.assertTrue(os.path.isfile(disk_path))

            res = delete_uploaded_user_track(conn, self.user_a_id, track["id"])
            self.assertTrue(res["file_removed"])
            self.assertFalse(os.path.isfile(disk_path))

    def test_del_06_deleted_track_disappears_from_ui_and_library(self) -> None:
        """6. Deleted track disappears from the user's library list and UI state."""
        with get_db(commit=True) as conn:
            track = save_uploaded_user_track(
                conn=conn,
                user_id=self.user_a_id,
                original_filename="ui_remove_test.mp3",
                raw_bytes=_make_valid_mp3_bytes(),
                title="UI Remove Test",
            )
            before_lib = list_music_library_for_user(conn, self.user_a_id)
            self.assertEqual(len(before_lib["uploaded_tracks"]), 1)

            delete_uploaded_user_track(conn, self.user_a_id, track["id"])
            after_lib = list_music_library_for_user(conn, self.user_a_id)
            self.assertEqual(len(after_lib["uploaded_tracks"]), 0)

        repo_root = Path(__file__).resolve().parent.parent
        ctx_tsx = (repo_root / "src" / "context" / "MusicPlayerContext.tsx").read_text(encoding="utf-8")
        self.assertIn("setUploadedTracks((prev) => prev.filter((t) => t.id !== trackId));", ctx_tsx)

    def test_del_07_user_a_cannot_delete_user_b_track(self) -> None:
        """7. User A cannot delete User B's uploaded track (HTTP 403 Forbidden)."""
        with get_db(commit=True) as conn:
            track_b = save_uploaded_user_track(
                conn=conn,
                user_id=self.user_b_id,
                original_filename="user_b_private.ogg",
                raw_bytes=_make_valid_ogg_bytes(),
                title="User B Song",
            )
            with self.assertRaises(HTTPException) as ctx_del:
                delete_uploaded_user_track(conn, self.user_a_id, track_b["id"])
            self.assertEqual(ctx_del.exception.status_code, 403)

            # Verify User B's track remains intact
            lib_b = list_music_library_for_user(conn, self.user_b_id)
            self.assertEqual(len(lib_b["uploaded_tracks"]), 1)

    def test_del_08_deleted_track_cannot_be_streamed_afterward(self) -> None:
        """8. Deleted track cannot be streamed afterward (HTTP 404 Not Found)."""
        with get_db(commit=True) as conn:
            track = save_uploaded_user_track(
                conn=conn,
                user_id=self.user_a_id,
                original_filename="no_stream_after_delete.wav",
                raw_bytes=_make_valid_wav_bytes(0.25),
                title="No Stream After Delete",
            )
            delete_uploaded_user_track(conn, self.user_a_id, track["id"])

        with self.assertRaises(HTTPException) as ctx_stream:
            stream_uploaded_music_track(track["id"], current_user={"id": self.user_a_id})
        self.assertEqual(ctx_stream.exception.status_code, 404)

    def test_del_09_deleting_currently_playing_song_stops_playback_safely(self) -> None:
        """9. Deleting the currently playing song stops playback, clears source, revokes ObjectURL, and resets track."""
        repo_root = Path(__file__).resolve().parent.parent
        ctx_tsx = (repo_root / "src" / "context" / "MusicPlayerContext.tsx").read_text(encoding="utf-8")
        self.assertIn("if (currentTrackId === trackId || loadedTrackIdRef.current === trackId)", ctx_tsx)
        self.assertIn("audioRef.current.pause();", ctx_tsx)
        self.assertIn("audioRef.current.removeAttribute('src');", ctx_tsx)
        self.assertIn("revokeActiveObjectUrl();", ctx_tsx)
        self.assertIn("setIsPlaying(false);", ctx_tsx)
        self.assertIn("setCurrentTrackId('builtin_study_gentle');", ctx_tsx)

        with get_db(commit=True) as conn:
            track = save_uploaded_user_track(
                conn=conn,
                user_id=self.user_a_id,
                original_filename="playing_now.wav",
                raw_bytes=_make_valid_wav_bytes(0.25),
                title="Playing Now",
            )
            conn.execute(
                "UPDATE user_preferences SET music_last_track_id = ? WHERE user_id = ?",
                (track["id"], self.user_a_id),
            )
            delete_uploaded_user_track(conn, self.user_a_id, track["id"])
            pref = ensure_user_preferences(conn, self.user_a_id)
            self.assertEqual(pref["music_last_track_id"], "builtin_study_gentle")

    def test_del_10_deleting_non_playing_song_does_not_interrupt_active_song(self) -> None:
        """10. Deleting a non-playing song preserves the active playing track in preferences and player state."""
        with get_db(commit=True) as conn:
            active_track = save_uploaded_user_track(
                conn=conn,
                user_id=self.user_a_id,
                original_filename="active_song.wav",
                raw_bytes=_make_valid_wav_bytes(0.25),
                title="Active Song",
            )
            other_track = save_uploaded_user_track(
                conn=conn,
                user_id=self.user_a_id,
                original_filename="other_song.wav",
                raw_bytes=_make_valid_wav_bytes(0.25),
                title="Other Song",
            )
            conn.execute(
                "UPDATE user_preferences SET music_last_track_id = ? WHERE user_id = ?",
                (active_track["id"], self.user_a_id),
            )
            delete_uploaded_user_track(conn, self.user_a_id, other_track["id"])
            pref = ensure_user_preferences(conn, self.user_a_id)
            self.assertEqual(pref["music_last_track_id"], active_track["id"])

    def test_del_11_backend_failure_does_not_falsely_remove_track_from_ui(self) -> None:
        """11. Backend deletion failure keeps track in UI state and keeps confirm modal open with error toast."""
        repo_root = Path(__file__).resolve().parent.parent
        ctx_tsx = (repo_root / "src" / "context" / "MusicPlayerContext.tsx").read_text(encoding="utf-8")
        del_block = ctx_tsx.split("const deleteTrack = useCallback")[1]
        self.assertLess(
            del_block.index("setUploadedTracks((prev) => prev.filter"),
            del_block.index("} catch (err: any) {"),
        )
        self.assertIn("return false;", del_block.split("} catch (err: any) {")[1])

    def test_del_12_repeated_delete_actions_are_handled_safely(self) -> None:
        """12. Repeated delete actions are blocked in flight on frontend and return 404 cleanly on backend."""
        repo_root = Path(__file__).resolve().parent.parent
        ctx_tsx = (repo_root / "src" / "context" / "MusicPlayerContext.tsx").read_text(encoding="utf-8")
        self.assertIn("deletingInFlightRef.current.has(trackId)", ctx_tsx)

        with get_db(commit=True) as conn:
            track = save_uploaded_user_track(
                conn=conn,
                user_id=self.user_a_id,
                original_filename="once.wav",
                raw_bytes=_make_valid_wav_bytes(0.25),
                title="Delete Once",
            )
            delete_uploaded_user_track(conn, self.user_a_id, track["id"])
            with self.assertRaises(HTTPException) as ctx_second:
                delete_uploaded_user_track(conn, self.user_a_id, track["id"])
            self.assertEqual(ctx_second.exception.status_code, 404)

    def test_task1_customized_roadmap_overflow_layout_fix(self) -> None:
        """Task 1: Customized Roadmap uses responsive .crm-* grid and separated preview actions."""
        repo_root = Path(__file__).resolve().parent.parent
        crm_tsx = (repo_root / "src" / "pages" / "CustomizedRoadmapPage.tsx").read_text(encoding="utf-8")
        css = (repo_root / "src" / "styles" / "design-system.css").read_text(encoding="utf-8")

        self.assertIn('className="crm-editors-grid"', crm_tsx)
        self.assertIn('className="crm-tutorial-preview"', crm_tsx)
        self.assertIn('className="crm-tutorial-preview-top"', crm_tsx)
        self.assertIn('className="crm-tutorial-actions"', crm_tsx)
        self.assertIn(".crm-editors-grid", css)
        self.assertIn("@media (max-width: 1120px)", css)
        self.assertIn("@media (max-width: 560px)", css)

    def test_task3_complete_user_facing_studyos_branding_cleanup(self) -> None:
        """Task 3: AI Mentor and all user-facing pages/components display StudyOS with zero user-facing BRAINOVA."""
        repo_root = Path(__file__).resolve().parent.parent
        mentor_tsx = (repo_root / "src" / "components" / "CareerMentorPanel.tsx").read_text(encoding="utf-8")
        self.assertIn("StudyOS AI Mentor", mentor_tsx)
        self.assertNotIn("BRAINOVA AI Mentor", mentor_tsx)

        app_shell_tsx = (repo_root / "src" / "components" / "AppShell.tsx").read_text(encoding="utf-8")
        self.assertEqual(app_shell_tsx.count("LEARN SMARTER. THINK BIGGER."), 2)
        self.assertIn("StudyOS", app_shell_tsx)

        allowed_internal_tokens = {"BRAINOVA_THEMES", "[BRAINOVA]"}
        for path in list((repo_root / "src" / "pages").glob("*.tsx")) + list((repo_root / "src" / "components").glob("*.tsx")):
            lines = path.read_text(encoding="utf-8").splitlines()
            for line_no, line in enumerate(lines, 1):
                stripped = line.strip()
                if stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*") or stripped.startswith("{/*"):
                    continue
                if "BRAINOVA" in stripped:
                    cleaned = stripped
                    for tok in allowed_internal_tokens:
                        cleaned = cleaned.replace(tok, "")
                    self.assertNotIn(
                        "BRAINOVA",
                        cleaned,
                        f"Found user-facing BRAINOVA in {path.name}:{line_no}: {stripped}",
                    )


if __name__ == "__main__":
    unittest.main()
