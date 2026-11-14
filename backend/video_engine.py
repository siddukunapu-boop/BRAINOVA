"""
BRAINOVA — Genuine 1080p Playable Educational Video Synthesis & Validation Engine
Renders 1920x1080 HD educational slide & diagram frames (with full Unicode & Indic script support for
English, Telugu, Hindi, Kannada, Tamil, and Marathi via Segoe UI / Nirmala UI), synthesizes synchronized
voiceover narration (.wav), encodes a genuine 1080p H.264 (avc1) + AAC (mp4a) .mp4 file via Windows
Runtime MediaStreamSource + MediaTranscoder, and validates the resulting MP4 container, streams, codecs,
duration, and hardware/software decode before marking any video ready.
"""

import base64
import ctypes
import json
import os
import shutil
import struct
import subprocess
import time
import uuid
from typing import Any, Dict, List, Optional

from backend.database import AUDIO_DIR, VIDEOS_DIR
from backend.tts_engine import synthesize_podcast_audio


DURATION_TARGET_SECONDS: Dict[str, int] = {
    "1–3 minutes": 90,
    "1-3 minutes": 90,
    "3–5 minutes": 180,
    "3-5 minutes": 180,
    "5–10 minutes": 300,
    "5-10 minutes": 300,
    "10–15 minutes": 600,
    "10-15 minutes": 600,
}

_CONTAINER_BOXES = {
    b"moov",
    b"trak",
    b"mdia",
    b"minf",
    b"stbl",
    b"edts",
    b"dinf",
    b"udta",
    b"mvex",
}


def parse_target_duration_seconds(duration_label: str) -> int:
    if not duration_label:
        return 120
    for key, val in DURATION_TARGET_SECONDS.items():
        if key.lower() in duration_label.lower():
            return val
    return 120


class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_uint32),
        ("Data2", ctypes.c_uint16),
        ("Data3", ctypes.c_uint16),
        ("Data4", ctypes.c_ubyte * 8),
    ]

    @classmethod
    def from_uuid_str(cls, u_str: str) -> "_GUID":
        u = uuid.UUID(u_str)
        g = cls()
        ctypes.memmove(ctypes.byref(g), u.bytes_le, 16)
        return g


def _release_com_ptr(ptr: ctypes.c_void_p) -> None:
    if ptr and ptr.value:
        try:
            vtable = ctypes.cast(ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
            release_fn = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vtable[2])
            release_fn(ptr)
        except Exception:
            pass
        ptr.value = None


def _verify_mp4_decode_with_media_foundation(mp4_path: str) -> Dict[str, Any]:
    """
    Uses Windows Media Foundation (mfplat.dll + mfreadwrite.dll) IMFSourceReader to demux and
    decode both the H.264 video stream (to uncompressed NV12) and the AAC audio stream (to
    uncompressed PCM), proving the MP4 is genuinely playable by the operating system media pipeline.
    """
    if os.name != "nt":
        return {"decoder_verified": False, "error": "Windows Media Foundation requires Windows OS."}

    mfplat = ctypes.windll.mfplat
    mfreadwrite = ctypes.windll.mfreadwrite

    MF_VERSION = 0x00020070
    FIRST_VIDEO = 0xFFFFFFFC
    FIRST_AUDIO = 0xFFFFFFFD

    MF_MT_MAJOR_TYPE = _GUID.from_uuid_str("48eba18e-f8c9-4687-bf11-0a74c9f96a8f")
    MF_MT_SUBTYPE = _GUID.from_uuid_str("f7e34c9a-42e8-4714-b74b-cb29d72c35e5")
    MFMediaType_Video = _GUID.from_uuid_str("73646976-0000-0010-8000-00aa00389b71")
    MFMediaType_Audio = _GUID.from_uuid_str("73647561-0000-0010-8000-00aa00389b71")
    MFVideoFormat_NV12 = _GUID.from_uuid_str("3231564E-0000-0010-8000-00AA00389B71")
    MFAudioFormat_PCM = _GUID.from_uuid_str("00000001-0000-0010-8000-00aa00389b71")

    hr_startup = mfplat.MFStartup(MF_VERSION, 0)
    if hr_startup != 0:
        return {
            "decoder_verified": False,
            "error": f"MFStartup failed with HRESULT 0x{hr_startup & 0xFFFFFFFF:08x}",
        }

    reader = ctypes.c_void_p()
    v_mt = ctypes.c_void_p()
    a_mt = ctypes.c_void_p()
    try:
        abs_path = os.path.abspath(mp4_path)
        hr_open = mfreadwrite.MFCreateSourceReaderFromURL(
            ctypes.c_wchar_p(abs_path), None, ctypes.byref(reader)
        )
        if hr_open != 0 or not reader.value:
            return {
                "decoder_verified": False,
                "error": f"MFCreateSourceReaderFromURL rejected file (HRESULT 0x{hr_open & 0xFFFFFFFF:08x})",
            }

        vtable = ctypes.cast(reader, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        set_mt_fn = ctypes.WINFUNCTYPE(
            ctypes.c_long, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_void_p
        )(vtable[7])
        read_sample_fn = ctypes.WINFUNCTYPE(
            ctypes.c_long,
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_uint32),
            ctypes.POINTER(ctypes.c_uint32),
            ctypes.POINTER(ctypes.c_int64),
            ctypes.POINTER(ctypes.c_void_p),
        )(vtable[9])

        def _create_media_type(major: _GUID, sub: _GUID) -> ctypes.c_void_p:
            mt = ctypes.c_void_p()
            mfplat.MFCreateMediaType(ctypes.byref(mt))
            mvt = ctypes.cast(mt, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
            set_guid_fn = ctypes.WINFUNCTYPE(
                ctypes.c_long, ctypes.c_void_p, ctypes.POINTER(_GUID), ctypes.POINTER(_GUID)
            )(mvt[24])
            set_guid_fn(mt, ctypes.byref(MF_MT_MAJOR_TYPE), ctypes.byref(major))
            set_guid_fn(mt, ctypes.byref(MF_MT_SUBTYPE), ctypes.byref(sub))
            return mt

        v_mt = _create_media_type(MFMediaType_Video, MFVideoFormat_NV12)
        hr_vmt = set_mt_fn(reader, FIRST_VIDEO, None, v_mt)
        if hr_vmt != 0:
            return {
                "decoder_verified": False,
                "error": f"Video stream failed NV12 decoder negotiation (HRESULT 0x{hr_vmt & 0xFFFFFFFF:08x})",
            }

        a_mt = _create_media_type(MFMediaType_Audio, MFAudioFormat_PCM)
        hr_amt = set_mt_fn(reader, FIRST_AUDIO, None, a_mt)
        if hr_amt != 0:
            return {
                "decoder_verified": False,
                "error": f"Audio stream failed PCM decoder negotiation (HRESULT 0x{hr_amt & 0xFFFFFFFF:08x})",
            }

        decoded_video_bytes = 0
        for _ in range(8):
            actual_idx = ctypes.c_uint32()
            flags = ctypes.c_uint32()
            ts = ctypes.c_int64()
            sample = ctypes.c_void_p()
            shr = read_sample_fn(
                reader,
                FIRST_VIDEO,
                0,
                ctypes.byref(actual_idx),
                ctypes.byref(flags),
                ctypes.byref(ts),
                ctypes.byref(sample),
            )
            if shr != 0:
                _release_com_ptr(sample)
                return {
                    "decoder_verified": False,
                    "error": f"Video ReadSample failed (HRESULT 0x{shr & 0xFFFFFFFF:08x})",
                }
            if sample.value:
                try:
                    svt = ctypes.cast(sample, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
                    get_len_fn = ctypes.WINFUNCTYPE(
                        ctypes.c_long, ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)
                    )(svt[45])
                    total_len = ctypes.c_uint32()
                    if get_len_fn(sample, ctypes.byref(total_len)) == 0:
                        decoded_video_bytes = int(total_len.value)
                finally:
                    _release_com_ptr(sample)
                if decoded_video_bytes > 0:
                    break

        decoded_audio_bytes = 0
        for _ in range(8):
            actual_idx = ctypes.c_uint32()
            flags = ctypes.c_uint32()
            ts = ctypes.c_int64()
            sample = ctypes.c_void_p()
            shr = read_sample_fn(
                reader,
                FIRST_AUDIO,
                0,
                ctypes.byref(actual_idx),
                ctypes.byref(flags),
                ctypes.byref(ts),
                ctypes.byref(sample),
            )
            if shr != 0:
                _release_com_ptr(sample)
                return {
                    "decoder_verified": False,
                    "error": f"Audio ReadSample failed (HRESULT 0x{shr & 0xFFFFFFFF:08x})",
                }
            if sample.value:
                try:
                    svt = ctypes.cast(sample, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
                    get_len_fn = ctypes.WINFUNCTYPE(
                        ctypes.c_long, ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)
                    )(svt[45])
                    total_len = ctypes.c_uint32()
                    if get_len_fn(sample, ctypes.byref(total_len)) == 0:
                        decoded_audio_bytes = int(total_len.value)
                finally:
                    _release_com_ptr(sample)
                if decoded_audio_bytes > 0:
                    break

        if decoded_video_bytes <= 0 or decoded_audio_bytes <= 0:
            return {
                "decoder_verified": False,
                "error": f"Decoder produced empty samples (video_bytes={decoded_video_bytes}, audio_bytes={decoded_audio_bytes})",
            }

        return {
            "decoder_verified": True,
            "decoded_video_bytes": decoded_video_bytes,
            "decoded_audio_bytes": decoded_audio_bytes,
        }
    finally:
        _release_com_ptr(v_mt)
        _release_com_ptr(a_mt)
        _release_com_ptr(reader)
        mfplat.MFShutdown()


def validate_mp4_media_file(mp4_path: str) -> Dict[str, Any]:
    """
    Performs rigorous structural ISO BMFF parsing AND Windows Media Foundation stream decode
    validation on `mp4_path`. Never marks a file valid merely because it exists or exceeds a
    size threshold.
    """
    if not mp4_path or not os.path.isfile(mp4_path):
        return {"valid": False, "error": "MP4 file does not exist on disk."}

    try:
        file_size = os.path.getsize(mp4_path)
        if file_size < 512:
            return {"valid": False, "error": f"MP4 file is too small ({file_size} bytes)."}
        with open(mp4_path, "rb") as f:
            data = f.read()
    except OSError as exc:
        return {"valid": False, "error": f"Unable to read MP4 file: {exc}"}

    top_boxes: List[str] = []
    mdat_ranges: List[tuple[int, int]] = []
    moov_range: Optional[tuple[int, int]] = None

    pos = 0
    end = len(data)
    while pos + 8 <= end:
        size, btype = struct.unpack(">I4s", data[pos : pos + 8])
        hdr_len = 8
        if size == 1:
            if pos + 16 > end:
                return {"valid": False, "error": "Truncated 64-bit box header in MP4 container."}
            size = struct.unpack(">Q", data[pos + 8 : pos + 16])[0]
            hdr_len = 16
        elif size == 0:
            size = end - pos

        if size < hdr_len or pos + size > end:
            return {"valid": False, "error": f"Corrupt MP4 box boundary at offset {pos} (size={size})."}

        bname = btype.decode("ascii", errors="replace")
        top_boxes.append(bname)
        if btype == b"mdat":
            if size - hdr_len > 0:
                mdat_ranges.append((pos + hdr_len, pos + size))
        elif btype == b"moov":
            moov_range = (pos + hdr_len, pos + size)

        pos += size

    if pos != end:
        return {"valid": False, "error": "Trailing unparsed bytes at end of MP4 container."}

    if "ftyp" not in top_boxes or "moov" not in top_boxes or not mdat_ranges or not moov_range:
        return {
            "valid": False,
            "error": f"Missing required ISO BMFF top-level boxes (found={top_boxes}).",
        }

    mvhd_timescale = 0
    mvhd_duration_sec = 0.0
    tracks: List[Dict[str, Any]] = []

    def _iter_children(start_off: int, end_off: int):
        cur = start_off
        while cur + 8 <= end_off:
            sz, bt = struct.unpack(">I4s", data[cur : cur + 8])
            hl = 8
            if sz == 1:
                if cur + 16 > end_off:
                    break
                sz = struct.unpack(">Q", data[cur + 8 : cur + 16])[0]
                hl = 16
            elif sz == 0:
                sz = end_off - cur
            if sz < hl or cur + sz > end_off:
                break
            yield bt, cur + hl, cur + sz
            cur += sz

    def _parse_trak(t_start: int, t_end: int) -> Dict[str, Any]:
        t_info: Dict[str, Any] = {
            "handler_type": "",
            "codec": "",
            "width": 0,
            "height": 0,
            "sample_count": 0,
            "stts_entries": 0,
            "chunk_offsets": [],
        }
        for bt, c_start, c_end in _iter_children(t_start, t_end):
            payload = data[c_start:c_end]
            if bt == b"tkhd" and len(payload) >= 84:
                w_fixed, h_fixed = struct.unpack(">II", payload[-8:])
                t_info["width"] = int(w_fixed >> 16)
                t_info["height"] = int(h_fixed >> 16)
            elif bt == b"mdia":
                for mbt, m_start, m_end in _iter_children(c_start, c_end):
                    mpayload = data[m_start:m_end]
                    if mbt == b"hdlr" and len(mpayload) >= 12:
                        t_info["handler_type"] = mpayload[8:12].decode("ascii", errors="ignore")
                    elif mbt == b"minf":
                        for nbt, n_start, n_end in _iter_children(m_start, m_end):
                            if nbt == b"stbl":
                                for sbt, s_start, s_end in _iter_children(n_start, n_end):
                                    spayload = data[s_start:s_end]
                                    if sbt == b"stsd" and len(spayload) >= 16:
                                        _, fmt = struct.unpack(">I4s", spayload[8:16])
                                        t_info["codec"] = fmt.decode("ascii", errors="ignore").strip()
                                    elif sbt == b"stts" and len(spayload) >= 8:
                                        entry_cnt = struct.unpack(">I", spayload[4:8])[0]
                                        t_info["stts_entries"] = int(entry_cnt)
                                    elif sbt == b"stsz" and len(spayload) >= 12:
                                        sample_size, sample_cnt = struct.unpack(">II", spayload[4:12])
                                        t_info["sample_count"] = int(sample_cnt)
                                        if sample_size == 0 and sample_cnt > 0:
                                            if len(spayload) < 12 + sample_cnt * 4:
                                                t_info["sample_count"] = 0
                                    elif sbt == b"stco" and len(spayload) >= 8:
                                        cnt = struct.unpack(">I", spayload[4:8])[0]
                                        if len(spayload) >= 8 + cnt * 4:
                                            t_info["chunk_offsets"] = list(
                                                struct.unpack(f">{cnt}I", spayload[8 : 8 + cnt * 4])
                                            )
                                    elif sbt == b"co64" and len(spayload) >= 8:
                                        cnt = struct.unpack(">I", spayload[4:8])[0]
                                        if len(spayload) >= 8 + cnt * 8:
                                            t_info["chunk_offsets"] = list(
                                                struct.unpack(f">{cnt}Q", spayload[8 : 8 + cnt * 8])
                                            )
        return t_info

    for bt, c_start, c_end in _iter_children(moov_range[0], moov_range[1]):
        payload = data[c_start:c_end]
        if bt == b"mvhd" and len(payload) >= 20:
            ver = payload[0]
            if ver == 0:
                ts_val, dur_val = struct.unpack(">II", payload[12:20])
            elif len(payload) >= 32:
                ts_val, dur_val = struct.unpack(">IQ", payload[20:32])
            else:
                ts_val, dur_val = 0, 0
            mvhd_timescale = int(ts_val)
            if mvhd_timescale > 0:
                mvhd_duration_sec = float(dur_val) / float(mvhd_timescale)
        elif bt == b"trak":
            tracks.append(_parse_trak(c_start, c_end))

    if mvhd_timescale <= 0 or mvhd_duration_sec <= 0.0:
        return {"valid": False, "error": "Invalid or zero mvhd duration/timescale in MP4."}

    def _offsets_in_mdat(offsets: List[int]) -> bool:
        if not offsets:
            return False
        for off in offsets:
            if not any(m_start <= off < m_end for m_start, m_end in mdat_ranges):
                return False
        return True

    video_tracks = [
        t
        for t in tracks
        if t["handler_type"] == "vide"
        and t["codec"] in ("avc1", "h264", "hev1", "hvc1", "mp4v")
        and t["width"] > 0
        and t["height"] > 0
        and t["sample_count"] > 0
        and t["stts_entries"] > 0
        and _offsets_in_mdat(t["chunk_offsets"])
    ]
    audio_tracks = [
        t
        for t in tracks
        if t["handler_type"] == "soun"
        and t["codec"] in ("mp4a", "aac")
        and t["sample_count"] > 0
        and t["stts_entries"] > 0
        and _offsets_in_mdat(t["chunk_offsets"])
    ]

    if not video_tracks:
        return {
            "valid": False,
            "error": f"MP4 has no valid encoded video track (tracks={tracks}).",
        }
    if not audio_tracks:
        return {
            "valid": False,
            "error": f"MP4 has no valid encoded audio track (tracks={tracks}).",
        }

    v_trak = video_tracks[0]
    a_trak = audio_tracks[0]

    decode_check = _verify_mp4_decode_with_media_foundation(mp4_path)
    if not decode_check.get("decoder_verified"):
        return {
            "valid": False,
            "error": decode_check.get("error", "Media Foundation decode verification failed."),
        }

    return {
        "valid": True,
        "has_video_stream": True,
        "has_audio_stream": True,
        "video_codec": v_trak["codec"],
        "audio_codec": a_trak["codec"],
        "width": v_trak["width"],
        "height": v_trak["height"],
        "resolution": f"{v_trak['width']}x{v_trak['height']}",
        "duration_seconds": round(mvhd_duration_sec, 2),
        "video_sample_count": v_trak["sample_count"],
        "audio_sample_count": a_trak["sample_count"],
        "decoded_video_bytes": decode_check["decoded_video_bytes"],
        "decoded_audio_bytes": decode_check["decoded_audio_bytes"],
        "decoder_verified": True,
    }


def synthesize_educational_video(
    output_id: str,
    storyboard: Dict[str, Any],
    language: str = "English",
    duration_label: str = "3–5 minutes",
    style_label: str = "Concept Breakdown & Architecture",
    openai_api_key: Optional[str] = None,
    resume_audio_path: Optional[str] = None,
    progress_callback: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Generates a genuine playable 1080p .mp4 educational video file from the structured storyboard.
    1. Synthesizes synchronized spoken narration (.wav) across all scenes.
    2. Renders 1920x1080 HD visual slide & diagram PNG frames for each scene (plus a static thumbnail).
    3. Encodes a real H.264/AAC 1080p .mp4 file in VIDEOS_DIR using WinRT MediaStreamSource + MediaTranscoder.
    4. Validates the MP4 container structure, video/audio tracks, codecs, duration, and OS decoder playback.
    5. Raises RuntimeError if encoding or validation fails (never creates a fake PNG/WAV fallback container).
    """
    os.makedirs(VIDEOS_DIR, exist_ok=True)
    os.makedirs(AUDIO_DIR, exist_ok=True)

    scenes: List[Dict[str, Any]] = storyboard.get("scenes") or []
    if not scenes:
        scenes = [
            {
                "scene_number": 1,
                "title": storyboard.get("title", "BRAINOVA Video Overview"),
                "duration_sec": 15,
                "visual_direction": "Core Concept Architecture Diagram",
                "on_screen_text": "BRAINOVA — Learn Smarter. Think Bigger.",
                "narration": storyboard.get("summary", "Welcome to this BRAINOVA educational video overview."),
                "key_points": ["Core Concepts", "Architecture & Flow", "Practical Application"],
                "diagram_nodes": ["Input Source", "Core Mechanism", "Verified Output"],
            }
        ]

    # Build narration dialogue turns from scenes
    dialogue_turns: List[Dict[str, str]] = []
    for idx, sc in enumerate(scenes):
        narration_text = sc.get("narration") or sc.get("on_screen_text") or sc.get("title") or ""
        spoken_hint = sc.get("spoken_text") or narration_text
        dialogue_turns.append(
            {
                "speaker": "Alex" if idx % 2 == 0 else "Maya",
                "text": narration_text,
                "spoken_text": spoken_hint,
            }
        )

    if progress_callback:
        progress_callback("audio_synchronization", "Synthesizing & synchronizing native narration", 50)

    # Synthesize real spoken audio narration (.wav) with strict native-voice enforcement (or resume from valid WAV checkpoint)
    audio_meta: Dict[str, Any] = {}
    if resume_audio_path and os.path.exists(resume_audio_path) and os.path.getsize(resume_audio_path) > 1000:
        try:
            import wave as _wave
            with _wave.open(resume_audio_path, "rb") as _wf:
                _dur = _wf.getnframes() / float(_wf.getframerate() or 16000)
            audio_meta = {
                "file_path": resume_audio_path,
                "duration_seconds": max(4, int(round(_dur))),
                "voice_supported": True,
                "engine": "resumed_wav_checkpoint",
            }
        except Exception:
            audio_meta = {}

    if not audio_meta:
        audio_meta = synthesize_podcast_audio(
            output_id=f"{output_id}_vid",
            dialogue=dialogue_turns,
            openai_api_key=openai_api_key,
            language=language,
            require_native_voice=True,
        )
    if not audio_meta.get("file_path") or not audio_meta.get("voice_supported", True):
        raise RuntimeError(
            audio_meta.get("error")
            or f"Native-language voice synthesis is unavailable for {language}. Configure OpenAI TTS or install a {language} system voice."
        )
    wav_path = audio_meta["file_path"]
    actual_audio_sec = max(8, int(audio_meta.get("duration_seconds", 24)))

    # Prepare per-scene frame directory
    frames_dir = os.path.join(VIDEOS_DIR, f"frames_{output_id}")
    os.makedirs(frames_dir, exist_ok=True)
    mp4_filename = f"{output_id}.mp4"
    mp4_path = os.path.join(VIDEOS_DIR, mp4_filename)
    thumb_filename = f"{output_id}_thumb.png"
    thumb_path = os.path.join(VIDEOS_DIR, thumb_filename)

    if os.path.exists(mp4_path):
        try:
            os.remove(mp4_path)
        except OSError:
            pass

    # Narration-synchronized duration allocation proportional to spoken word count per scene
    weights = [
        max(8, len(str(sc.get("spoken_text") or sc.get("narration") or sc.get("title") or "").split()))
        for sc in scenes
    ]
    total_weight = max(1, sum(weights))
    min_sc_sec = 1 if len(scenes) > 24 else 4
    scene_durations = [
        max(min_sc_sec, int(round(actual_audio_sec * (w / total_weight))))
        for w in weights
    ]
    per_scene_sec = max(min_sc_sec, int(round(actual_audio_sec / max(1, len(scenes)))))

    # Write scene manifest JSON with UTF-8 encoding for the .NET 1080p frame renderer + WinRT MediaTranscoder encoder
    manifest_path = os.path.join(frames_dir, "manifest.json")
    manifest_data = {
        "title": storyboard.get("title", "BRAINOVA Video Overview"),
        "language": language,
        "duration_label": duration_label,
        "style_label": style_label,
        "wav_path": os.path.abspath(wav_path),
        "mp4_path": os.path.abspath(mp4_path),
        "thumb_path": os.path.abspath(thumb_path),
        "frames_dir": os.path.abspath(frames_dir),
        "per_scene_sec": per_scene_sec,
        "scenes": [
            {
                "scene_number": idx + 1,
                "total_scenes": len(scenes),
                "title": str(sc.get("title") or f"Scene {idx + 1}")[:90],
                "educational_objective": str(sc.get("educational_objective") or sc.get("on_screen_text") or "")[:120],
                "visual_mode": str(sc.get("visual_mode") or "diagram_flow")[:40],
                "source_citation": str(sc.get("source_citation") or "")[:90],
                "on_screen_text": str(sc.get("on_screen_text") or sc.get("title") or "")[:120],
                "narration": str(sc.get("narration") or "")[:230].rsplit(" ", 1)[0] if len(str(sc.get("narration") or "")) > 230 else str(sc.get("narration") or ""),
                "visual_direction": str(sc.get("visual_direction") or "System Flow Diagram")[:110],
                "key_points": [
                    (str(kp)[:135].rsplit(" ", 1)[0] + "..." if len(str(kp)) > 135 else str(kp))
                    for kp in (
                        sc.get("key_points")
                        or [sc.get("on_screen_text", ""), sc.get("visual_direction", "")]
                    )
                    if kp
                ][:4],
                "diagram_nodes": [
                    str(dn)[:42]
                    for dn in (
                        sc.get("diagram_nodes")
                        or ["1. Foundation", "2. Core Logic", "3. Synthesis", "4. Verification"]
                    )
                ][:4],
                "duration_sec": scene_durations[idx],
            }
            for idx, sc in enumerate(scenes)
        ],
    }

    with open(manifest_path, "w", encoding="utf-8") as mf:
        json.dump(manifest_data, mf, ensure_ascii=False, indent=2)

    ps_script_path = os.path.join(frames_dir, "render_video.ps1")
    ps_script = r"""
param([string]$ManifestPath)
$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Runtime.WindowsRuntime

[Windows.Media.Transcoding.MediaTranscoder, Windows.Media, ContentType=WindowsRuntime] | Out-Null
[Windows.Storage.Streams.InMemoryRandomAccessStream, Windows.Storage.Streams, ContentType=WindowsRuntime] | Out-Null
[Windows.Foundation.IAsyncAction, Windows.Foundation, ContentType=WindowsRuntime] | Out-Null

$jsonText = [System.IO.File]::ReadAllText($ManifestPath, [System.Text.Encoding]::UTF8)
$manifest = ConvertFrom-Json $jsonText

$rtDir = [System.Runtime.InteropServices.RuntimeEnvironment]::GetRuntimeDirectory()
$winMdDir = "C:\Windows\System32\WinMetadata"
$cp = New-Object System.CodeDom.Compiler.CompilerParameters
$cp.GenerateInMemory = $true
$null = $cp.ReferencedAssemblies.Add("System.dll")
$null = $cp.ReferencedAssemblies.Add("System.Core.dll")
$null = $cp.ReferencedAssemblies.Add((Join-Path $rtDir "System.Runtime.dll"))
$null = $cp.ReferencedAssemblies.Add((Join-Path $rtDir "System.Runtime.InteropServices.WindowsRuntime.dll"))
$null = $cp.ReferencedAssemblies.Add([System.Drawing.Bitmap].Assembly.Location)
$null = $cp.ReferencedAssemblies.Add((Join-Path $winMdDir "Windows.Foundation.winmd"))
$null = $cp.ReferencedAssemblies.Add((Join-Path $winMdDir "Windows.Media.winmd"))
$null = $cp.ReferencedAssemblies.Add((Join-Path $winMdDir "Windows.Storage.winmd"))

$csCode = @"
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.Drawing.Text;
using System.IO;
using System.Runtime.InteropServices;
using System.Threading;
using Windows.Foundation;
using Windows.Media.Core;
using Windows.Media.MediaProperties;
using Windows.Media.Transcoding;
using Windows.Storage;
using Windows.Storage.Streams;

public class SceneData
{
    public int SceneNumber;
    public int TotalScenes;
    public string Title;
    public string Objective;
    public string VisualMode;
    public string Citation;
    public string OnScreenText;
    public string Narration;
    public string[] KeyPoints;
    public string[] DiagramNodes;
    public int DurationSec;
}

public static class BrainovaWinRtMp4Encoder
{
    private const int FPS = 24;

    private static IBuffer BytesToIBuffer(byte[] data, int offset, int count)
    {
        DataWriter writer = new DataWriter();
        if (offset == 0 && count == data.Length)
        {
            writer.WriteBytes(data);
        }
        else
        {
            byte[] slice = new byte[count];
            System.Buffer.BlockCopy(data, offset, slice, 0, count);
            writer.WriteBytes(slice);
        }
        return writer.DetachBuffer();
    }

    private static T AwaitOp<T>(IAsyncOperation<T> op)
    {
        using (ManualResetEventSlim ev = new ManualResetEventSlim(false))
        {
            op.Completed = (info, status) => ev.Set();
            if (op.Status != AsyncStatus.Started) ev.Set();
            ev.Wait();
            if (op.Status == AsyncStatus.Error) throw op.ErrorCode;
            return op.GetResults();
        }
    }

    private static void AwaitActionProgress<TProgress>(IAsyncActionWithProgress<TProgress> op)
    {
        using (ManualResetEventSlim ev = new ManualResetEventSlim(false))
        {
            op.Completed = (info, status) => ev.Set();
            if (op.Status != AsyncStatus.Started) ev.Set();
            ev.Wait();
            if (op.Status == AsyncStatus.Error) throw op.ErrorCode;
            op.GetResults();
        }
    }

    private static float Clamp01(double v) { return (float)Math.Max(0.0, Math.Min(1.0, v)); }

    private static PointF Project3D(double x, double y, double z, double yaw, double pitch, float cx, float cy, double fov)
    {
        double cyaw = Math.Cos(yaw), syaw = Math.Sin(yaw);
        double x1 = x * cyaw - z * syaw;
        double z1 = x * syaw + z * cyaw;
        double cpitch = Math.Cos(pitch), spitch = Math.Sin(pitch);
        double y2 = y * cpitch - z1 * spitch;
        double z2 = y * spitch + z1 * cpitch + 420.0;
        double scale = fov / Math.Max(120.0, z2);
        return new PointF(cx + (float)(x1 * scale), cy + (float)(y2 * scale));
    }

    private static void DrawBiologyOrganelle3D(Graphics g, Rectangle stage, double p, Font lblFont, Font smallFont)
    {
        float cx = stage.X + stage.Width * 0.50f;
        float cy = stage.Y + stage.Height * 0.44f;
        double yaw = Math.Sin(p * Math.PI * 2.0) * 0.32;
        double pitch = 0.28 + Math.Cos(p * Math.PI * 2.0) * 0.08;

        // 3D Outer & Inner Chloroplast/Mitochondrial Envelope Cutaway
        using (Pen outerPen = new Pen(Color.FromArgb(220, 16, 185, 129), 4f))
        using (Pen innerPen = new Pen(Color.FromArgb(210, 52, 211, 153), 2.5f))
        using (SolidBrush stromaBrush = new SolidBrush(Color.FromArgb(60, 6, 95, 70)))
        {
            List<PointF> outerPts = new List<PointF>();
            List<PointF> innerPts = new List<PointF>();
            for (int a = 0; a < 36; a++)
            {
                double ang = (a / 36.0) * Math.PI * 2.0;
                double ox = Math.Cos(ang) * 235.0;
                double oy = Math.Sin(ang) * 115.0;
                outerPts.Add(Project3D(ox, oy, -15.0, yaw, pitch, cx, cy, 430.0));
                innerPts.Add(Project3D(ox * 0.86, oy * 0.82, 10.0, yaw, pitch, cx, cy, 430.0));
            }
            g.FillPolygon(stromaBrush, outerPts.ToArray());
            g.DrawPolygon(outerPen, outerPts.ToArray());
            g.DrawPolygon(innerPen, innerPts.ToArray());
        }

        // Stacked 3D Thylakoid Grana Discs (left)
        for (int stack = 0; stack < 2; stack++)
        {
            double sx = -110.0 + stack * 85.0;
            for (int disc = 0; disc < 4; disc++)
            {
                double dy = 38.0 - disc * 22.0;
                PointF center = Project3D(sx, dy, 18.0, yaw, pitch, cx, cy, 430.0);
                int w = 64, h = 20;
                using (SolidBrush dBrush = new SolidBrush(Color.FromArgb(215, 5, 150, 105)))
                using (Pen dPen = new Pen(Color.FromArgb(240, 110, 231, 183), 1.8f))
                {
                    g.FillEllipse(dBrush, center.X - w / 2f, center.Y - h / 2f, w, h);
                    g.DrawEllipse(dPen, center.X - w / 2f, center.Y - h / 2f, w, h);
                }
            }
        }

        // Animated Photon Rays + Electron Transport Flow
        double photonT = (p * 3.0) % 1.0;
        PointF sunStart = new PointF(stage.X + 46, stage.Y + 54);
        PointF granaHit = Project3D(-95, -10, 18, yaw, pitch, cx, cy, 430.0);
        using (Pen rayPen = new Pen(Color.FromArgb(200, 250, 204, 21), 2.5f))
        {
            rayPen.DashStyle = DashStyle.Dash;
            g.DrawLine(rayPen, sunStart, granaHit);
        }
        float px = sunStart.X + (granaHit.X - sunStart.X) * (float)photonT;
        float py = sunStart.Y + (granaHit.Y - sunStart.Y) * (float)photonT;
        using (SolidBrush phBrush = new SolidBrush(Color.FromArgb(255, 253, 224, 71)))
        {
            g.FillEllipse(phBrush, px - 7, py - 7, 14, 14);
        }

        // Animated Electron Transport Bridge (Thylakoids -> ATP / Calvin Cycle)
        PointF etcStart = Project3D(-25, 0, 18, yaw, pitch, cx, cy, 430.0);
        float rcx = cx + 125f, rcy = cy + 6f, rad = 64f;
        using (Pen etcPen = new Pen(Color.FromArgb(210, 167, 139, 250), 2.8f))
        {
            etcPen.DashStyle = DashStyle.Dot;
            g.DrawLine(etcPen, etcStart.X, etcStart.Y, rcx - rad, rcy);
        }
        double etcT = (p * 2.5) % 1.0;
        float etx = etcStart.X + (rcx - rad - etcStart.X) * (float)etcT;
        float ety = etcStart.Y + (rcy - etcStart.Y) * (float)etcT;
        using (SolidBrush etcB = new SolidBrush(Color.FromArgb(255, 196, 181, 253)))
        {
            g.FillEllipse(etcB, etx - 6, ety - 6, 12, 12);
        }

        // Animated Calvin / ATP Cycle Ring (right side of organelle)
        using (Pen ringPen = new Pen(Color.FromArgb(220, 56, 189, 248), 4f))
        {
            g.DrawEllipse(ringPen, rcx - rad, rcy - rad, rad * 2, rad * 2);
        }
        double eAng = p * Math.PI * 4.0;
        float ex = rcx + (float)(Math.Cos(eAng) * rad);
        float ey = rcy + (float)(Math.Sin(eAng) * rad);
        using (SolidBrush eBrush = new SolidBrush(Color.FromArgb(255, 56, 189, 248)))
        {
            g.FillEllipse(eBrush, ex - 9, ey - 9, 18, 18);
        }
        using (SolidBrush wBrush = new SolidBrush(Color.FromArgb(255, 240, 253, 250)))
        using (SolidBrush yBrush = new SolidBrush(Color.FromArgb(255, 253, 224, 71)))
        using (SolidBrush pBrush = new SolidBrush(Color.FromArgb(255, 196, 181, 253)))
        {
            g.DrawString("hv (Light)", smallFont, yBrush, stage.X + 26, stage.Y + 28);
            g.DrawString("Outer Membrane", smallFont, wBrush, cx - 70, cy - 160);
            g.DrawString("Thylakoids", smallFont, wBrush, stage.X + 58, cy + 78);
            g.DrawString("e- / ATP", smallFont, pBrush, etcStart.X + 12, etcStart.Y - 36);
            g.DrawString("Calvin Cycle", smallFont, wBrush, rcx - 46, rcy - 18);
            g.DrawString("CO2 -> Glucose", smallFont, yBrush, rcx - 56, rcy + 4);
            g.DrawString("3D Organelle Cutaway & Energy Cycle", lblFont, wBrush, stage.X + 22, stage.Bottom - 44);
        }
    }

    private static void DrawCSTreeAlgorithm(Graphics g, Rectangle stage, double p, Font lblFont, Font smallFont)
    {
        float cx = stage.X + stage.Width * 0.5f;
        float topY = stage.Y + 72f;
        // Animated B-Tree insertion / search-path highlight
        int step = Math.Min(3, (int)(p * 4.0));
        string[] keys = step < 2 ? new[] { "[20]", "[10 | 15]", "[25 | 30]", "[35]" }
                                 : new[] { "[20 | 30]", "[10 | 15]", "[25]", "[35 | 40]" };
        PointF rootPos = new PointF(cx, topY);
        PointF[] childPos = new[] {
            new PointF(cx - 190f, topY + 145f),
            new PointF(cx,        topY + 145f),
            new PointF(cx + 190f, topY + 145f)
        };

        for (int i = 0; i < 3; i++)
        {
            bool activeEdge = (i == step % 3);
            using (Pen edgePen = new Pen(activeEdge ? Color.FromArgb(255, 56, 189, 248) : Color.FromArgb(140, 99, 102, 241), activeEdge ? 4f : 2f))
            {
                g.DrawLine(edgePen, rootPos.X, rootPos.Y + 26, childPos[i].X, childPos[i].Y - 26);
            }
        }

        // Root node
        RectangleF rRect = new RectangleF(rootPos.X - 95, rootPos.Y - 26, 190, 52);
        using (SolidBrush nb = new SolidBrush(Color.FromArgb(240, 30, 41, 82)))
        using (Pen np = new Pen(Color.FromArgb(255, 56, 189, 248), 3f))
        using (SolidBrush tb = new SolidBrush(Color.White))
        {
            g.FillRectangle(nb, rRect);
            g.DrawRectangle(np, rRect.X, rRect.Y, rRect.Width, rRect.Height);
            g.DrawString(keys[0], lblFont, tb, rRect.X + 42, rRect.Y + 12);
        }

        for (int i = 0; i < 3; i++)
        {
            bool isTarget = (i == step % 3);
            RectangleF cRect = new RectangleF(childPos[i].X - 78, childPos[i].Y - 26, 156, 52);
            using (SolidBrush nb = new SolidBrush(isTarget ? Color.FromArgb(240, 14, 116, 144) : Color.FromArgb(230, 24, 34, 66)))
            using (Pen np = new Pen(isTarget ? Color.FromArgb(255, 103, 232, 249) : Color.FromArgb(180, 99, 102, 241), isTarget ? 3.5f : 2f))
            using (SolidBrush tb = new SolidBrush(Color.White))
            {
                g.FillRectangle(nb, cRect);
                g.DrawRectangle(np, cRect.X, cRect.Y, cRect.Width, cRect.Height);
                g.DrawString(keys[i + 1], smallFont, tb, cRect.X + 26, cRect.Y + 14);
            }
        }

        string statusTxt = step < 2 ? "Step 1-2: Traversing search path -> inserting key 40"
                                    : "Step 3-4: Leaf full -> Node Split promotes 30 to parent";
        using (SolidBrush cb = new SolidBrush(Color.FromArgb(255, 125, 211, 252)))
        {
            g.DrawString(statusTxt, smallFont, cb, stage.X + 26, stage.Bottom - 78);
            g.DrawString("Animated B-Tree Insertion, Split & Search Path", lblFont, Brushes.White, stage.X + 26, stage.Bottom - 44);
        }
    }

    private static void DrawEconomicsCurve(Graphics g, Rectangle stage, double p, Font lblFont, Font smallFont)
    {
        float ox = stage.X + 74f, oy = stage.Bottom - 88f;
        float aw = stage.Width - 130f, ah = stage.Height - 150f;
        using (Pen axisPen = new Pen(Color.FromArgb(220, 203, 213, 225), 2.5f))
        {
            g.DrawLine(axisPen, ox, oy - ah, ox, oy);
            g.DrawLine(axisPen, ox, oy, ox + aw, oy);
        }
        // Supply / Policy Curve (upward)
        using (Pen sPen = new Pen(Color.FromArgb(230, 52, 211, 153), 3.5f))
        {
            g.DrawLine(sPen, ox + 30, oy - 35, ox + aw - 35, oy - ah + 35);
        }
        // Demand Curve shifting with policy rate animation
        float shift = (float)(Math.Sin(p * Math.PI) * 95.0);
        using (Pen d1Pen = new Pen(Color.FromArgb(130, 148, 163, 184), 2.5f))
        using (Pen d2Pen = new Pen(Color.FromArgb(245, 56, 189, 248), 4f))
        {
            d1Pen.DashStyle = DashStyle.Dash;
            g.DrawLine(d1Pen, ox + 45, oy - ah + 40, ox + aw - 45, oy - 40);
            g.DrawLine(d2Pen, ox + 45 + shift, oy - ah + 40, ox + aw - 45 + shift, oy - 40);
        }
        float eqX = ox + aw * 0.5f + shift * 0.5f;
        float eqY = oy - ah * 0.5f - shift * 0.28f;
        using (SolidBrush eqBrush = new SolidBrush(Color.FromArgb(255, 250, 204, 21)))
        {
            g.FillEllipse(eqBrush, eqX - 9, eqY - 9, 18, 18);
        }
        using (SolidBrush tb = new SolidBrush(Color.FromArgb(255, 226, 232, 240)))
        {
            g.DrawString("Rate / Price", smallFont, tb, ox - 45, oy - ah - 26);
            g.DrawString("Aggregate Output / Demand", smallFont, tb, ox + aw - 220, oy + 10);
            g.DrawString("Animated Equilibrium & Policy Shift", lblFont, Brushes.White, stage.X + 26, stage.Bottom - 44);
        }
    }

    private static void DrawDiagramFlow(Graphics g, Rectangle stage, SceneData sc, double p, Font nodeFont, Font smallFont)
    {
        string[] nodes = (sc.DiagramNodes != null && sc.DiagramNodes.Length > 0)
            ? sc.DiagramNodes
            : new[] { "1. Concept", "2. Mechanism", "3. Evidence", "4. Synthesis" };
        int count = Math.Min(4, nodes.Length);
        int activeIdx = Math.Min(count - 1, (int)(p * count));
        int nodeY = stage.Y + 46;
        for (int i = 0; i < count; i++)
        {
            bool active = (i <= activeIdx);
            bool current = (i == activeIdx);
            Rectangle nRect = new Rectangle(stage.X + 44, nodeY, stage.Width - 88, 76);
            using (SolidBrush nb = new SolidBrush(current ? Color.FromArgb(245, 14, 116, 144) : (active ? Color.FromArgb(235, 24, 34, 66) : Color.FromArgb(140, 17, 24, 46))))
            using (Pen np = new Pen(current ? Color.FromArgb(255, 103, 232, 249) : Color.FromArgb(190, 56, 189, 248), current ? 3.5f : 2f))
            using (SolidBrush tb = new SolidBrush(active ? Color.White : Color.FromArgb(170, 148, 163, 184)))
            {
                g.FillRectangle(nb, nRect);
                g.DrawRectangle(np, nRect);
                g.DrawString(nodes[i], nodeFont, tb, new RectangleF(nRect.X + 18, nRect.Y + 20, nRect.Width - 36, 42));
            }
            if (i < count - 1)
            {
                int midX = stage.X + stage.Width / 2;
                using (Pen lp = new Pen(Color.FromArgb(220, 56, 189, 248), 3f))
                {
                    g.DrawLine(lp, midX, nodeY + 76, midX, nodeY + 114);
                }
                double pulse = (p * count) - i;
                if (pulse >= 0 && pulse <= 1)
                {
                    float py = nodeY + 76 + (float)(pulse * 38.0);
                    g.FillEllipse(Brushes.Cyan, midX - 6, py - 6, 12, 12);
                }
            }
            nodeY += 116;
        }
        using (SolidBrush sb = new SolidBrush(Color.FromArgb(255, 148, 163, 184)))
        {
            g.DrawString("Animated Concept Architecture", smallFont, sb, stage.X + 44, stage.Bottom - 36);
        }
    }

    private static void DrawHistoryTimeline(Graphics g, Rectangle stage, SceneData sc, double p, Font nodeFont, Font smallFont)
    {
        string[] nodes = (sc.DiagramNodes != null && sc.DiagramNodes.Length > 0)
            ? sc.DiagramNodes
            : new string[] { "1. Origins", "2. Turning Point", "3. Expansion", "4. Impact" };
        int count = Math.Min(4, nodes.Length);
        int yMid = stage.Y + stage.Height / 2;
        int xStart = stage.X + 56;
        int xEnd = stage.Right - 56;
        using (Pen trackPen = new Pen(Color.FromArgb(140, 148, 163, 184), 4f))
        using (Pen progPen = new Pen(Color.FromArgb(255, 251, 191, 36), 5f))
        {
            g.DrawLine(trackPen, xStart, yMid, xEnd, yMid);
            int activeX = xStart + (int)((xEnd - xStart) * Clamp01(p));
            g.DrawLine(progPen, xStart, yMid, activeX, yMid);
        }
        for (int i = 0; i < count; i++)
        {
            double frac = count == 1 ? 0.5 : (double)i / (count - 1);
            int nx = xStart + (int)((xEnd - xStart) * frac);
            bool active = p >= frac * 0.85;
            int boxY = (i % 2 == 0) ? (yMid - 140) : (yMid + 44);
            Rectangle card = new Rectangle(Math.Max(stage.X + 20, Math.Min(stage.Right - 220, nx - 100)), boxY, 200, 96);
            using (SolidBrush nb = new SolidBrush(active ? Color.FromArgb(240, 120, 53, 15) : Color.FromArgb(220, 22, 32, 60)))
            using (Pen np = new Pen(active ? Color.FromArgb(255, 251, 191, 36) : Color.FromArgb(150, 99, 102, 241), 2.5f))
            using (SolidBrush dotB = new SolidBrush(active ? Color.FromArgb(255, 251, 191, 36) : Color.FromArgb(255, 100, 116, 139)))
            {
                g.FillEllipse(dotB, nx - 10, yMid - 10, 20, 20);
                g.DrawLine(np, nx, yMid, nx, (i % 2 == 0) ? card.Bottom : card.Top);
                g.FillRectangle(nb, card);
                g.DrawRectangle(np, card);
                g.DrawString(nodes[i], smallFont, Brushes.White, new RectangleF(card.X + 10, card.Y + 12, card.Width - 20, 72));
            }
        }
        using (SolidBrush sb = new SolidBrush(Color.FromArgb(255, 251, 191, 36)))
        {
            g.DrawString("Chronological Timeline & Causal Progression", nodeFont, sb, stage.X + 28, stage.Bottom - 44);
        }
    }

    private static void DrawEquationDerivation(Graphics g, Rectangle stage, SceneData sc, double p, Font nodeFont, Font smallFont)
    {
        string[] steps = (sc.DiagramNodes != null && sc.DiagramNodes.Length > 0)
            ? sc.DiagramNodes
            : new string[] { "1. Given Form", "2. Transform", "3. Solve", "4. Result" };
        int count = Math.Min(4, steps.Length);
        int y = stage.Y + 46;
        for (int i = 0; i < count; i++)
        {
            bool active = p >= (double)i / Math.Max(1, count) * 0.75;
            Rectangle box = new Rectangle(stage.X + 44, y, stage.Width - 88, 92);
            using (SolidBrush fb = new SolidBrush(active ? Color.FromArgb(235, 30, 58, 138) : Color.FromArgb(190, 18, 25, 48)))
            using (Pen fp = new Pen(active ? Color.FromArgb(255, 56, 189, 248) : Color.FromArgb(110, 100, 116, 139), 2f))
            {
                g.FillRectangle(fb, box);
                g.DrawRectangle(fp, box);
                g.DrawString(steps[i], nodeFont, Brushes.White, new RectangleF(box.X + 18, box.Y + 24, box.Width - 36, 48));
            }
            if (i < count - 1)
            {
                using (Pen ap = new Pen(Color.FromArgb(220, 168, 85, 247), 3f))
                {
                    int mx = stage.X + stage.Width / 2;
                    g.DrawLine(ap, mx, y + 92, mx, y + 116);
                }
            }
            y += 118;
        }
        using (SolidBrush sb = new SolidBrush(Color.FromArgb(255, 125, 211, 252)))
        {
            g.DrawString("Step-by-Step Equation & Quantitative Derivation", smallFont, sb, stage.X + 44, stage.Bottom - 40);
        }
    }

    private static void DrawComparisonMatrix(Graphics g, Rectangle stage, SceneData sc, double p, Font nodeFont, Font smallFont)
    {
        string[] items = (sc.DiagramNodes != null && sc.DiagramNodes.Length > 0)
            ? sc.DiagramNodes
            : new string[] { "Approach A", "Approach B", "Key Difference", "Best Use Case" };
        int halfW = (stage.Width - 96) / 2;
        Rectangle leftCol = new Rectangle(stage.X + 36, stage.Y + 56, halfW, stage.Height - 130);
        Rectangle rightCol = new Rectangle(stage.X + 60 + halfW, stage.Y + 56, halfW, stage.Height - 130);
        using (SolidBrush lb = new SolidBrush(Color.FromArgb(220, 17, 46, 78)))
        using (SolidBrush rb = new SolidBrush(Color.FromArgb(220, 49, 28, 82)))
        using (Pen lp = new Pen(Color.FromArgb(255, 56, 189, 248), 2.5f))
        using (Pen rp = new Pen(Color.FromArgb(255, 192, 132, 252), 2.5f))
        {
            g.FillRectangle(lb, leftCol);
            g.DrawRectangle(lp, leftCol);
            g.FillRectangle(rb, rightCol);
            g.DrawRectangle(rp, rightCol);
            g.DrawString(items[0], nodeFont, Brushes.White, new RectangleF(leftCol.X + 16, leftCol.Y + 24, leftCol.Width - 32, 120));
            if (items.Length > 1)
                g.DrawString(items[1], nodeFont, Brushes.White, new RectangleF(rightCol.X + 16, rightCol.Y + 24, rightCol.Width - 32, 120));
            if (p > 0.35 && items.Length > 2)
                g.DrawString(items[2], smallFont, Brushes.LightCyan, new RectangleF(leftCol.X + 16, leftCol.Y + 180, leftCol.Width - 32, 140));
            if (p > 0.65 && items.Length > 3)
                g.DrawString(items[3], smallFont, Brushes.Thistle, new RectangleF(rightCol.X + 16, rightCol.Y + 180, rightCol.Width - 32, 140));
        }
        using (SolidBrush sb = new SolidBrush(Color.FromArgb(255, 192, 132, 252)))
        {
            g.DrawString("Structured Side-by-Side Comparison & Tradeoffs", smallFont, sb, stage.X + 36, stage.Bottom - 40);
        }
    }

    private static void DrawGeoConceptMap(Graphics g, Rectangle stage, SceneData sc, double p, Font nodeFont, Font smallFont)
    {
        string[] nodes = (sc.DiagramNodes != null && sc.DiagramNodes.Length > 0)
            ? sc.DiagramNodes
            : new string[] { "Hub", "Region A", "Region B", "Region C" };
        PointF center = new PointF(stage.X + stage.Width * 0.5f, stage.Y + stage.Height * 0.48f);
        PointF[] targets = new PointF[] {
            new PointF(stage.X + stage.Width * 0.22f, stage.Y + stage.Height * 0.25f),
            new PointF(stage.X + stage.Width * 0.78f, stage.Y + stage.Height * 0.25f),
            new PointF(stage.X + stage.Width * 0.50f, stage.Y + stage.Height * 0.78f),
        };
        using (Pen linkP = new Pen(Color.FromArgb(180, 56, 189, 248), 3f))
        using (SolidBrush pulseB = new SolidBrush(Color.FromArgb(255, 34, 211, 238)))
        {
            for (int i = 0; i < targets.Length; i++)
            {
                g.DrawLine(linkP, center, targets[i]);
                float t = (float)((p * 1.5 + i * 0.3) % 1.0);
                float px = center.X + (targets[i].X - center.X) * t;
                float py = center.Y + (targets[i].Y - center.Y) * t;
                g.FillEllipse(pulseB, px - 7, py - 7, 14, 14);
            }
        }
        using (SolidBrush hubB = new SolidBrush(Color.FromArgb(240, 30, 58, 138)))
        using (Pen hubP = new Pen(Color.FromArgb(255, 56, 189, 248), 2.5f))
        {
            Rectangle hRect = new Rectangle((int)center.X - 110, (int)center.Y - 36, 220, 72);
            g.FillRectangle(hubB, hRect);
            g.DrawRectangle(hubP, hRect);
            g.DrawString(nodes[0], smallFont, Brushes.White, new RectangleF(hRect.X + 10, hRect.Y + 14, 200, 48));
            for (int i = 0; i < Math.Min(3, nodes.Length - 1); i++)
            {
                Rectangle tRect = new Rectangle((int)targets[i].X - 105, (int)targets[i].Y - 32, 210, 64);
                g.FillRectangle(hubB, tRect);
                g.DrawRectangle(hubP, tRect);
                g.DrawString(nodes[i + 1], smallFont, Brushes.White, new RectangleF(tRect.X + 10, tRect.Y + 12, 190, 44));
            }
        }
        using (SolidBrush sb = new SolidBrush(Color.FromArgb(255, 125, 211, 252)))
        {
            g.DrawString("Spatial & Network Topology Concept Map", smallFont, sb, stage.X + 36, stage.Bottom - 40);
        }
    }

    private static void RenderSceneStaticBase(Bitmap staticBmp, Bitmap bgBmp, SceneData sc, string langName, Font titleFont, Font subHeaderFont, Font bodyFont, Font captionFont, Font badgeFont, Font nodeFont)
    {
        using (Graphics g = Graphics.FromImage(staticBmp))
        {
            g.SmoothingMode = SmoothingMode.AntiAlias;
            g.TextRenderingHint = TextRenderingHint.ClearTypeGridFit;
            g.CompositingMode = CompositingMode.SourceCopy;
            g.DrawImageUnscaled(bgBmp, 0, 0);
            g.CompositingMode = CompositingMode.SourceOver;

            using (SolidBrush hdrBg = new SolidBrush(Color.FromArgb(230, 10, 15, 30)))
            using (SolidBrush cyanB = new SolidBrush(Color.FromArgb(255, 56, 189, 248)))
            using (SolidBrush mutedB = new SolidBrush(Color.FromArgb(255, 175, 190, 225)))
            {
                g.FillRectangle(hdrBg, 0, 0, 1920, 88);
                g.DrawString("BRAINOVA  |  EDUCATIONAL DOCUMENTARY (1080p • 24 FPS)", subHeaderFont, cyanB, 64, 28);
                string badge = "LANG: " + langName.ToUpper() + "   •   SCENE " + sc.SceneNumber + " / " + sc.TotalScenes + "   •   " + sc.Citation;
                g.DrawString(badge, badgeFont, mutedB, 1140, 31);
            }

            g.DrawString(sc.Title, titleFont, Brushes.White, new RectangleF(64, 112, 1792, 68));
            using (SolidBrush objB = new SolidBrush(Color.FromArgb(255, 125, 211, 252)))
            {
                g.DrawString("Objective: " + sc.Objective, badgeFont, objB, new RectangleF(64, 180, 1792, 34));
            }

            Rectangle leftCard = new Rectangle(64, 226, 1020, 616);
            using (SolidBrush cardB = new SolidBrush(Color.FromArgb(215, 17, 24, 46)))
            using (Pen borderP = new Pen(Color.FromArgb(140, 79, 112, 229), 2f))
            using (SolidBrush cyanB = new SolidBrush(Color.FromArgb(255, 56, 189, 248)))
            {
                g.FillRectangle(cardB, leftCard);
                g.DrawRectangle(borderP, leftCard);
                g.DrawString("SOURCE-GROUNDED EXPLANATION", subHeaderFont, cyanB, 96, 256);
            }

            Rectangle calloutRect = new Rectangle(96, 722, 956, 92);
            using (SolidBrush nodeB = new SolidBrush(Color.FromArgb(235, 24, 34, 66)))
            using (Pen cyanP = new Pen(Color.FromArgb(220, 56, 189, 248), 2.5f))
            using (SolidBrush cyanB = new SolidBrush(Color.FromArgb(255, 125, 211, 252)))
            {
                g.FillRectangle(nodeB, calloutRect);
                g.DrawRectangle(cyanP, calloutRect);
                g.DrawString(sc.OnScreenText, nodeFont, cyanB, new RectangleF(116, 742, 916, 62));
            }

            Rectangle capRect = new Rectangle(64, 868, 1792, 156);
            using (SolidBrush capB = new SolidBrush(Color.FromArgb(230, 10, 15, 30)))
            using (Pen borderP = new Pen(Color.FromArgb(140, 79, 112, 229), 2f))
            using (SolidBrush cyanB = new SolidBrush(Color.FromArgb(255, 56, 189, 248)))
            {
                g.FillRectangle(capB, capRect);
                g.DrawRectangle(borderP, capRect);
                g.DrawString("SPOKEN NARRATION (" + langName + ")", badgeFont, cyanB, 92, 884);
                g.DrawString(sc.Narration, captionFont, Brushes.White, new RectangleF(92, 916, 1736, 96));
            }
        }
    }

    private static void BakeKeyPointIntoStatic(Bitmap staticBmp, SceneData sc, int kpIdx, Font bodyFont)
    {
        if (sc.KeyPoints == null || kpIdx < 0 || kpIdx >= sc.KeyPoints.Length) return;
        int yPos = 314 + kpIdx * 116;
        using (Graphics g = Graphics.FromImage(staticBmp))
        using (SolidBrush dotB = new SolidBrush(Color.FromArgb(255, 56, 189, 248)))
        {
            g.SmoothingMode = SmoothingMode.AntiAlias;
            g.TextRenderingHint = TextRenderingHint.ClearTypeGridFit;
            g.FillEllipse(dotB, 98, yPos + 10, 12, 12);
            g.DrawString(sc.KeyPoints[kpIdx], bodyFont, Brushes.White, new RectangleF(126, yPos, 930, 102));
        }
    }

    private static void RenderDynamicStageOnly(Graphics g, SceneData sc, double sceneProgress, double globalProgress, Font badgeFont, Font nodeFont, Font smallFont)
    {
        g.SmoothingMode = SmoothingMode.AntiAlias;
        g.TextRenderingHint = TextRenderingHint.ClearTypeGridFit;

        // Top 4px global progress bar
        using (SolidBrush cyanB = new SolidBrush(Color.FromArgb(255, 56, 189, 248)))
        {
            int progW = Math.Max(4, (int)(1920.0 * Clamp01(globalProgress)));
            g.FillRectangle(cyanB, 0, 84, progW, 4);
        }

        // Right Card: Subject-Specific 3D / Animated Visualization Stage
        Rectangle rightCard = new Rectangle(1116, 226, 740, 616);
        using (SolidBrush cardB = new SolidBrush(Color.FromArgb(255, 14, 21, 42)))
        using (Pen borderP = new Pen(Color.FromArgb(160, 56, 189, 248), 2f))
        {
            g.FillRectangle(cardB, rightCard);
            g.DrawRectangle(borderP, rightCard);
        }

        if (sc.VisualMode == "biology_organelle")
            DrawBiologyOrganelle3D(g, rightCard, sceneProgress, badgeFont, smallFont);
        else if (sc.VisualMode == "cs_tree_algorithm")
            DrawCSTreeAlgorithm(g, rightCard, sceneProgress, badgeFont, smallFont);
        else if (sc.VisualMode == "economics_curve")
            DrawEconomicsCurve(g, rightCard, sceneProgress, badgeFont, smallFont);
        else if (sc.VisualMode == "history_timeline")
            DrawHistoryTimeline(g, rightCard, sc, sceneProgress, nodeFont, smallFont);
        else if (sc.VisualMode == "equation_derivation")
            DrawEquationDerivation(g, rightCard, sc, sceneProgress, nodeFont, smallFont);
        else if (sc.VisualMode == "comparison_matrix")
            DrawComparisonMatrix(g, rightCard, sc, sceneProgress, nodeFont, smallFont);
        else if (sc.VisualMode == "geo_concept_map")
            DrawGeoConceptMap(g, rightCard, sc, sceneProgress, nodeFont, smallFont);
        else
            DrawDiagramFlow(g, rightCard, sc, sceneProgress, nodeFont, smallFont);
    }

    private static void RenderFrame(Graphics g, SceneData sc, double sceneProgress, double globalProgress, string langName, Font titleFont, Font subHeaderFont, Font bodyFont, Font captionFont, Font badgeFont, Font nodeFont, Font smallFont)
    {
        g.SmoothingMode = SmoothingMode.AntiAlias;
        g.TextRenderingHint = TextRenderingHint.ClearTypeGridFit;

        Rectangle fullRect = new Rectangle(0, 0, 1920, 1080);
        using (LinearGradientBrush grad = new LinearGradientBrush(fullRect, Color.FromArgb(255, 7, 10, 22), Color.FromArgb(255, 19, 14, 43), 35f))
        {
            g.FillRectangle(grad, fullRect);
        }

        // Top Header + Continuous 24fps Progress Bar
        using (SolidBrush hdrBg = new SolidBrush(Color.FromArgb(230, 10, 15, 30)))
        using (SolidBrush cyanB = new SolidBrush(Color.FromArgb(255, 56, 189, 248)))
        using (SolidBrush mutedB = new SolidBrush(Color.FromArgb(255, 175, 190, 225)))
        {
            g.FillRectangle(hdrBg, 0, 0, 1920, 88);
            g.DrawString("BRAINOVA  |  EDUCATIONAL DOCUMENTARY (1080p • 24 FPS)", subHeaderFont, cyanB, 64, 28);
            string badge = "LANG: " + langName.ToUpper() + "   •   SCENE " + sc.SceneNumber + " / " + sc.TotalScenes + "   •   " + sc.Citation;
            g.DrawString(badge, badgeFont, mutedB, 1140, 31);
            int progW = Math.Max(4, (int)(1920.0 * Clamp01(globalProgress)));
            g.FillRectangle(cyanB, 0, 84, progW, 4);
        }

        // Scene Title + Educational Objective Pill
        g.DrawString(sc.Title, titleFont, Brushes.White, new RectangleF(64, 112, 1792, 68));
        using (SolidBrush objB = new SolidBrush(Color.FromArgb(255, 125, 211, 252)))
        {
            g.DrawString("Objective: " + sc.Objective, badgeFont, objB, new RectangleF(64, 180, 1792, 34));
        }

        // Left Card: Progressive Key Points Reveal
        Rectangle leftCard = new Rectangle(64, 226, 1020, 616);
        using (SolidBrush cardB = new SolidBrush(Color.FromArgb(215, 17, 24, 46)))
        using (Pen borderP = new Pen(Color.FromArgb(140, 79, 112, 229), 2f))
        using (SolidBrush cyanB = new SolidBrush(Color.FromArgb(255, 56, 189, 248)))
        {
            g.FillRectangle(cardB, leftCard);
            g.DrawRectangle(borderP, leftCard);
            g.DrawString("SOURCE-GROUNDED EXPLANATION", subHeaderFont, cyanB, 96, 256);
        }

        int kpCount = sc.KeyPoints != null ? sc.KeyPoints.Length : 0;
        int yPos = 314;
        for (int i = 0; i < kpCount; i++)
        {
            double revealAt = (double)i / Math.Max(1, kpCount) * 0.65;
            if (sceneProgress >= revealAt)
            {
                using (SolidBrush dotB = new SolidBrush(Color.FromArgb(255, 56, 189, 248)))
                {
                    g.FillEllipse(dotB, 98, yPos + 10, 12, 12);
                    g.DrawString(sc.KeyPoints[i], bodyFont, Brushes.White, new RectangleF(126, yPos, 930, 102));
                }
            }
            yPos += 116;
        }

        Rectangle calloutRect = new Rectangle(96, 722, 956, 92);
        using (SolidBrush nodeB = new SolidBrush(Color.FromArgb(235, 24, 34, 66)))
        using (Pen cyanP = new Pen(Color.FromArgb(220, 56, 189, 248), 2.5f))
        using (SolidBrush cyanB = new SolidBrush(Color.FromArgb(255, 125, 211, 252)))
        {
            g.FillRectangle(nodeB, calloutRect);
            g.DrawRectangle(cyanP, calloutRect);
            g.DrawString(sc.OnScreenText, nodeFont, cyanB, new RectangleF(116, 742, 916, 62));
        }

        // Right Card: Subject-Specific 3D / Animated Visualization Stage
        Rectangle rightCard = new Rectangle(1116, 226, 740, 616);
        using (SolidBrush cardB = new SolidBrush(Color.FromArgb(220, 14, 21, 42)))
        using (Pen borderP = new Pen(Color.FromArgb(160, 56, 189, 248), 2f))
        {
            g.FillRectangle(cardB, rightCard);
            g.DrawRectangle(borderP, rightCard);
        }

        if (sc.VisualMode == "biology_organelle")
            DrawBiologyOrganelle3D(g, rightCard, sceneProgress, badgeFont, smallFont);
        else if (sc.VisualMode == "cs_tree_algorithm")
            DrawCSTreeAlgorithm(g, rightCard, sceneProgress, badgeFont, smallFont);
        else if (sc.VisualMode == "economics_curve")
            DrawEconomicsCurve(g, rightCard, sceneProgress, badgeFont, smallFont);
        else if (sc.VisualMode == "history_timeline")
            DrawHistoryTimeline(g, rightCard, sc, sceneProgress, nodeFont, smallFont);
        else if (sc.VisualMode == "equation_derivation")
            DrawEquationDerivation(g, rightCard, sc, sceneProgress, nodeFont, smallFont);
        else if (sc.VisualMode == "comparison_matrix")
            DrawComparisonMatrix(g, rightCard, sc, sceneProgress, nodeFont, smallFont);
        else if (sc.VisualMode == "geo_concept_map")
            DrawGeoConceptMap(g, rightCard, sc, sceneProgress, nodeFont, smallFont);
        else
            DrawDiagramFlow(g, rightCard, sc, sceneProgress, nodeFont, smallFont);

        // Bottom Narration Caption Bar
        Rectangle capRect = new Rectangle(64, 868, 1792, 156);
        using (SolidBrush capB = new SolidBrush(Color.FromArgb(230, 10, 15, 30)))
        using (Pen borderP = new Pen(Color.FromArgb(140, 79, 112, 229), 2f))
        using (SolidBrush cyanB = new SolidBrush(Color.FromArgb(255, 56, 189, 248)))
        {
            g.FillRectangle(capB, capRect);
            g.DrawRectangle(borderP, capRect);
            g.DrawString("SPOKEN NARRATION (" + langName + ")", badgeFont, cyanB, 92, 884);
            g.DrawString(sc.Narration, captionFont, Brushes.White, new RectangleF(92, 916, 1736, 96));
        }
    }

    public static string EncodeMp4(SceneData[] scenes, string langName, string framesDir, string thumbPath, string wavPath, string mp4Path)
    {
        Stopwatch sw = Stopwatch.StartNew();
        string fontFamily = "Nirmala UI";
        Font titleFont = new Font(fontFamily, 32f, FontStyle.Bold);
        Font subHeaderFont = new Font(fontFamily, 17f, FontStyle.Bold);
        Font bodyFont = new Font(fontFamily, 20f, FontStyle.Regular);
        Font captionFont = new Font(fontFamily, 19f, FontStyle.Italic);
        Font badgeFont = new Font(fontFamily, 14f, FontStyle.Bold);
        Font nodeFont = new Font(fontFamily, 17f, FontStyle.Bold);
        Font smallFont = new Font(fontFamily, 13.5f, FontStyle.Bold);

        List<double> sceneStartSec = new List<double>();
        List<double> sceneEndSec = new List<double>();
        double cumulativeSec = 0.0;
        for (int i = 0; i < scenes.Length; i++)
        {
            sceneStartSec.Add(cumulativeSec);
            int dur = scenes[i].DurationSec > 0 ? scenes[i].DurationSec : 12;
            cumulativeSec += dur;
            sceneEndSec.Add(cumulativeSec);
        }

        // Export 1 keyframe PNG per scene for chapter thumbnails & API compatibility
        using (Bitmap keyBmp = new Bitmap(1920, 1080, PixelFormat.Format32bppArgb))
        using (Graphics kg = Graphics.FromImage(keyBmp))
        {
            for (int i = 0; i < scenes.Length; i++)
            {
                double gp = (sceneStartSec[i] + (sceneEndSec[i] - sceneStartSec[i]) * 0.65) / Math.Max(1.0, cumulativeSec);
                RenderFrame(kg, scenes[i], 0.72, gp, langName, titleFont, subHeaderFont, bodyFont, captionFont, badgeFont, nodeFont, smallFont);
                string fp = Path.Combine(framesDir, "scene_" + (i + 1) + ".png");
                keyBmp.Save(fp, ImageFormat.Png);
                if (i == 0 && !string.IsNullOrEmpty(thumbPath)) keyBmp.Save(thumbPath, ImageFormat.Png);
            }
        }

        // Load WAV PCM bytes
        uint sampleRate = 24000, channels = 1, bitsPerSample = 16;
        byte[] pcmBytes = new byte[0];
        if (!string.IsNullOrEmpty(wavPath) && File.Exists(wavPath))
        {
            byte[] wavAll = File.ReadAllBytes(wavPath);
            if (wavAll.Length > 44)
            {
                channels = BitConverter.ToUInt16(wavAll, 22);
                sampleRate = BitConverter.ToUInt32(wavAll, 24);
                bitsPerSample = BitConverter.ToUInt16(wavAll, 34);
                int dataOffset = 12, dataLen = wavAll.Length - 44;
                while (dataOffset + 8 <= wavAll.Length)
                {
                    string chunkId = System.Text.Encoding.ASCII.GetString(wavAll, dataOffset, 4);
                    int chunkSize = BitConverter.ToInt32(wavAll, dataOffset + 4);
                    if (chunkId == "data") { dataOffset += 8; dataLen = Math.Min(chunkSize, wavAll.Length - dataOffset); break; }
                    dataOffset += 8 + chunkSize;
                }
                if (dataOffset < wavAll.Length && dataLen > 0)
                {
                    pcmBytes = new byte[dataLen];
                    System.Buffer.BlockCopy(wavAll, dataOffset, pcmBytes, 0, dataLen);
                }
            }
        }
        uint bytesPerSampleFrame = (channels * (bitsPerSample / 8));
        uint bytesPerSec = sampleRate * bytesPerSampleFrame;
        int totalPcmBytes = (int)(cumulativeSec * bytesPerSec);
        if (pcmBytes.Length < totalPcmBytes)
        {
            byte[] padded = new byte[totalPcmBytes];
            if (pcmBytes.Length > 0) System.Buffer.BlockCopy(pcmBytes, 0, padded, 0, pcmBytes.Length);
            pcmBytes = padded;
        }

        VideoEncodingProperties vProps = VideoEncodingProperties.CreateUncompressed(MediaEncodingSubtypes.Bgra8, 1920, 1080);
        vProps.FrameRate.Numerator = FPS;
        vProps.FrameRate.Denominator = 1;
        VideoStreamDescriptor vDesc = new VideoStreamDescriptor(vProps);
        AudioEncodingProperties aProps = AudioEncodingProperties.CreatePcm(sampleRate, channels, bitsPerSample);
        AudioStreamDescriptor aDesc = new AudioStreamDescriptor(aProps);

        MediaStreamSource mss = new MediaStreamSource(vDesc, aDesc);
        mss.Duration = TimeSpan.FromSeconds(cumulativeSec);
        mss.CanSeek = false;
        mss.BufferTime = TimeSpan.Zero;

        int totalFrames = (int)Math.Ceiling(cumulativeSec * FPS);
        int frameIdx = 0;
        double frameStepSec = 1.0 / FPS;
        int audioOffset = 0;
        int audioChunkBytes = (int)bytesPerSec;
        if (audioChunkBytes % (int)bytesPerSampleFrame != 0) audioChunkBytes -= (audioChunkBytes % (int)bytesPerSampleFrame);

        // Pre-render 1920x1080 gradient background ONCE + cached static scene base
        Bitmap bgBmp = new Bitmap(1920, 1080, PixelFormat.Format32bppArgb);
        using (Graphics bgG = Graphics.FromImage(bgBmp))
        using (LinearGradientBrush grad = new LinearGradientBrush(new Rectangle(0, 0, 1920, 1080), Color.FromArgb(255, 7, 10, 22), Color.FromArgb(255, 19, 14, 43), 35f))
        {
            bgG.FillRectangle(grad, new Rectangle(0, 0, 1920, 1080));
        }

        Bitmap staticSceneBmp = new Bitmap(1920, 1080, PixelFormat.Format32bppArgb);
        byte[] staticSceneBytes = new byte[1920 * 1080 * 4];
        int cachedSceneIdx = -1;
        int cachedRevealCount = 0;

        // Single reusable 1080p bitmap + byte buffer -> zero-copy AsBuffer!
        Bitmap streamBmp = new Bitmap(1920, 1080, PixelFormat.Format32bppArgb);
        Graphics streamG = Graphics.FromImage(streamBmp);
        byte[] frameBuf = new byte[1920 * 1080 * 4];

        mss.Starting += (sender, args) => { args.Request.SetActualStartPosition(TimeSpan.Zero); };
        mss.SampleRequested += (sender, args) =>
        {
            var req = args.Request;
            if (req.StreamDescriptor == vDesc)
            {
                if (frameIdx >= totalFrames) { req.Sample = null; return; }
                double t = frameIdx * frameStepSec;
                int sIdx = 0;
                for (int i = 0; i < sceneEndSec.Count; i++) { sIdx = i; if (t < sceneEndSec[i]) break; }
                double sDur = Math.Max(0.1, sceneEndSec[sIdx] - sceneStartSec[sIdx]);
                double sProg = Clamp01((t - sceneStartSec[sIdx]) / sDur);

                if (sIdx != cachedSceneIdx)
                {
                    cachedSceneIdx = sIdx;
                    cachedRevealCount = 0;
                    RenderSceneStaticBase(staticSceneBmp, bgBmp, scenes[sIdx], langName, titleFont, subHeaderFont, bodyFont, captionFont, badgeFont, nodeFont);
                    BitmapData sbd = staticSceneBmp.LockBits(new Rectangle(0, 0, 1920, 1080), ImageLockMode.ReadOnly, PixelFormat.Format32bppArgb);
                    Marshal.Copy(sbd.Scan0, staticSceneBytes, 0, staticSceneBytes.Length);
                    staticSceneBmp.UnlockBits(sbd);
                }

                int kpLen = scenes[sIdx].KeyPoints != null ? scenes[sIdx].KeyPoints.Length : 0;
                int targetReveal = 0;
                for (int k = 0; k < kpLen; k++)
                {
                    if (sProg >= ((double)k / Math.Max(1, kpLen) * 0.65)) targetReveal = k + 1;
                }
                if (targetReveal > cachedRevealCount)
                {
                    for (int k = cachedRevealCount; k < targetReveal; k++)
                    {
                        BakeKeyPointIntoStatic(staticSceneBmp, scenes[sIdx], k, bodyFont);
                    }
                    cachedRevealCount = targetReveal;
                    BitmapData sbd = staticSceneBmp.LockBits(new Rectangle(0, 0, 1920, 1080), ImageLockMode.ReadOnly, PixelFormat.Format32bppArgb);
                    Marshal.Copy(sbd.Scan0, staticSceneBytes, 0, staticSceneBytes.Length);
                    staticSceneBmp.UnlockBits(sbd);
                }

                BitmapData bdW = streamBmp.LockBits(new Rectangle(0, 0, 1920, 1080), ImageLockMode.WriteOnly, PixelFormat.Format32bppArgb);
                Marshal.Copy(staticSceneBytes, 0, bdW.Scan0, staticSceneBytes.Length);
                streamBmp.UnlockBits(bdW);

                RenderDynamicStageOnly(streamG, scenes[sIdx], sProg, t / Math.Max(1.0, cumulativeSec), badgeFont, nodeFont, smallFont);

                BitmapData bd = streamBmp.LockBits(new Rectangle(0, 0, 1920, 1080), ImageLockMode.ReadOnly, PixelFormat.Format32bppArgb);
                Marshal.Copy(bd.Scan0, frameBuf, 0, frameBuf.Length);
                streamBmp.UnlockBits(bd);

                MediaStreamSample samp = MediaStreamSample.CreateFromBuffer(BytesToIBuffer(frameBuf, 0, frameBuf.Length), TimeSpan.FromSeconds(t));
                samp.Duration = TimeSpan.FromSeconds(frameStepSec);
                samp.KeyFrame = (frameIdx % FPS == 0);
                req.Sample = samp;
                frameIdx++;
                if (frameIdx % 120 == 0)
                {
                    int pct = Math.Min(92, 68 + (int)(24.0 * frameIdx / Math.Max(1, totalFrames)));
                    Console.WriteLine("PROGRESS:" + pct);
                    GC.Collect(2, GCCollectionMode.Forced, true);
                }
            }
            else if (req.StreamDescriptor == aDesc)
            {
                if (audioOffset >= totalPcmBytes) { req.Sample = null; return; }
                int count = Math.Min(audioChunkBytes, totalPcmBytes - audioOffset);
                double audioTimeSec = (double)audioOffset / (double)bytesPerSec;
                double chunkDurSec = (double)count / (double)bytesPerSec;
                MediaStreamSample aSamp = MediaStreamSample.CreateFromBuffer(BytesToIBuffer(pcmBytes, audioOffset, count), TimeSpan.FromSeconds(audioTimeSec));
                aSamp.Duration = TimeSpan.FromSeconds(chunkDurSec);
                req.Sample = aSamp;
                audioOffset += count;
            }
        };

        MediaEncodingProfile profile = MediaEncodingProfile.CreateMp4(VideoEncodingQuality.HD1080p);
        profile.Video.FrameRate.Numerator = FPS;
        profile.Video.FrameRate.Denominator = 1;
        profile.Video.Bitrate = 3500000;
        MediaTranscoder transcoder = new MediaTranscoder();
        transcoder.HardwareAccelerationEnabled = true;

        using (InMemoryRandomAccessStream ras = new InMemoryRandomAccessStream())
        {
            var prepResult = AwaitOp(transcoder.PrepareMediaStreamSourceTranscodeAsync(mss, ras, profile));
            if (!prepResult.CanTranscode) throw new InvalidOperationException("Cannot transcode: " + prepResult.FailureReason.ToString());
            AwaitActionProgress(prepResult.TranscodeAsync());

            ras.Seek(0);
            uint size = (uint)ras.Size;
            DataReader reader = new DataReader(ras);
            AwaitOp(reader.LoadAsync(size));
            byte[] mp4Bytes = new byte[size];
            reader.ReadBytes(mp4Bytes);
            File.WriteAllBytes(mp4Path, mp4Bytes);
        }

        staticSceneBmp.Dispose(); bgBmp.Dispose();
        streamG.Dispose(); streamBmp.Dispose();
        titleFont.Dispose(); subHeaderFont.Dispose(); bodyFont.Dispose(); captionFont.Dispose();
        badgeFont.Dispose(); nodeFont.Dispose(); smallFont.Dispose();
        sw.Stop();
        long peakMb = Process.GetCurrentProcess().PeakWorkingSet64 / (1024 * 1024);
        return string.Format("METRICS:fps={0};frames={1};sec={2:F2};peak_mb={3}", FPS, frameIdx, sw.Elapsed.TotalSeconds, peakMb);
    }
}
"@

$provider = New-Object Microsoft.CSharp.CSharpCodeProvider
$cr = $provider.CompileAssemblyFromSource($cp, $csCode)
if ($cr.Errors.HasErrors) {
    $errMessages = ($cr.Errors | ForEach-Object { $_.ToString() }) -join "; "
    throw ("CSharp WinRT encoder compilation failed: " + $errMessages)
}

$sceneList = New-Object System.Collections.Generic.List[SceneData]
foreach ($sc in $manifest.scenes) {
    $sd = New-Object SceneData
    $sd.SceneNumber = [int]$sc.scene_number
    $sd.TotalScenes = [int]$sc.total_scenes
    $sd.Title = [string]$sc.title
    $sd.Objective = [string]$sc.educational_objective
    $sd.VisualMode = [string]$sc.visual_mode
    $sd.Citation = [string]$sc.source_citation
    $sd.OnScreenText = [string]$sc.on_screen_text
    $sd.Narration = [string]$sc.narration
    $sd.KeyPoints = @($sc.key_points | ForEach-Object { [string]$_ })
    $sd.DiagramNodes = @($sc.diagram_nodes | ForEach-Object { [string]$_ })
    $sd.DurationSec = [int]$sc.duration_sec
    $sceneList.Add($sd)
}

$metrics = [BrainovaWinRtMp4Encoder]::EncodeMp4($sceneList.ToArray(), [string]$manifest.language, $manifest.frames_dir, $manifest.thumb_path, $manifest.wav_path, $manifest.mp4_path)
Write-Output $metrics
Write-Output "RENDER_SUCCESS:winrt_media_transcoder_h264_aac_24fps"
"""

    with open(ps_script_path, "w", encoding="utf-8-sig") as pf:
        pf.write(ps_script)

    provider = "winrt_media_transcoder_h264_aac"
    encode_error = ""
    render_metrics: Dict[str, Any] = {"fps": 24}
    try:
        if progress_callback:
            progress_callback(
                "visual_rendering",
                f"Rendering {len(scenes)} adaptive scenes at 1080p 24 FPS & encoding MP4",
                68,
            )

        encode_timeout = max(300, int(actual_audio_sec * 4))
        proc = subprocess.Popen(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                ps_script_path,
                "-ManifestPath",
                manifest_path,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="ignore",
        )
        stdout_lines: List[str] = []
        deadline = time.monotonic() + encode_timeout
        try:
            assert proc.stdout is not None
            for line in proc.stdout:
                line = line.rstrip("\r\n")
                stdout_lines.append(line)
                if line.startswith("PROGRESS:") and progress_callback:
                    try:
                        pct_val = int(line.split(":", 1)[1].strip())
                        progress_callback(
                            "mp4_encoding",
                            f"Encoding continuous 1080p 24 FPS MP4 ({len(scenes)} scenes)",
                            pct_val,
                        )
                    except ValueError:
                        pass
                if time.monotonic() > deadline:
                    proc.kill()
                    raise RuntimeError(f"Video encoding exceeded timeout ({encode_timeout}s).")
            rem_time = max(5, int(deadline - time.monotonic()))
            ret_code = proc.wait(timeout=rem_time)
            stderr_txt = proc.stderr.read() if proc.stderr else ""
        finally:
            if proc.stdout:
                proc.stdout.close()
            if proc.stderr:
                proc.stderr.close()
        if ret_code != 0:
            raise subprocess.CalledProcessError(ret_code, "powershell", output="\n".join(stdout_lines), stderr=stderr_txt)

        for line in stdout_lines:
            if line.startswith("METRICS:"):
                for kv in line[len("METRICS:"):].split(";"):
                    if "=" in kv:
                        k, v = kv.split("=", 1)
                        try:
                            render_metrics[k.strip()] = float(v) if "." in v else int(v)
                        except ValueError:
                            render_metrics[k.strip()] = v.strip()
    except subprocess.CalledProcessError as exc:
        err_msg = (exc.stderr or "").strip() if isinstance(exc.stderr, str) else (exc.stderr or b"").decode("utf-8", errors="ignore").strip()
        out_msg = (exc.output or "").strip() if isinstance(exc.output, str) else (exc.output or b"").decode("utf-8", errors="ignore").strip()
        encode_error = err_msg or out_msg or f"PowerShell exited with status {exc.returncode}"
    except Exception as exc:
        encode_error = f"{type(exc).__name__}: {exc}"

    # Capture 1920x1080 PNG slide frames as structured objects with `image_data_url` before cleanup
    slide_frames: List[Dict[str, Any]] = []
    for idx, sc_meta in enumerate(manifest_data["scenes"], start=1):
        fp = os.path.join(frames_dir, f"scene_{idx}.png")
        if os.path.exists(fp):
            try:
                with open(fp, "rb") as img_f:
                    b64 = base64.b64encode(img_f.read()).decode("ascii")
                    slide_frames.append(
                        {
                            "scene_number": idx,
                            "title": sc_meta.get("title", f"Scene {idx}"),
                            "duration_sec": sc_meta.get("duration_sec", per_scene_sec),
                            "image_data_url": f"data:image/png;base64,{b64}",
                        }
                    )
            except Exception:
                pass

    thumbnail_data_url = slide_frames[0]["image_data_url"] if slide_frames else ""

    # Clean up temporary frames directory after encoding
    shutil.rmtree(frames_dir, ignore_errors=True)

    if encode_error:
        if os.path.exists(mp4_path):
            try:
                os.remove(mp4_path)
            except OSError:
                pass
        raise RuntimeError(f"WinRT 1080p MP4 video encoding failed: {encode_error}")

    if not slide_frames:
        if os.path.exists(mp4_path):
            try:
                os.remove(mp4_path)
            except OSError:
                pass
        raise RuntimeError("1080p slide frame rendering failed: no scene frames were generated.")

    if progress_callback:
        progress_callback("final_validation", "Validating final MP4 container, codecs & playback tracks", 94)

    validation = validate_mp4_media_file(mp4_path)
    if not validation.get("valid"):
        if os.path.exists(mp4_path):
            try:
                os.remove(mp4_path)
            except OSError:
                pass
        raise RuntimeError(
            f"Generated MP4 failed media stream validation: {validation.get('error', 'Invalid MP4 container or streams.')}"
        )

    total_duration_sec = sum(int(s.get("duration_sec", per_scene_sec)) for s in manifest_data["scenes"])
    verified_duration_sec = int(round(validation.get("duration_seconds") or total_duration_sec)) or total_duration_sec
    is_ready = bool(validation.get("valid") and validation.get("decoder_verified"))

    return {
        "file_name": mp4_filename,
        "file_path": mp4_path,
        "video_url": f"/api/studio/video/{output_id}.mp4",
        "audio_url": f"/api/studio/audio/{output_id}_vid.wav",
        "audio_file_path": wav_path,
        "thumbnail_path": thumb_path if os.path.exists(thumb_path) else "",
        "thumbnail_data_url": thumbnail_data_url,
        "slide_frames": slide_frames,
        "duration_seconds": verified_duration_sec,
        "duration_label": duration_label,
        "style_label": style_label,
        "language": language,
        "resolution": validation.get("resolution", "1920x1080"),
        "resolution_label": "1920x1080 (1080p Full HD)",
        "video_codec": validation.get("video_codec", "avc1"),
        "audio_codec": validation.get("audio_codec", "mp4a"),
        "fps": render_metrics.get("fps", 24),
        "render_metrics": render_metrics,
        "provider": provider,
        "ready": is_ready,
        "video_ready": is_ready,
    }
