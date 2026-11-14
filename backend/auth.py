"""
BRAINOVA — Authentication, Persistent Session Revocation, Credential Encryption Boundary,
Scoped Media Tokens, and Server-Side Ownership Guards
"""

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Header, Request, status

from backend.crypto import (
    CREDENTIAL_COLUMNS,
    CredentialEncryptionError,
    CredentialKeyUnavailableError,
    decrypt_credential,
    encrypt_credential,
    is_encrypted_credential,
    mask_credential,
)
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
            raise RuntimeError(
                f"The local signing key at {secret_path} is invalid; replace it or set AETHER_JWT_SECRET."
            )
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


def _token_revocation_id(token: str, payload: Dict[str, Any]) -> str:
    """Returns the unique `jti` claim or a SHA-256 digest for legacy tokens issued without `jti`."""
    jti = payload.get("jti")
    if jti and isinstance(jti, str):
        return jti
    return "sha256:" + hashlib.sha256(token.encode("utf-8")).hexdigest()


def is_token_revoked(jti: str) -> bool:
    """Checks the persistent SQLite `revoked_tokens` table to see if a session token was revoked."""
    if not jti:
        return False
    try:
        with get_db(commit=False) as conn:
            table_exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='revoked_tokens'"
            ).fetchone()
            if not table_exists:
                return False
            row = conn.execute("SELECT jti FROM revoked_tokens WHERE jti = ?", (jti,)).fetchone()
            return bool(row)
    except Exception:
        return False


def create_access_token(
    user_id: str,
    email: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    now = datetime.now(timezone.utc)
    exp_dt = now + (expires_delta if expires_delta is not None else timedelta(hours=JWT_EXP_HOURS))
    payload = {
        "sub": user_id,
        "email": email,
        "jti": new_id("jti"),
        "scope": "session",
        "iat": int(now.timestamp()),
        "exp": int(exp_dt.timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str, check_revocation: bool = True) -> Dict[str, Any]:
    if not token or not isinstance(token, str):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
        )
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired. Please sign in again.",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
        )

    # Prevent narrow media playback tokens from ever being used as general session tokens
    token_scope = payload.get("scope")
    if token_scope not in (None, "session"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Scoped media token cannot be used for API authentication.",
        )

    if check_revocation:
        rev_id = _token_revocation_id(token, payload)
        if is_token_revoked(rev_id):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session has been logged out or revoked. Please sign in again.",
            )

    return payload


def revoke_access_token(token: str, expected_user_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Revokes the caller's active JWT session token persistently in SQLite (`revoked_tokens`).
    Enforces that a user can only revoke their own session token.
    """
    payload = decode_access_token(token, check_revocation=False)
    token_owner = payload.get("sub")
    if not token_owner:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload.")

    if expected_user_id and token_owner != expected_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot revoke a session belonging to another user.",
        )

    rev_id = _token_revocation_id(token, payload)
    exp_ts = int(payload.get("exp") or (int(datetime.now(timezone.utc).timestamp()) + 3600))
    now_ts = int(datetime.now(timezone.utc).timestamp())
    now_iso = utc_now()

    with get_db(commit=True) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS revoked_tokens (
                jti TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                expires_at INTEGER NOT NULL,
                revoked_at TEXT NOT NULL
            )
            """
        )
        # Prune already-expired tokens to keep table compact
        conn.execute("DELETE FROM revoked_tokens WHERE expires_at < ?", (now_ts,))
        conn.execute(
            """
            INSERT OR REPLACE INTO revoked_tokens (jti, user_id, expires_at, revoked_at)
            VALUES (?, ?, ?, ?)
            """,
            (rev_id, token_owner, exp_ts, now_iso),
        )

    return {"jti": rev_id, "user_id": token_owner, "revoked_at": now_iso}


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
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["exp", "sub", "scope", "output_id"]},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Audio playback link is invalid or expired.",
        )

    if (
        payload.get("scope") != "studio_audio"
        or payload.get("output_id") != output_id
        or not payload.get("sub")
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Audio playback link is invalid or expired.",
        )
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
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["exp", "sub", "scope", "output_id"]},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Video playback link is invalid or expired.",
        )

    if (
        payload.get("scope") != "studio_video"
        or payload.get("output_id") != output_id
        or not payload.get("sub")
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Video playback link is invalid or expired.",
        )
    return payload["sub"]


def encrypt_user_preference_credentials(user_id: str, updates: Dict[str, str]) -> Dict[str, str]:
    """
    Encrypts any non-empty API credential updates using AES-256-GCM bound to `user_id:column_name`
    before writing to SQLite.
    """
    encrypted_updates: Dict[str, str] = {}
    for col, raw_val in updates.items():
        if col not in CREDENTIAL_COLUMNS:
            continue
        cleaned = (raw_val or "").strip()
        if not cleaned:
            encrypted_updates[col] = ""
        else:
            encrypted_updates[col] = encrypt_credential(cleaned, aad_context=f"{user_id}:{col}")
    return encrypted_updates


def ensure_user_preferences(conn, user_id: str, decrypt_in_memory: bool = True) -> Dict[str, Any]:
    """
    Ensures the `user_preferences` row exists for `user_id`.
    If any legacy plaintext credentials exist on the row, migrates them to AES-256-GCM at rest.
    When `decrypt_in_memory=True` (default for internal server callers), returns a copy with
    decrypted credentials in memory without ever writing plaintext back to SQLite.
    """
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

    result = dict(row)
    migrated_cols: Dict[str, str] = {}

    for col in CREDENTIAL_COLUMNS:
        stored_val = (result.get(col) or "").strip()
        if not stored_val:
            result[col] = ""
            continue

        aad_ctx = f"{user_id}:{col}"
        if is_encrypted_credential(stored_val):
            if decrypt_in_memory:
                result[col] = decrypt_credential(stored_val, aad_context=aad_ctx)
        elif stored_val.startswith("enc:"):
            raise CredentialEncryptionError(f"Unsupported or corrupted encrypted credential in column '{col}'.")
        else:
            # Opportunistically encrypt legacy plaintext credential at rest
            ciphertext = encrypt_credential(stored_val, aad_context=aad_ctx)
            migrated_cols[col] = ciphertext
            result[col] = stored_val if decrypt_in_memory else ciphertext

    if migrated_cols:
        set_clause = ", ".join(f"{k} = ?" for k in migrated_cols.keys())
        conn.execute(
            f"UPDATE user_preferences SET {set_clause} WHERE user_id = ?",
            [*migrated_cols.values(), user_id],
        )

    return result


def sanitize_preferences_for_client(pref: Dict[str, Any]) -> Dict[str, Any]:
    """Never expose raw or encrypted API keys in client-readable responses."""
    env_gemini = bool(os.environ.get("GEMINI_API_KEY", "").strip())
    env_openai = bool(os.environ.get("OPENAI_API_KEY", "").strip())
    env_anthropic = bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())
    env_youtube = bool(os.environ.get("YOUTUBE_DATA_API_KEY", "").strip())
    env_eleven = bool(os.environ.get("ELEVENLABS_API_KEY", "").strip())
    env_video = bool(os.environ.get("VIDEO_PROVIDER_API_KEY", "").strip())

    gem_val = (pref.get("gemini_api_key") or "").strip()
    oai_val = (pref.get("openai_api_key") or "").strip()
    ant_val = (pref.get("anthropic_api_key") or "").strip()
    yt_val = (pref.get("youtube_api_key") or "").strip()
    elv_val = (pref.get("elevenlabs_api_key") or "").strip()
    vid_val = (pref.get("video_provider_key") or "").strip()

    has_gemini = bool(gem_val) or env_gemini
    has_openai = bool(oai_val) or env_openai
    has_anthropic = bool(ant_val) or env_anthropic
    has_youtube = bool(yt_val) or env_youtube
    has_eleven = bool(elv_val) or env_eleven
    has_video = bool(vid_val) or env_video

    def _safe_mask(v: str) -> str:
        if not v or is_encrypted_credential(v):
            return "••••••••••••" if v else ""
        return mask_credential(v)

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
        "masked_credentials": {
            "gemini_api_key": _safe_mask(gem_val),
            "openai_api_key": _safe_mask(oai_val),
            "anthropic_api_key": _safe_mask(ant_val),
            "youtube_api_key": _safe_mask(yt_val),
            "elevenlabs_api_key": _safe_mask(elv_val),
            "video_provider_key": _safe_mask(vid_val),
        },
        "updated_at": pref.get("updated_at", ""),
    }


def extract_bearer_token(
    request: Request,
    authorization: Optional[str] = Header(default=None),
) -> str:
    """
    Extracts and validates the Bearer token from the Authorization header.
    Explicitly rejects generic JWT authentication tokens passed in URL query parameters (`?token=`).
    """
    if request.query_params.get("token") is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication tokens in URL query parameters are not permitted. Use the Authorization Bearer header.",
        )

    token: Optional[str] = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in.",
        )
    return token


def get_current_user(
    request: Request,
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    token = extract_bearer_token(request, authorization)
    payload = decode_access_token(token, check_revocation=True)
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
