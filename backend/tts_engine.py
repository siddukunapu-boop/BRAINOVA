"""
BRAINOVA — Genuine Spoken Audio Synthesis Engine (Cloud TTS + Local Windows SAPI + Multi-Language PCM WAV Fallback)
Generates real playable .wav files from multi-speaker podcast scripts and video narration scripts across 6 languages:
English, Telugu (తెలుగు), Hindi (हिन्दी), Kannada (ಕನ್ನಡ), Tamil (தமிழ்), and Marathi (मराठी).
"""

import math
import os
import struct
import subprocess
import wave
from typing import Any, Dict, List, Optional

import httpx

from backend.database import AUDIO_DIR

LANGUAGE_CULTURE_MAP: Dict[str, str] = {
    "English": "en-US",
    "Telugu": "te-IN",
    "Hindi": "hi-IN",
    "Kannada": "kn-IN",
    "Tamil": "ta-IN",
    "Marathi": "mr-IN",
}


def _generate_fallback_speech_envelope_wav(
    output_path: str,
    dialogue: List[Dict[str, str]],
    target_duration_sec: Optional[int] = None,
) -> int:
    """
    Pure-Python harmonic speech-cadence WAV synthesizer used when neither Cloud TTS
    nor a matching culture voice in Windows SAPI produces non-silent audio.
    Ensures a valid, audible, playable WAV file always exists on disk.
    """
    sample_rate = 22050
    frames = bytearray()
    total_samples = 0

    turns = dialogue if dialogue else [{"speaker": "Narrator", "text": "BRAINOVA educational overview."}]
    per_turn_target = (
        max(1.5, min(6.0, float(target_duration_sec) / max(1, len(turns))))
        if target_duration_sec
        else None
    )

    for idx, turn in enumerate(turns):
        text = turn.get("spoken_text") or turn.get("text", "") or turn.get("narration", "") or "Educational concept explanation."
        speaker = turn.get("speaker", "Alex")
        base_freq = 165.0 if ("alex" in speaker.lower() or idx % 2 == 0) else 215.0
        words = text.split()
        duration_sec = per_turn_target if per_turn_target else min(4.2, max(1.2, len(words) * 0.15))
        num_samples = int(sample_rate * duration_sec)
        for s in range(num_samples):
            t = s / sample_rate
            syllable_env = 0.52 + 0.48 * math.sin(2.0 * math.pi * 4.4 * t)
            fade = min(1.0, s / 800.0, (num_samples - s) / 800.0)
            freq = base_freq + 16.0 * math.sin(2.0 * math.pi * 1.6 * t)
            val = (
                0.60 * math.sin(2.0 * math.pi * freq * t)
                + 0.25 * math.sin(2.0 * math.pi * (freq * 2.0) * t)
                + 0.15 * math.sin(2.0 * math.pi * (freq * 3.0) * t)
            )
            sample = int(max(-32767, min(32767, val * syllable_env * fade * 9200)))
            frames.extend(struct.pack("<h", sample))
        total_samples += num_samples
        pause_samples = int(sample_rate * 0.22)
        frames.extend(b"\x00\x00" * pause_samples)
        total_samples += pause_samples

    with wave.open(output_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(bytes(frames))

    return max(1, int(total_samples / sample_rate))


def synthesize_podcast_audio(
    output_id: str,
    dialogue: List[Dict[str, str]],
    openai_api_key: Optional[str] = None,
    language: str = "English",
    target_duration_sec: Optional[int] = None,
    require_native_voice: bool = False,
) -> Dict[str, Any]:
    """
    Synthesizes a real playable audio file (.wav) from a multi-speaker podcast or video narration script.
    Supports English, Telugu, Hindi, Kannada, Tamil, and Marathi.
    When `require_native_voice` is True, never silently falls back to English SAPI voices or synthetic
    beeps if native-language TTS is unavailable; reports an explicit structured error state instead.
    """
    os.makedirs(AUDIO_DIR, exist_ok=True)
    wav_filename = f"{output_id}.wav"
    output_path = os.path.join(AUDIO_DIR, wav_filename)
    culture = LANGUAGE_CULTURE_MAP.get(language)
    if not culture:
        return {
            "file_name": "",
            "file_path": "",
            "audio_url": "",
            "duration_seconds": 0,
            "language": language,
            "provider": "unavailable",
            "status": "unsupported_tts_language",
            "voice_supported": False,
            "error": f"Unsupported TTS language '{language}'.",
        }

    # 1. Try OpenAI TTS if configured (supports multilingual UTF-8 scripts natively)
    if openai_api_key and openai_api_key.strip():
        try:
            full_text = "\n\n".join(
                f"{turn.get('speaker', 'Host')}: {turn.get('spoken_text') or turn.get('text', '') or turn.get('narration', '')}"
                for turn in dialogue
            )[:3900]
            with httpx.Client(timeout=35.0) as client:
                resp = client.post(
                    "https://api.openai.com/v1/audio/speech",
                    headers={"Authorization": f"Bearer {openai_api_key.strip()}"},
                    json={
                        "model": "tts-1",
                        "voice": "alloy",
                        "input": full_text,
                        "response_format": "wav",
                    },
                )
                if resp.status_code == 200 and len(resp.content) > 1000:
                    with open(output_path, "wb") as f:
                        f.write(resp.content)
                    duration_sec = _get_wav_duration(output_path)
                    return {
                        "file_name": wav_filename,
                        "file_path": output_path,
                        "audio_url": f"/api/studio/audio/{output_id}.wav",
                        "duration_seconds": duration_sec,
                        "language": language,
                        "provider": "openai_tts_1",
                        "status": "ready",
                        "voice_supported": True,
                    }
        except Exception:
            pass

    # 2. Synthesize real spoken WAV using Windows SAPI (.NET System.Speech) with UTF-8 BOM for Indic scripts
    sapi_missing_native = False
    try:
        ps_script_path = os.path.join(AUDIO_DIR, f"tts_{output_id}.ps1")
        ps_lines = [
            "Add-Type -AssemblyName System.Speech",
            "$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer",
            "$synth.Rate = 0",
            "$installed = $synth.GetInstalledVoices() | Where-Object { $_.Enabled }",
            f"$cultureVoice = ($installed | Where-Object {{ $_.VoiceInfo.Culture.Name -eq '{culture}' }} | Select-Object -First 1)",
        ]
        if require_native_voice and language != "English":
            ps_lines.extend(
                [
                    "if (-not $cultureVoice) {",
                    "  $synth.Dispose()",
                    "  Write-Error 'NO_NATIVE_SAPI_VOICE'",
                    "  exit 42",
                    "}",
                ]
            )
        ps_lines.extend(
            [
                f"$synth.SetOutputToWaveFile('{output_path.replace(chr(39), chr(39)+chr(39))}')",
                "$voices = $installed | ForEach-Object { $_.VoiceInfo.Name }",
                "$voiceA = if ($cultureVoice) { $cultureVoice.VoiceInfo.Name } else { ($voices | Where-Object { $_ -match 'David' } | Select-Object -First 1) }",
                "$voiceB = if ($cultureVoice) { $cultureVoice.VoiceInfo.Name } else { ($voices | Where-Object { $_ -match 'Zira' } | Select-Object -First 1) }",
                "if (-not $voiceA) { $voiceA = $voices[0] }",
                "if (-not $voiceB) { $voiceB = $voices[-1] }",
                "$builder = New-Object System.Speech.Synthesis.PromptBuilder",
            ]
        )
        for idx, turn in enumerate(dialogue[:16]):
            speaker = turn.get("speaker", "Alex")
            # Prefer normalized spoken_text for TTS pronunciation while preserving visual `text` for transcript display
            raw_text = (turn.get("spoken_text") or turn.get("text") or turn.get("narration") or "").replace("'", "''").replace('"', "").replace("\n", " ").strip()
            if not raw_text:
                continue
            v_var = "$voiceA" if ("alex" in speaker.lower() or "host 1" in speaker.lower() or idx % 2 == 0) else "$voiceB"
            ps_lines.append(f"if ({v_var}) {{ $builder.StartVoice({v_var}) }}")
            ps_lines.append(f"$builder.AppendText('{raw_text}')")
            ps_lines.append("$builder.AppendBreak([System.TimeSpan]::FromMilliseconds(260))")
            ps_lines.append(f"if ({v_var}) {{ $builder.EndVoice() }}")

        ps_lines.append("$synth.Speak($builder)")
        ps_lines.append("$synth.SetOutputToNull()")
        ps_lines.append("$synth.Dispose()")

        # Write with UTF-8 BOM (utf-8-sig) so Windows PowerShell 5.1 reads Indic Unicode scripts cleanly
        with open(ps_script_path, "w", encoding="utf-8-sig") as f:
            f.write("\n".join(ps_lines))

        proc = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps_script_path],
            timeout=45,
            capture_output=True,
        )
        try:
            os.remove(ps_script_path)
        except OSError:
            pass

        if proc.returncode == 42:
            sapi_missing_native = True
        elif proc.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 4000:
            duration_sec = _get_wav_duration(output_path)
            if duration_sec >= 2:
                return {
                    "file_name": wav_filename,
                    "file_path": output_path,
                    "audio_url": f"/api/studio/audio/{output_id}.wav",
                    "duration_seconds": duration_sec,
                    "language": language,
                    "provider": "windows_sapi_neural_dual_voice",
                    "status": "ready",
                    "voice_supported": True,
                }
    except Exception:
        pass

    if require_native_voice:
        if language != "English" or sapi_missing_native:
            return {
                "file_name": "",
                "file_path": "",
                "audio_url": "",
                "duration_seconds": 0,
                "language": language,
                "provider": "unavailable",
                "status": "unsupported_tts_language",
                "voice_supported": False,
                "error": (
                    f"Native {language} ({culture}) speech synthesis is unavailable: "
                    f"no OpenAI TTS key is configured and no local Windows SAPI voice for {culture} is installed. "
                    "The generated transcript has been preserved."
                ),
            }
        return {
            "file_name": "",
            "file_path": "",
            "audio_url": "",
            "duration_seconds": 0,
            "language": language,
            "provider": "unavailable",
            "status": "failed",
            "voice_supported": False,
            "error": "Audio synthesis failed: neither OpenAI TTS nor local Windows SAPI produced playable speech. Transcript preserved.",
        }

    # 3. Fallback pure-Python WAV generator (used only when non-strict, e.g. video muxing track)
    duration_sec = _generate_fallback_speech_envelope_wav(output_path, dialogue, target_duration_sec=target_duration_sec)
    return {
        "file_name": wav_filename,
        "file_path": output_path,
        "audio_url": f"/api/studio/audio/{output_id}.wav",
        "duration_seconds": duration_sec,
        "language": language,
        "provider": "local_pcm_synthesizer",
        "status": "fallback_pcm",
        "voice_supported": False,
    }


def _get_wav_duration(path: str) -> int:
    try:
        with wave.open(path, "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            if rate > 0:
                return max(1, int(round(frames / float(rate))))
    except Exception:
        pass
    return 15
