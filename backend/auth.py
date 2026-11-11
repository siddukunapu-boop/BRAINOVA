"""
AetherLearn AI — Authentication, Session Management, and Server-Side Ownership Guards
"""

import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Header, Request, status

from backend.database import get_db, new_id, utc_now

def _load_jwt_secret() -> str:
    """Use an explicitly configured signing key, or create a private local one for development."""
    configured = os.environ.get("AETHER_JWT_SECRET", "").strip()
    if configured:
        if len(configured) < 32:
            raise RuntimeError("AETHER_JWT_SECRET must contain at least 32 characters.")
        return configured

    if os.environ.get("AETHER_ENV", "development").strip().lower() == "production":
        raise RuntimeError("AETHER_JWT_SECRET must be configured when AETHER_ENV=production.")

    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    os.makedirs(data_dir, exist_ok=True)
    secret_path = os.path.join(data_dir, ".aether_jwt_secret")
    try:
        secret_bytes = secrets.token_urlsafe(48).encode("utf-8")
        descriptor = os.open(secret_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        try:
            os.write(descriptor, secret_bytes)
        finally:
            os.close(descriptor)
        return secret_bytes.decode("utf-8")
    except FileExistsError:
        with open(secret_path, "r", encoding="utf-8") as secret_file:
            secret = secret_file.read().strip()
        if len(secret) < 32:
            raise RuntimeError(f"The local signing key at {secret_path} is invalid; replace it or set AETHER_JWT_SECRET.")
        return secret


JWT_SECRET = _load_jwt_secret()
JWT_ALGORITHM = "HS256"
JWT_EXP_HOURS = 168  # 7 days
MEDIA_TOKEN_EXP_MINUTES = 30


def hash_password(plain_password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(plain_password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


def create_access_token(user_id: str, email: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "email": email,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=JWT_EXP_HOURS)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> Dict[str, Any]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired. Please sign in again.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token.")


def create_audio_playback_token(user_id: str, output_id: str) -> str:
    """Create a short-lived token that can read one user's one saved audio output."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "scope": "studio_audio",
        "output_id": output_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=MEDIA_TOKEN_EXP_MINUTES)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_audio_playback_token(token: str, output_id: str) -> str:
    """Validate a media-only token and return its owner ID."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Audio playback link is invalid or expired.")

    if payload.get("scope") != "studio_audio" or payload.get("output_id") != output_id or not payload.get("sub"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Audio playback link is invalid or expired.")
    return payload["sub"]


def create_video_playback_token(user_id: str, output_id: str) -> str:
    """Create a short-lived token that can stream one user's saved video output."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "scope": "studio_video",
        "output_id": output_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=MEDIA_TOKEN_EXP_MINUTES)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_video_playback_token(token: str, output_id: str) -> str:
    """Validate a video playback token and return its owner ID."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Video playback link is invalid or expired.")

    if payload.get("scope") != "studio_video" or payload.get("output_id") != output_id or not payload.get("sub"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Video playback link is invalid or expired.")
    return payload["sub"]


def ensure_user_preferences(conn, user_id: str) -> Dict[str, Any]:
    row = conn.execute("SELECT * FROM user_preferences WHERE user_id = ?", (user_id,)).fetchone()
    if not row:
        now = utc_now()
        conn.execute(
            """
            INSERT INTO user_preferences (
                user_id, ai_provider, gemini_model, openai_model, anthropic_model,
                default_skill_level, study_hours_per_week, auto_generate_policy,
                show_demo_data, reduced_motion, updated_at
            ) VALUES (?, 'auto', 'gemini-2.5-flash', 'gpt-4o-mini', 'claude-3-5-sonnet-latest', 'Intermediate', 12, 'all_async', 0, 0, ?)
            """,
            (user_id, now),
        )
        row = conn.execute("SELECT * FROM user_preferences WHERE user_id = ?", (user_id,)).fetchone()
    return row


def sanitize_preferences_for_client(pref: Dict[str, Any]) -> Dict[str, Any]:
    """Never expose raw API keys in client-readable responses."""
    env_gemini = bool(os.environ.get("GEMINI_API_KEY", "").strip())
    env_openai = bool(os.environ.get("OPENAI_API_KEY", "").strip())
    env_anthropic = bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())
    env_youtube = bool(os.environ.get("YOUTUBE_DATA_API_KEY", "").strip())
    env_eleven = bool(os.environ.get("ELEVENLABS_API_KEY", "").strip())
    env_video = bool(os.environ.get("VIDEO_PROVIDER_API_KEY", "").strip())

    has_gemini = bool(pref.get("gemini_api_key", "").strip()) or env_gemini
    has_openai = bool(pref.get("openai_api_key", "").strip()) or env_openai
    has_anthropic = bool(pref.get("anthropic_api_key", "").strip()) or env_anthropic
    has_youtube = bool(pref.get("youtube_api_key", "").strip()) or env_youtube
    has_eleven = bool(pref.get("elevenlabs_api_key", "").strip()) or env_eleven
    has_video = bool(pref.get("video_provider_key", "").strip()) or env_video

    return {
        "user_id": pref["user_id"],
        "ai_provider": pref.get("ai_provider", "auto"),
        "gemini_model": pref.get("gemini_model", "gemini-2.5-flash"),
        "openai_model": pref.get("openai_model", "gpt-4o-mini"),
        "anthropic_model": pref.get("anthropic_model", "claude-3-5-sonnet-latest"),
        "default_skill_level": pref.get("default_skill_level", "Intermediate"),
        "study_hours_per_week": pref.get("study_hours_per_week", 12),
        "auto_generate_policy": pref.get("auto_generate_policy", "all_async"),
        "show_demo_data": bool(pref.get("show_demo_data", 0)),
        "reduced_motion": bool(pref.get("reduced_motion", 0)),
        "theme": pref.get("theme") or "neural_night",
        "preferred_language": pref.get("preferred_language") or "English",
        "credentials_status": {
            "gemini_configured": has_gemini,
            "openai_configured": has_openai,
            "anthropic_configured": has_anthropic,
            "any_llm_configured": has_gemini or has_openai or has_anthropic,
            "youtube_api_configured": has_youtube,
            "elevenlabs_configured": has_eleven,
            "local_sapi_tts_available": True,
            "video_provider_configured": has_video,
            "local_video_renderer_available": True,
        },
        "updated_at": pref.get("updated_at", ""),
    }


def get_current_user(
    request: Request,
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    token: Optional[str] = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    elif request.query_params.get("token"):
        token = request.query_params.get("token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in.",
        )

    payload = decode_access_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload.")

    with get_db(commit=True) as conn:
        user = conn.execute(
            "SELECT id, email, name, role, target_role, bio, avatar_color, avatar_url, created_at, updated_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account no longer exists.")
        prefs = ensure_user_preferences(conn, user_id)
        user["preferences"] = sanitize_preferences_for_client(prefs)
        return user

