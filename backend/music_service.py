"""
BRAINOVA — Music & Focus Sounds Backend Service
Provides:
1. 12 original, royalty-free (first-party synthesized CC0) playable audio tracks across 4 categories:
   - Study Music
   - Deep Focus
   - Focus Noise
   - Nature & Ambient
2. Strict audio file upload validation (extension + magic-byte signature inspection + executable rejection + size limits).
3. Per-user isolated storage, metadata persistence, streaming, and safe file deletion.
"""

import array
import io
import math
import os
import random
import re
import sqlite3
import wave
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException

from backend.database import AUDIO_DIR, is_mongo_authoritative, new_id, utc_now

DEFAULT_MAX_UPLOAD_KB = 40_000
DEFAULT_MAX_UPLOAD_BYTES = DEFAULT_MAX_UPLOAD_KB * 1024
RECOMMENDED_UPLOAD_CHUNK_BYTES = 2 * 1024 * 1024  # 2 MiB (well below Vercel 4.5 MB limit)
MAX_UPLOAD_CHUNK_BYTES = 3 * 1024 * 1024          # 3 MiB hard per-chunk cap


def get_max_audio_upload_bytes() -> int:
    raw_bytes = (os.environ.get("BRAINOVA_MAX_AUDIO_UPLOAD_BYTES") or "").strip()
    if raw_bytes.isdigit() and int(raw_bytes) > 0:
        return int(raw_bytes)
    raw_kb = (os.environ.get("BRAINOVA_MAX_AUDIO_UPLOAD_KB") or "").strip()
    if raw_kb:
        try:
            kb = float(raw_kb)
            if kb > 0:
                return int(kb * 1024)
        except ValueError:
            pass
    raw_mb = (os.environ.get("BRAINOVA_MAX_AUDIO_UPLOAD_MB") or "").strip()
    if raw_mb:
        try:
            mb = float(raw_mb)
            if mb > 0:
                return int(mb * 1024 * 1024)
        except ValueError:
            pass
    return DEFAULT_MAX_UPLOAD_BYTES


def format_upload_limit_label(max_bytes: Optional[int] = None) -> str:
    limit = max_bytes if max_bytes is not None else get_max_audio_upload_bytes()
    max_kb = max(1, round(limit / 1024))
    max_mb = round(max_kb / 1000, 1) if max_kb % 1000 != 0 else int(max_kb // 1000)
    return f"{max_kb:,} KB ({max_mb} MB)"


BUILTIN_CATEGORIES: List[Dict[str, str]] = [
    {
        "id": "study_music",
        "name": "Study Music",
        "description": "Gentle instrumental progressions, soft piano, and calm ambient harmonic beds",
    },
    {
        "id": "deep_focus",
        "name": "Deep Focus",
        "description": "Deep concentration drones, minimal atmospheric soundscapes, and distraction-reducing ambience",
    },
    {
        "id": "focus_noise",
        "name": "Focus Noise",
        "description": "Calibrated brown, white, and pink acoustic masking noise for cognitive isolation",
    },
    {
        "id": "nature_ambient",
        "name": "Nature & Ambient",
        "description": "Organic rainfall, gentle forest breeze, and rhythmic ocean water soundscapes",
    },
]

BUILTIN_TRACKS: List[Dict[str, Any]] = [
    # A. Study Music
    {
        "id": "builtin_study_gentle",
        "title": "Gentle Instrumental Study",
        "subtitle": "Warm harmonic electric-piano chords for sustained reading & coding",
        "category": "study_music",
        "category_label": "Study Music",
        "file_format": "WAV",
        "mime_type": "audio/wav",
        "duration_seconds": 12.0,
        "is_builtin": True,
        "license": "StudyOS Original Synthesized Audio (CC0 / Royalty-Free)",
    },
    {
        "id": "builtin_study_piano",
        "title": "Soft Nocturne Piano",
        "subtitle": "Delicate arpeggiated piano intervals with warm acoustic decay",
        "category": "study_music",
        "category_label": "Study Music",
        "file_format": "WAV",
        "mime_type": "audio/wav",
        "duration_seconds": 12.0,
        "is_builtin": True,
        "license": "StudyOS Original Synthesized Audio (CC0 / Royalty-Free)",
    },
    {
        "id": "builtin_study_ambient",
        "title": "Calm Ambient Instrumental",
        "subtitle": "Slow-breathing major-seventh instrumental pads for calm comprehension",
        "category": "study_music",
        "category_label": "Study Music",
        "file_format": "WAV",
        "mime_type": "audio/wav",
        "duration_seconds": 12.0,
        "is_builtin": True,
        "license": "StudyOS Original Synthesized Audio (CC0 / Royalty-Free)",
    },
    # B. Deep Focus
    {
        "id": "builtin_focus_concentration",
        "title": "Deep Concentration Ambient",
        "subtitle": "Low-register harmonic fifths engineered for uninterrupted deep work",
        "category": "deep_focus",
        "category_label": "Deep Focus",
        "file_format": "WAV",
        "mime_type": "audio/wav",
        "duration_seconds": 12.0,
        "is_builtin": True,
        "license": "StudyOS Original Synthesized Audio (CC0 / Royalty-Free)",
    },
    {
        "id": "builtin_focus_minimal",
        "title": "Minimal Atmospheric Soundscape",
        "subtitle": "Subtle dark-velvet resonant texture with zero rhythmic distraction",
        "category": "deep_focus",
        "category_label": "Deep Focus",
        "file_format": "WAV",
        "mime_type": "audio/wav",
        "duration_seconds": 12.0,
        "is_builtin": True,
        "license": "StudyOS Original Synthesized Audio (CC0 / Royalty-Free)",
    },
    {
        "id": "builtin_focus_shield",
        "title": "Distraction-Reducing Instrumental Ambience",
        "subtitle": "Balanced mid-frequency harmonic masking canopy for noisy environments",
        "category": "deep_focus",
        "category_label": "Deep Focus",
        "file_format": "WAV",
        "mime_type": "audio/wav",
        "duration_seconds": 12.0,
        "is_builtin": True,
        "license": "StudyOS Original Synthesized Audio (CC0 / Royalty-Free)",
    },
    # C. Focus Noise
    {
        "id": "builtin_noise_brown",
        "title": "Warm Brown Noise",
        "subtitle": "Deep 1/f² Brownian low-frequency cascade for calm mental grounding",
        "category": "focus_noise",
        "category_label": "Focus Noise",
        "file_format": "WAV",
        "mime_type": "audio/wav",
        "duration_seconds": 10.0,
        "is_builtin": True,
        "license": "StudyOS Original Synthesized Audio (CC0 / Royalty-Free)",
    },
    {
        "id": "builtin_noise_white",
        "title": "Pure Softened White Noise",
        "subtitle": "Smooth uniform broadband acoustic masking to block external chatter",
        "category": "focus_noise",
        "category_label": "Focus Noise",
        "file_format": "WAV",
        "mime_type": "audio/wav",
        "duration_seconds": 10.0,
        "is_builtin": True,
        "license": "StudyOS Original Synthesized Audio (CC0 / Royalty-Free)",
    },
    {
        "id": "builtin_noise_pink",
        "title": "Balanced Pink Noise",
        "subtitle": "Equal-energy-per-octave 1/f spectrum for balanced auditory focus",
        "category": "focus_noise",
        "category_label": "Focus Noise",
        "file_format": "WAV",
        "mime_type": "audio/wav",
        "duration_seconds": 10.0,
        "is_builtin": True,
        "license": "StudyOS Original Synthesized Audio (CC0 / Royalty-Free)",
    },
    # D. Nature & Ambient
    {
        "id": "builtin_nature_rain",
        "title": "Midnight Rain Sounds",
        "subtitle": "Steady nocturnal rainfall with gentle acoustic pattering",
        "category": "nature_ambient",
        "category_label": "Nature & Ambient",
        "file_format": "WAV",
        "mime_type": "audio/wav",
        "duration_seconds": 10.0,
        "is_builtin": True,
        "license": "StudyOS Original Synthesized Audio (CC0 / Royalty-Free)",
    },
    {
        "id": "builtin_nature_forest",
        "title": "Gentle Forest Ambience",
        "subtitle": "Soft woodland canopy breeze and tranquil natural resonance",
        "category": "nature_ambient",
        "category_label": "Nature & Ambient",
        "file_format": "WAV",
        "mime_type": "audio/wav",
        "duration_seconds": 12.0,
        "is_builtin": True,
        "license": "StudyOS Original Synthesized Audio (CC0 / Royalty-Free)",
    },
    {
        "id": "builtin_nature_ocean",
        "title": "Ocean & Water Ambience",
        "subtitle": "Rhythmic coastal tide swells and calm receding water wash",
        "category": "nature_ambient",
        "category_label": "Nature & Ambient",
        "file_format": "WAV",
        "mime_type": "audio/wav",
        "duration_seconds": 12.0,
        "is_builtin": True,
        "license": "StudyOS Original Synthesized Audio (CC0 / Royalty-Free)",
    },
]

BUILTIN_TRACK_MAP: Dict[str, Dict[str, Any]] = {t["id"]: t for t in BUILTIN_TRACKS}

ALLOWED_UPLOAD_EXTENSIONS: Dict[str, Tuple[str, str]] = {
    ".mp3": ("MP3", "audio/mpeg"),
    ".wav": ("WAV", "audio/wav"),
    ".ogg": ("OGG", "audio/ogg"),
}

FORBIDDEN_SIGNATURES: Tuple[bytes, ...] = (
    b"MZ",              # Windows PE / EXE / DLL
    b"\x7fELF",         # Linux ELF binary
    b"#!",              # Shell / script shebang
    b"PK\x03\x04",      # ZIP / JAR / APK archive
    b"<?php",           # PHP script
    b"<script",         # HTML / JS payload
    b"<!DOCTYPE html",  # HTML document
    b"<html",           # HTML document
)


def _envelope_loop(t: float, duration: float, fade_sec: float = 0.25) -> float:
    if t < fade_sec:
        return 0.5 * (1.0 - math.cos(math.pi * (t / fade_sec)))
    if t > duration - fade_sec:
        rem = max(0.0, duration - t)
        return 0.5 * (1.0 - math.cos(math.pi * (rem / fade_sec)))
    return 1.0


def synthesize_builtin_wav_bytes(track_id: str) -> bytes:
    """
    Deterministically synthesize a warm, clean 16-bit PCM WAV file for any built-in track.
    Uses standard library `wave`, `array`, `math`, and seeded `random` so zero external binaries or
    copyrighted third-party files are required, completing in <35ms per track on serverless runtimes.
    """
    meta = BUILTIN_TRACK_MAP.get(track_id)
    if not meta:
        raise KeyError(f"Unknown built-in track ID: {track_id}")

    sample_rate = 16000
    duration = float(meta["duration_seconds"])
    total_samples = int(sample_rate * duration)
    # Synthesize a 2.0-second seamless cycle and tile to full duration with envelope smoothing
    cycle_sec = 2.0
    cycle_samples = int(sample_rate * cycle_sec)
    rng = random.Random(track_id)
    two_pi = 2.0 * math.pi
    sin = math.sin

    cycle_buf = [0] * cycle_samples

    if track_id == "builtin_study_gentle":
        f1, f2, f3, f4 = 174.61, 220.00, 261.63, 329.63
        for i in range(cycle_samples):
            t = i / sample_rate
            env = _envelope_loop(t, cycle_sec, 0.2)
            lfo = 0.88 + 0.12 * sin(two_pi * 0.5 * t)
            val = (sin(two_pi * f1 * t) + sin(two_pi * f2 * t) + sin(two_pi * f3 * t) + sin(two_pi * f4 * t)) * 0.18 * env * lfo
            cycle_buf[i] = int(max(-32767.0, min(32767.0, val * 32767.0)))

    elif track_id == "builtin_study_piano":
        notes = (261.63, 329.63, 392.00, 493.88)
        note_dur = cycle_sec / len(notes)
        for i in range(cycle_samples):
            t = i / sample_rate
            idx = min(len(notes) - 1, int(t / note_dur))
            nt = t - idx * note_dur
            freq = notes[idx]
            attack = min(1.0, nt / 0.03)
            decay = math.exp(-3.0 * nt)
            pad = 0.16 * sin(two_pi * 130.81 * t) + 0.12 * sin(two_pi * 196.00 * t)
            tone = (0.65 * sin(two_pi * freq * t) + 0.20 * sin(two_pi * freq * 2.0 * t)) * attack * decay
            val = (tone * 0.42 + pad) * _envelope_loop(t, cycle_sec, 0.15)
            cycle_buf[i] = int(max(-32767.0, min(32767.0, val * 32767.0)))

    elif track_id == "builtin_study_ambient":
        for i in range(cycle_samples):
            t = i / sample_rate
            swell = 0.75 + 0.25 * sin(two_pi * (t / cycle_sec))
            val = (
                0.26 * sin(two_pi * 146.83 * t)
                + 0.22 * sin(two_pi * 220.00 * t + 0.4)
                + 0.18 * sin(two_pi * 277.18 * t + 1.1)
                + 0.16 * sin(two_pi * 329.63 * t + 1.9)
            ) * 0.55 * swell * _envelope_loop(t, cycle_sec, 0.2)
            cycle_buf[i] = int(max(-32767.0, min(32767.0, val * 32767.0)))

    elif track_id == "builtin_focus_concentration":
        for i in range(cycle_samples):
            t = i / sample_rate
            mod = 0.85 + 0.15 * sin(two_pi * 0.5 * t)
            val = (
                0.45 * sin(two_pi * 110.0 * t)
                + 0.30 * sin(two_pi * 165.0 * t)
                + 0.18 * sin(two_pi * 220.5 * t)
            ) * 0.55 * mod * _envelope_loop(t, cycle_sec, 0.2)
            cycle_buf[i] = int(max(-32767.0, min(32767.0, val * 32767.0)))

    elif track_id == "builtin_focus_minimal":
        lp = 0.0
        for i in range(cycle_samples):
            t = i / sample_rate
            lp = 0.985 * lp + 0.015 * rng.uniform(-1.0, 1.0)
            harmonic = 0.35 * sin(two_pi * 130.81 * t) + 0.25 * sin(two_pi * 196.00 * t)
            val = (harmonic + lp * 0.35) * 0.52 * _envelope_loop(t, cycle_sec, 0.2)
            cycle_buf[i] = int(max(-32767.0, min(32767.0, val * 32767.0)))

    elif track_id == "builtin_focus_shield":
        lp = 0.0
        for i in range(cycle_samples):
            t = i / sample_rate
            lp = 0.96 * lp + 0.04 * rng.uniform(-1.0, 1.0)
            bed = 0.30 * sin(two_pi * 146.83 * t) + 0.25 * sin(two_pi * 220.00 * t) + 0.20 * sin(two_pi * 293.66 * t)
            val = (bed * 0.65 + lp * 0.25) * 0.55 * _envelope_loop(t, cycle_sec, 0.2)
            cycle_buf[i] = int(max(-32767.0, min(32767.0, val * 32767.0)))

    elif track_id == "builtin_noise_brown":
        brown = 0.0
        for i in range(cycle_samples):
            t = i / sample_rate
            brown = (brown + 0.035 * rng.uniform(-1.0, 1.0)) * 0.992
            val = max(-0.95, min(0.95, brown * 1.45)) * 0.55 * _envelope_loop(t, cycle_sec, 0.15)
            cycle_buf[i] = int(max(-32767.0, min(32767.0, val * 32767.0)))

    elif track_id == "builtin_noise_white":
        prev = 0.0
        for i in range(cycle_samples):
            t = i / sample_rate
            prev = 0.65 * prev + 0.35 * rng.uniform(-1.0, 1.0)
            val = prev * 0.36 * _envelope_loop(t, cycle_sec, 0.15)
            cycle_buf[i] = int(max(-32767.0, min(32767.0, val * 32767.0)))

    elif track_id == "builtin_noise_pink":
        b0 = b1 = b2 = 0.0
        for i in range(cycle_samples):
            t = i / sample_rate
            white = rng.uniform(-1.0, 1.0)
            b0 = 0.99765 * b0 + white * 0.0990460
            b1 = 0.96300 * b1 + white * 0.2965164
            b2 = 0.57000 * b2 + white * 1.0526913
            pink = (b0 + b1 + b2 + white * 0.1848) * 0.14
            val = max(-0.95, min(0.95, pink)) * 0.45 * _envelope_loop(t, cycle_sec, 0.15)
            cycle_buf[i] = int(max(-32767.0, min(32767.0, val * 32767.0)))

    elif track_id == "builtin_nature_rain":
        lp1 = lp2 = drop_env = 0.0
        drop_freq = 900.0
        for i in range(cycle_samples):
            t = i / sample_rate
            white = rng.uniform(-1.0, 1.0)
            lp1 = 0.86 * lp1 + 0.14 * white
            lp2 = 0.97 * lp2 + 0.03 * white
            rain_bed = (lp1 - lp2 * 0.5) * 0.52
            if rng.random() < 0.002:
                drop_env = rng.uniform(0.08, 0.22)
                drop_freq = rng.uniform(650.0, 1350.0)
            drop_env *= 0.992
            val = (rain_bed + drop_env * sin(two_pi * drop_freq * t)) * 0.55 * _envelope_loop(t, cycle_sec, 0.15)
            cycle_buf[i] = int(max(-32767.0, min(32767.0, val * 32767.0)))

    elif track_id == "builtin_nature_forest":
        breeze = 0.0
        for i in range(cycle_samples):
            t = i / sample_rate
            breeze = 0.982 * breeze + 0.018 * rng.uniform(-1.0, 1.0)
            wind_swell = 0.55 + 0.45 * sin(two_pi * (t / cycle_sec))
            chime = (0.14 * sin(two_pi * 293.66 * t) + 0.10 * sin(two_pi * 440.00 * t)) * 0.6
            val = (breeze * 0.75 * wind_swell + chime) * 0.55 * _envelope_loop(t, cycle_sec, 0.2)
            cycle_buf[i] = int(max(-32767.0, min(32767.0, val * 32767.0)))

    else:
        surf = 0.0
        for i in range(cycle_samples):
            t = i / sample_rate
            white = rng.uniform(-1.0, 1.0)
            alpha = 0.02 + 0.05 * (0.5 + 0.5 * sin(two_pi * (t / cycle_sec)))
            surf = (1.0 - alpha) * surf + alpha * white
            tide_env = 0.35 + 0.65 * (0.5 + 0.5 * sin(two_pi * (t / cycle_sec) - math.pi / 2.0))
            val = (surf * tide_env * 0.85 + 0.12 * sin(two_pi * 82.41 * t)) * 0.58 * _envelope_loop(t, cycle_sec, 0.2)
            cycle_buf[i] = int(max(-32767.0, min(32767.0, val * 32767.0)))

    repeats = max(1, total_samples // cycle_samples)
    full_samples = array.array("h", cycle_buf * repeats)
    if len(full_samples) < total_samples:
        full_samples.extend(cycle_buf[: total_samples - len(full_samples)])

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(full_samples.tobytes())
    return buf.getvalue()


def get_or_create_builtin_wav_path(track_id: str) -> str:
    if track_id not in BUILTIN_TRACK_MAP:
        raise HTTPException(status_code=404, detail="Built-in audio track not found.")
    builtin_dir = os.path.join(AUDIO_DIR, "builtin")
    os.makedirs(builtin_dir, exist_ok=True)
    disk_path = os.path.join(builtin_dir, f"{track_id}.wav")
    if not os.path.isfile(disk_path) or os.path.getsize(disk_path) < 1024:
        wav_bytes = synthesize_builtin_wav_bytes(track_id)
        with open(disk_path, "wb") as f:
            f.write(wav_bytes)
    return disk_path


def _is_valid_mp3_bytes(data: bytes) -> bool:
    if len(data) < 16:
        return False
    if data.startswith(b"ID3"):
        return True
    # Scan first 512 bytes for a valid MPEG Audio frame sync word
    scan_limit = min(len(data) - 4, 512)
    for offset in range(scan_limit):
        b0 = data[offset]
        b1 = data[offset + 1]
        b2 = data[offset + 2]
        if b0 == 0xFF and (b1 & 0xE0) == 0xE0:
            version_bits = (b1 >> 3) & 0x03
            layer_bits = (b1 >> 1) & 0x03
            bitrate_idx = (b2 >> 4) & 0x0F
            sr_idx = (b2 >> 2) & 0x03
            if version_bits != 0x01 and layer_bits != 0x00 and bitrate_idx not in (0x00, 0x0F) and sr_idx != 0x03:
                return True
    return False


def _is_valid_wav_bytes(data: bytes) -> bool:
    if len(data) < 44:
        return False
    return data[:4] == b"RIFF" and data[8:12] == b"WAVE"


def _is_valid_ogg_bytes(data: bytes) -> bool:
    if len(data) < 28:
        return False
    return data[:4] == b"OggS"


def validate_uploaded_audio(
    filename: str,
    raw_bytes: bytes,
    content_type: Optional[str] = None,
) -> Tuple[str, str, str, float]:
    """
    Validate uploaded audio file extension, size, forbidden executable headers, and binary audio magic bytes.
    Returns (ext, file_format_label, mime_type, estimated_duration_seconds).
    """
    if not filename or not filename.strip():
        raise HTTPException(status_code=400, detail="Audio filename is required.")

    # Reject any path traversal patterns in raw filename
    base_name = os.path.basename(filename.strip().replace("\\", "/"))
    ext = os.path.splitext(base_name)[1].lower()
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Unsupported audio format. Only MP3 (.mp3), WAV (.wav), and OGG (.ogg) files are allowed.",
        )

    if not raw_bytes or len(raw_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded audio file is empty.")

    max_bytes = get_max_audio_upload_bytes()
    if len(raw_bytes) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Audio file exceeds the maximum allowed upload size of {format_upload_limit_label(max_bytes)}.",
        )

    head_lower = raw_bytes[:64].lstrip().lower()
    for sig in FORBIDDEN_SIGNATURES:
        if raw_bytes.startswith(sig) or head_lower.startswith(sig.lower()):
            raise HTTPException(
                status_code=400,
                detail="Invalid or unsafe file content detected. Executable or script files are strictly prohibited.",
            )

    fmt_label, canonical_mime = ALLOWED_UPLOAD_EXTENSIONS[ext]
    duration_sec = 0.0

    if ext == ".wav":
        if not _is_valid_wav_bytes(raw_bytes):
            raise HTTPException(
                status_code=400,
                detail="File content does not match a valid WAV audio header (RIFF/WAVE).",
            )
        try:
            with wave.open(io.BytesIO(raw_bytes), "rb") as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                if rate > 0 and frames > 0:
                    duration_sec = round(frames / float(rate), 2)
        except Exception:
            duration_sec = 0.0
    elif ext == ".ogg":
        if not _is_valid_ogg_bytes(raw_bytes):
            raise HTTPException(
                status_code=400,
                detail="File content does not match a valid OGG audio container header (OggS).",
            )
    elif ext == ".mp3":
        if not _is_valid_mp3_bytes(raw_bytes):
            raise HTTPException(
                status_code=400,
                detail="File content does not match a valid MP3 audio stream (ID3 or MPEG frame sync).",
            )

    _ = content_type
    return ext, fmt_label, canonical_mime, duration_sec


def sanitize_track_stem(raw_name: str) -> str:
    base = os.path.basename((raw_name or "track").replace("\\", "/"))
    stem = os.path.splitext(base)[0]
    cleaned = re.sub(r"[^a-zA-Z0-9_-]", "_", stem).strip("_")
    return (cleaned[:48] or "audio_track")


def get_user_audio_dir(user_id: str) -> str:
    safe_uid = re.sub(r"[^a-zA-Z0-9_-]", "", user_id)
    if not safe_uid:
        raise HTTPException(status_code=400, detail="Invalid user identifier.")
    user_dir = os.path.join(AUDIO_DIR, "user_uploads", safe_uid)
    os.makedirs(user_dir, exist_ok=True)
    return user_dir


def resolve_safe_user_track_path(user_id: str, storage_filename: str) -> str:
    user_dir = os.path.realpath(get_user_audio_dir(user_id))
    clean_file = os.path.basename(storage_filename.replace("\\", "/"))
    if not clean_file or clean_file != storage_filename or ".." in clean_file:
        raise HTTPException(status_code=400, detail="Invalid storage filename.")
    candidate = os.path.realpath(os.path.join(user_dir, clean_file))
    if not candidate.startswith(user_dir + os.sep):
        raise HTTPException(status_code=403, detail="Access outside user audio directory is forbidden.")
    return candidate


def format_uploaded_track_row(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "title": row["title"],
        "original_filename": row.get("original_filename") or "",
        "subtitle": f"{row.get('original_filename') or 'Audio'} · {row['file_format']} ({round(int(row.get('file_size') or 0) / 1024, 1)} KB)",
        "category": "uploaded",
        "category_label": "Personal Library",
        "file_format": row["file_format"],
        "mime_type": row["mime_type"],
        "file_size": int(row.get("file_size") or 0),
        "duration_seconds": float(row.get("duration_seconds") or 0.0),
        "is_builtin": False,
        "stream_url": f"/api/music/tracks/{row['id']}/stream",
        "created_at": row["created_at"],
    }


def list_music_library_for_user(conn: sqlite3.Connection, user_id: str) -> Dict[str, Any]:
    rows = conn.execute(
        """
        SELECT id, user_id, title, original_filename, storage_filename, file_format,
               mime_type, file_size, duration_seconds, category, created_at
        FROM user_music_tracks
        WHERE user_id = ?
        ORDER BY created_at DESC
        """,
        (user_id,),
    ).fetchall()

    uploaded_list = [format_uploaded_track_row(r) for r in rows]

    max_bytes = get_max_audio_upload_bytes()
    max_kb = max(1, round(max_bytes / 1024))
    max_mb = round(max_kb / 1000, 1) if max_kb % 1000 != 0 else int(max_kb // 1000)
    durable_mongo = _get_durable_audio_mongo_db() is not None
    return {
        "categories": [
            {
                "id": "uploaded",
                "name": "Personal Music Library",
                "description": "Your private uploaded MP3, WAV, and OGG audio tracks.",
            }
        ],
        "builtin_tracks": [],
        "uploaded_tracks": uploaded_list,
        "max_upload_bytes": max_bytes,
        "max_upload_kb": max_kb,
        "max_upload_mb": max_mb,
        "chunk_size_bytes": RECOMMENDED_UPLOAD_CHUNK_BYTES,
        "max_chunk_bytes": MAX_UPLOAD_CHUNK_BYTES,
        "storage_notice": (
            "Uploaded audio files are durably stored in MongoDB GridFS for your account."
            if durable_mongo
            else "Uploaded audio files are stored in authenticated per-user storage on disk."
        ),
    }


def _get_durable_audio_mongo_db():
    """Return the MongoDB database handle when MongoDB is authoritative (production/Vercel), else None."""
    if not is_mongo_authoritative():
        return None
    from backend.mongo_sync import get_mongo_database

    return get_mongo_database(require_configured=False)


def _store_audio_binary(
    track_id: str,
    user_id: str,
    storage_filename: str,
    mime_type: str,
    raw_bytes: bytes,
) -> None:
    """Persist finalized audio bytes to local cache and durable MongoDB GridFS (in production)."""
    disk_path = resolve_safe_user_track_path(user_id, storage_filename)
    with open(disk_path, "wb") as f:
        f.write(raw_bytes)

    mongo_db = _get_durable_audio_mongo_db()
    if mongo_db is not None:
        from gridfs import GridFS

        fs = GridFS(mongo_db, collection="music_audio_fs")
        for existing in fs.find({"metadata.track_id": track_id, "metadata.user_id": user_id}):
            fs.delete(existing._id)
        fs.put(
            raw_bytes,
            filename=storage_filename,
            contentType=mime_type,
            metadata={
                "track_id": track_id,
                "user_id": user_id,
                "storage_filename": storage_filename,
                "file_size": len(raw_bytes),
            },
        )


def _delete_durable_audio_binary(track_id: str, user_id: str) -> None:
    mongo_db = _get_durable_audio_mongo_db()
    if mongo_db is None:
        return
    try:
        from gridfs import GridFS

        fs = GridFS(mongo_db, collection="music_audio_fs")
        for existing in fs.find({"metadata.track_id": track_id, "metadata.user_id": user_id}):
            fs.delete(existing._id)
    except Exception:
        pass


def get_user_track_size_and_reader(
    user_id: str,
    storage_filename: str,
    track_id: str,
) -> Tuple[int, Optional[str], Optional[Any]]:
    """
    Resolve an uploaded track's total byte size and either a local disk path or a MongoDB GridFS GridOut handle.
    Raises HTTPException(404) if neither exists.
    """
    disk_path = resolve_safe_user_track_path(user_id, storage_filename)
    if os.path.isfile(disk_path):
        return os.path.getsize(disk_path), disk_path, None

    mongo_db = _get_durable_audio_mongo_db()
    if mongo_db is not None:
        from gridfs import GridFS

        fs = GridFS(mongo_db, collection="music_audio_fs")
        grid_out = fs.find_one({"metadata.track_id": track_id, "metadata.user_id": user_id})
        if grid_out is not None:
            return int(grid_out.length), None, grid_out

    raise HTTPException(
        status_code=404,
        detail="Uploaded audio binary is no longer present on storage. Please re-upload the track.",
    )


def save_uploaded_user_track(
    conn: sqlite3.Connection,
    user_id: str,
    original_filename: str,
    raw_bytes: bytes,
    title: Optional[str] = None,
    content_type: Optional[str] = None,
) -> Dict[str, Any]:
    ext, fmt_label, canonical_mime, duration_sec = validate_uploaded_audio(
        filename=original_filename,
        raw_bytes=raw_bytes,
        content_type=content_type,
    )
    track_id = new_id("mtrk")
    safe_stem = sanitize_track_stem(original_filename)
    storage_filename = f"{track_id}_{safe_stem}{ext}"

    display_title = (title or "").strip()
    if not display_title:
        raw_stem = os.path.splitext(os.path.basename(original_filename.replace("\\", "/")))[0].strip()
        display_title = re.sub(r"[_-]+", " ", raw_stem).strip() or "Uploaded Audio Track"
    display_title = display_title[:80]

    _store_audio_binary(
        track_id=track_id,
        user_id=user_id,
        storage_filename=storage_filename,
        mime_type=canonical_mime,
        raw_bytes=raw_bytes,
    )

    now = utc_now()
    conn.execute(
        """
        INSERT INTO user_music_tracks (
            id, user_id, title, original_filename, storage_filename,
            file_format, mime_type, file_size, duration_seconds, category, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'uploaded', ?)
        """,
        (
            track_id,
            user_id,
            display_title,
            os.path.basename(original_filename.replace("\\", "/"))[:120],
            storage_filename,
            fmt_label,
            canonical_mime,
            len(raw_bytes),
            duration_sec,
            now,
        ),
    )

    row = conn.execute(
        "SELECT * FROM user_music_tracks WHERE id = ? AND user_id = ?",
        (track_id, user_id),
    ).fetchone()
    return format_uploaded_track_row(row)


def _get_upload_session_dir(user_id: str, upload_id: str) -> str:
    safe_uid = re.sub(r"[^a-zA-Z0-9_-]", "", user_id)
    safe_upid = re.sub(r"[^a-zA-Z0-9_-]", "", upload_id)
    if not safe_uid or not safe_upid:
        raise HTTPException(status_code=400, detail="Invalid upload session identifier.")
    session_dir = os.path.join(AUDIO_DIR, "upload_sessions", safe_uid, safe_upid)
    os.makedirs(session_dir, exist_ok=True)
    return session_dir


def _cleanup_upload_session(conn: sqlite3.Connection, user_id: str, upload_id: str) -> None:
    import shutil

    safe_uid = re.sub(r"[^a-zA-Z0-9_-]", "", user_id)
    safe_upid = re.sub(r"[^a-zA-Z0-9_-]", "", upload_id)
    if safe_uid and safe_upid:
        session_dir = os.path.join(AUDIO_DIR, "upload_sessions", safe_uid, safe_upid)
        shutil.rmtree(session_dir, ignore_errors=True)

    mongo_db = _get_durable_audio_mongo_db()
    if mongo_db is not None:
        try:
            mongo_db["music_upload_chunks"].delete_many({"upload_id": upload_id, "user_id": user_id})
            mongo_db["music_upload_sessions"].delete_one({"id": upload_id, "user_id": user_id})
        except Exception:
            pass

    conn.execute(
        "DELETE FROM music_upload_sessions WHERE id = ? AND user_id = ?",
        (upload_id, user_id),
    )


def _load_upload_session(conn: sqlite3.Connection, user_id: str, upload_id: str) -> Dict[str, Any]:
    mongo_db = _get_durable_audio_mongo_db()
    if mongo_db is not None:
        doc = mongo_db["music_upload_sessions"].find_one({"id": upload_id})
        if not doc:
            raise HTTPException(status_code=404, detail="Upload session not found or expired.")
        if doc.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="You do not have permission to access this upload session.")
        return doc

    row = conn.execute(
        "SELECT * FROM music_upload_sessions WHERE id = ?",
        (upload_id,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Upload session not found or expired.")
    if row["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="You do not have permission to access this upload session.")
    return dict(row)


def init_chunked_audio_upload(
    conn: sqlite3.Connection,
    user_id: str,
    filename: str,
    file_size: int,
    total_chunks: int,
    title: Optional[str] = None,
    content_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Initialize a chunked audio upload session after validating filename, extension, and total file size."""
    if not filename or not filename.strip():
        raise HTTPException(status_code=400, detail="Audio filename is required.")

    base_name = os.path.basename(filename.strip().replace("\\", "/"))
    ext = os.path.splitext(base_name)[1].lower()
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Unsupported audio format. Only MP3 (.mp3), WAV (.wav), and OGG (.ogg) files are allowed.",
        )

    if file_size <= 0:
        raise HTTPException(status_code=400, detail="Uploaded audio file is empty.")

    max_bytes = get_max_audio_upload_bytes()
    if file_size > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Audio file exceeds the maximum allowed upload size of {format_upload_limit_label(max_bytes)}.",
        )

    if total_chunks < 1 or total_chunks > 128:
        raise HTTPException(status_code=400, detail="Invalid total chunk count for audio upload.")

    fmt_label, canonical_mime = ALLOWED_UPLOAD_EXTENSIONS[ext]
    upload_id = new_id("mup")
    now = utc_now()
    session_doc = {
        "id": upload_id,
        "user_id": user_id,
        "original_filename": base_name[:120],
        "title": (title or "").strip()[:80] or None,
        "content_type": content_type,
        "expected_size": int(file_size),
        "total_chunks": int(total_chunks),
        "ext": ext,
        "file_format": fmt_label,
        "mime_type": canonical_mime,
        "status": "pending",
        "created_at": now,
    }

    mongo_db = _get_durable_audio_mongo_db()
    if mongo_db is not None:
        mongo_db["music_upload_sessions"].insert_one(dict(session_doc))
    else:
        conn.execute(
            """
            INSERT INTO music_upload_sessions (
                id, user_id, original_filename, title, content_type,
                expected_size, total_chunks, ext, file_format, mime_type, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
            """,
            (
                upload_id,
                user_id,
                session_doc["original_filename"],
                session_doc["title"],
                content_type,
                int(file_size),
                int(total_chunks),
                ext,
                fmt_label,
                canonical_mime,
                now,
            ),
        )
        _get_upload_session_dir(user_id, upload_id)

    return {
        "upload_id": upload_id,
        "chunk_size_bytes": RECOMMENDED_UPLOAD_CHUNK_BYTES,
        "max_chunk_bytes": MAX_UPLOAD_CHUNK_BYTES,
        "max_upload_bytes": max_bytes,
        "max_upload_kb": max(1, round(max_bytes / 1024)),
    }


def save_audio_upload_chunk(
    conn: sqlite3.Connection,
    user_id: str,
    upload_id: str,
    chunk_index: int,
    raw_chunk: bytes,
) -> Dict[str, Any]:
    """Validate and persist a single chunk (< 4.5 MB Vercel limit) for an active upload session."""
    if not raw_chunk or len(raw_chunk) == 0:
        raise HTTPException(status_code=400, detail="Uploaded audio chunk is empty.")
    if len(raw_chunk) > MAX_UPLOAD_CHUNK_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Upload chunk exceeds the {MAX_UPLOAD_CHUNK_BYTES // (1024 * 1024)} MB per-request chunk limit.",
        )

    session = _load_upload_session(conn, user_id, upload_id)
    total_chunks = int(session["total_chunks"])
    if chunk_index < 0 or chunk_index >= total_chunks:
        raise HTTPException(status_code=400, detail="Chunk index out of range for upload session.")

    if chunk_index == 0:
        head_lower = raw_chunk[:64].lstrip().lower()
        for sig in FORBIDDEN_SIGNATURES:
            if raw_chunk.startswith(sig) or head_lower.startswith(sig.lower()):
                _cleanup_upload_session(conn, user_id, upload_id)
                raise HTTPException(
                    status_code=400,
                    detail="Invalid or unsafe file content detected. Executable or script files are strictly prohibited.",
                )

    max_bytes = get_max_audio_upload_bytes()
    mongo_db = _get_durable_audio_mongo_db()
    if mongo_db is not None:
        from bson.binary import Binary

        existing_chunks = list(
            mongo_db["music_upload_chunks"].find(
                {"upload_id": upload_id, "user_id": user_id},
                {"chunk_index": 1, "size": 1},
            )
        )
        other_bytes = sum(int(c.get("size") or 0) for c in existing_chunks if int(c.get("chunk_index", -1)) != chunk_index)
        if other_bytes + len(raw_chunk) > max_bytes:
            _cleanup_upload_session(conn, user_id, upload_id)
            raise HTTPException(
                status_code=413,
                detail=f"Audio file exceeds the maximum allowed upload size of {format_upload_limit_label(max_bytes)}.",
            )
        mongo_db["music_upload_chunks"].update_one(
            {"upload_id": upload_id, "user_id": user_id, "chunk_index": chunk_index},
            {
                "$set": {
                    "upload_id": upload_id,
                    "user_id": user_id,
                    "chunk_index": chunk_index,
                    "size": len(raw_chunk),
                    "data": Binary(raw_chunk),
                    "created_at": utc_now(),
                }
            },
            upsert=True,
        )
    else:
        session_dir = _get_upload_session_dir(user_id, upload_id)
        chunk_path = os.path.join(session_dir, f"chunk_{chunk_index:05d}.part")
        other_bytes = 0
        for fname in os.listdir(session_dir):
            if fname.startswith("chunk_") and fname.endswith(".part") and fname != f"chunk_{chunk_index:05d}.part":
                other_bytes += os.path.getsize(os.path.join(session_dir, fname))
        if other_bytes + len(raw_chunk) > max_bytes:
            _cleanup_upload_session(conn, user_id, upload_id)
            raise HTTPException(
                status_code=413,
                detail=f"Audio file exceeds the maximum allowed upload size of {format_upload_limit_label(max_bytes)}.",
            )
        with open(chunk_path, "wb") as f:
            f.write(raw_chunk)

    return {
        "upload_id": upload_id,
        "chunk_index": chunk_index,
        "received_bytes": len(raw_chunk),
    }


def complete_chunked_audio_upload(
    conn: sqlite3.Connection,
    user_id: str,
    upload_id: str,
) -> Dict[str, Any]:
    """Reassemble chunks, validate total reconstructed file size and audio headers, and finalize durable storage."""
    session = _load_upload_session(conn, user_id, upload_id)
    total_chunks = int(session["total_chunks"])
    expected_size = int(session["expected_size"])
    max_bytes = get_max_audio_upload_bytes()

    parts: List[bytes] = []
    mongo_db = _get_durable_audio_mongo_db()
    if mongo_db is not None:
        chunk_docs = {
            int(doc["chunk_index"]): bytes(doc["data"])
            for doc in mongo_db["music_upload_chunks"].find({"upload_id": upload_id, "user_id": user_id})
        }
        for idx in range(total_chunks):
            if idx not in chunk_docs:
                raise HTTPException(status_code=400, detail=f"Missing upload chunk {idx + 1} of {total_chunks}.")
            parts.append(chunk_docs[idx])
    else:
        session_dir = _get_upload_session_dir(user_id, upload_id)
        for idx in range(total_chunks):
            chunk_path = os.path.join(session_dir, f"chunk_{idx:05d}.part")
            if not os.path.isfile(chunk_path):
                raise HTTPException(status_code=400, detail=f"Missing upload chunk {idx + 1} of {total_chunks}.")
            with open(chunk_path, "rb") as f:
                parts.append(f.read())

    reconstructed = b"".join(parts)
    parts.clear()
    total_size = len(reconstructed)

    if total_size <= 0:
        _cleanup_upload_session(conn, user_id, upload_id)
        raise HTTPException(status_code=400, detail="Reconstructed audio file is empty.")

    if total_size > max_bytes:
        _cleanup_upload_session(conn, user_id, upload_id)
        raise HTTPException(
            status_code=413,
            detail=f"Audio file exceeds the maximum allowed upload size of {format_upload_limit_label(max_bytes)}.",
        )

    if total_size != expected_size:
        _cleanup_upload_session(conn, user_id, upload_id)
        raise HTTPException(
            status_code=400,
            detail=f"Reconstructed audio file size ({total_size} bytes) does not match expected size ({expected_size} bytes).",
        )

    try:
        track = save_uploaded_user_track(
            conn=conn,
            user_id=user_id,
            original_filename=session["original_filename"],
            raw_bytes=reconstructed,
            title=session.get("title"),
            content_type=session.get("content_type"),
        )
    finally:
        _cleanup_upload_session(conn, user_id, upload_id)

    return track


def abort_chunked_audio_upload(
    conn: sqlite3.Connection,
    user_id: str,
    upload_id: str,
) -> Dict[str, Any]:
    """Cancel an in-progress chunked upload and clean up its temporary chunks."""
    _load_upload_session(conn, user_id, upload_id)
    _cleanup_upload_session(conn, user_id, upload_id)
    return {"aborted": True, "upload_id": upload_id}


def delete_uploaded_user_track(conn: sqlite3.Connection, user_id: str, track_id: str) -> Dict[str, Any]:
    row = conn.execute(
        "SELECT * FROM user_music_tracks WHERE id = ?",
        (track_id,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Uploaded audio track not found.")
    if row["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="You do not have permission to delete this audio track.")

    storage_filename = row["storage_filename"]
    conn.execute(
        "DELETE FROM user_music_tracks WHERE id = ? AND user_id = ?",
        (track_id, user_id),
    )

    # Reset user's last selected track if it pointed to the deleted track
    conn.execute(
        """
        UPDATE user_preferences
        SET music_last_track_id = 'builtin_study_gentle', music_last_position = 0
        WHERE user_id = ? AND music_last_track_id = ?
        """,
        (user_id, track_id),
    )

    file_removed = False
    try:
        disk_path = resolve_safe_user_track_path(user_id, storage_filename)
        if os.path.isfile(disk_path):
            os.remove(disk_path)
            file_removed = True
    except Exception:
        file_removed = False

    _delete_durable_audio_binary(track_id, user_id)

    return {
        "deleted": True,
        "track_id": track_id,
        "file_removed": file_removed,
    }
