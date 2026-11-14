"""
BRAINOVA — Strict Email OTP Verification & Pending Registration Service
Implements cryptographically secure 6-digit OTP generation, keyed HMAC-SHA256
storage, constant-time verification, concurrency-safe SQLite account activation,
and backend-enforced rate limits.
"""

import hashlib
import hmac
import os
import re
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

from fastapi import HTTPException

from backend.auth import (
    create_access_token,
    ensure_user_preferences,
    hash_password,
    sanitize_preferences_for_client,
)
from backend.database import DATA_DIR, get_db, log_activity, new_id
from backend.email_service import EmailDeliveryError, send_verification_email

OTP_LENGTH = 6
OTP_EXPIRY_SECONDS = 300  # 5 minutes
RESEND_COOLDOWN_SECONDS = 60  # 60 seconds
MAX_OTP_ATTEMPTS = 5
MAX_RESENDS_PER_HOUR = 3
MAX_REGISTRATIONS_PER_HOUR = 8

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _load_otp_secret() -> bytes:
    configured = os.environ.get("BRAINOVA_OTP_SECRET", "").strip()
    if os.environ.get("VERCEL"):
        if configured and len(configured) >= 32:
            return configured.encode("utf-8")
        seed = (
            configured
            or os.environ.get("AETHER_JWT_SECRET", "").strip()
            or os.environ.get("VERCEL_PROJECT_ID")
            or "brainova"
        )
        return hashlib.sha256(f"brainova-vercel-otp:{seed}".encode("utf-8")).hexdigest().encode("utf-8")

    if configured:
        if len(configured) < 32:
            raise RuntimeError("BRAINOVA_OTP_SECRET must contain at least 32 characters.")
        return configured.encode("utf-8")

    if os.environ.get("AETHER_ENV", "development").strip().lower() == "production":
        raise RuntimeError(
            "BRAINOVA_OTP_SECRET must be configured when AETHER_ENV=production."
        )

    os.makedirs(DATA_DIR, exist_ok=True)
    secret_path = os.path.join(DATA_DIR, ".aether_otp_secret")
    try:
        secret_bytes = secrets.token_urlsafe(48).encode("utf-8")
        descriptor = os.open(secret_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        try:
            os.write(descriptor, secret_bytes)
        finally:
            os.close(descriptor)
        return secret_bytes
    except FileExistsError:
        with open(secret_path, "r", encoding="utf-8") as f:
            secret = f.read().strip()
        if len(secret) < 32:
            raise RuntimeError(f"The local OTP key at {secret_path} is invalid.")
        return secret.encode("utf-8")


_OTP_SECRET_BYTES = _load_otp_secret()


def _utc_now_dt() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def normalize_email(raw_email: str) -> str:
    cleaned = (raw_email or "").strip().lower()
    if not _EMAIL_RE.match(cleaned) or len(cleaned) > 254:
        raise HTTPException(status_code=400, detail="Please enter a valid email address.")
    return cleaned


def mask_email(email: str) -> str:
    parts = email.split("@", 1)
    if len(parts) != 2:
        return "****"
    local, domain = parts
    visible = local[:4] if len(local) > 4 else local[:1]
    return f"{visible}****@{domain}"


def generate_otp_code() -> str:
    """Generate a cryptographically secure 6-digit OTP preserving leading zeros."""
    return f"{secrets.randbelow(1_000_000):06d}"


def compute_otp_hmac(pending_token: str, otp_code: str) -> str:
    msg = f"{pending_token}:{otp_code}".encode("utf-8")
    return hmac.new(_OTP_SECRET_BYTES, msg, hashlib.sha256).hexdigest()


def verify_otp_hmac(pending_token: str, otp_code: str, expected_hmac: str) -> bool:
    if not expected_hmac or not otp_code:
        return False
    candidate = compute_otp_hmac(pending_token, otp_code)
    return hmac.compare_digest(candidate, expected_hmac)


def cleanup_expired_pending_registrations(conn: sqlite3.Connection, now_dt: Optional[datetime] = None) -> int:
    """Safely remove abandoned pending registrations older than 24 hours without touching users."""
    ref = now_dt or _utc_now_dt()
    cutoff = (ref - timedelta(hours=24)).isoformat()
    cur = conn.execute(
        "DELETE FROM pending_registrations WHERE otp_expires_at < ?",
        (cutoff,),
    )
    return cur.rowcount or 0


def _enforce_registration_rate_limit(
    conn: sqlite3.Connection,
    email_clean: str,
    client_ip: str,
    now_dt: datetime,
) -> None:
    keys = [f"email:{email_clean}"]
    if client_ip:
        keys.append(f"ip:{client_ip}")

    for rate_key in keys:
        row = conn.execute(
            "SELECT * FROM registration_rate_limits WHERE rate_key = ?",
            (rate_key,),
        ).fetchone()
        if row:
            window_start = _parse_iso(row["window_start"])
            if now_dt - window_start < timedelta(hours=1):
                if int(row["request_count"]) >= MAX_REGISTRATIONS_PER_HOUR:
                    raise HTTPException(
                        status_code=429,
                        detail="Too many registration attempts. Please wait before requesting another verification code.",
                    )
                conn.execute(
                    "UPDATE registration_rate_limits SET request_count = request_count + 1, updated_at = ? WHERE rate_key = ?",
                    (now_dt.isoformat(), rate_key),
                )
            else:
                conn.execute(
                    "UPDATE registration_rate_limits SET window_start = ?, request_count = 1, updated_at = ? WHERE rate_key = ?",
                    (now_dt.isoformat(), now_dt.isoformat(), rate_key),
                )
        else:
            conn.execute(
                """
                INSERT INTO registration_rate_limits (rate_key, window_start, request_count, updated_at)
                VALUES (?, ?, 1, ?)
                """,
                (rate_key, now_dt.isoformat(), now_dt.isoformat()),
            )


def _format_pending_response(row: Dict[str, Any], now_dt: datetime) -> Dict[str, Any]:
    expires_dt = _parse_iso(row["otp_expires_at"])
    last_sent_dt = _parse_iso(row["last_sent_at"])
    resend_available_dt = last_sent_dt + timedelta(seconds=RESEND_COOLDOWN_SECONDS)

    expires_in = max(0, int((expires_dt - now_dt).total_seconds()))
    resend_in = max(0, int((resend_available_dt - now_dt).total_seconds()))
    attempts_remaining = max(0, MAX_OTP_ATTEMPTS - int(row["attempt_count"]))
    resends_remaining = max(0, MAX_RESENDS_PER_HOUR - int(row["resend_count"]))

    return {
        "status": "verification_required",
        "pending_token": row["pending_token"],
        "masked_email": mask_email(row["email"]),
        "expires_at": row["otp_expires_at"],
        "expires_in_seconds": expires_in,
        "resend_available_at": resend_available_dt.isoformat(),
        "resend_cooldown_seconds": resend_in,
        "attempts_remaining": attempts_remaining,
        "resends_remaining": resends_remaining,
        "expired": expires_in <= 0,
        "otp_invalidated": not bool(row["otp_hmac"]),
    }


def initiate_pending_registration(
    *,
    name: str,
    email: str,
    password: str,
    target_role: str = "Full Stack Developer",
    confirm_password: Optional[str] = None,
    client_ip: str = "",
) -> Dict[str, Any]:
    clean_name = (name or "").strip()
    if len(clean_name) < 1 or len(clean_name) > 40:
        raise HTTPException(status_code=400, detail="Full name must be between 1 and 40 characters.")

    email_clean = normalize_email(email)

    if len(password or "") < 6 or len(password or "") > 25:
        raise HTTPException(status_code=400, detail="Password must be between 6 and 25 characters.")
    if confirm_password is not None and password != confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match.")

    clean_role = (target_role or "Full Stack Developer").strip() or "Full Stack Developer"
    now_dt = _utc_now_dt()
    now_iso = now_dt.isoformat()
    expires_iso = (now_dt + timedelta(seconds=OTP_EXPIRY_SECONDS)).isoformat()

    pending_id = new_id("preg")
    pending_token = secrets.token_urlsafe(32)
    otp_code = generate_otp_code()
    otp_hmac = compute_otp_hmac(pending_token, otp_code)
    pw_hash = hash_password(password)

    with get_db(commit=True) as conn:
        conn.execute("BEGIN IMMEDIATE")
        cleanup_expired_pending_registrations(conn, now_dt)

        existing_user = conn.execute(
            "SELECT id FROM users WHERE email = ?",
            (email_clean,),
        ).fetchone()
        if not existing_user and os.environ.get("VERCEL"):
            try:
                from backend.mongo_sync import restore_user_by_email_from_mongo

                if restore_user_by_email_from_mongo(conn, email_clean):
                    existing_user = conn.execute(
                        "SELECT id FROM users WHERE email = ?",
                        (email_clean,),
                    ).fetchone()
            except Exception:
                pass
        if existing_user:
            raise HTTPException(
                status_code=409,
                detail="An account with this email already exists. Please sign in instead.",
            )

        _enforce_registration_rate_limit(conn, email_clean, client_ip, now_dt)

        existing_pending = conn.execute(
            "SELECT * FROM pending_registrations WHERE email = ?",
            (email_clean,),
        ).fetchone()

        resend_count = 0
        resend_window_start = now_iso
        if existing_pending:
            prev_window = _parse_iso(existing_pending["resend_window_start"])
            if now_dt - prev_window < timedelta(hours=1):
                resend_count = int(existing_pending["resend_count"]) + 1
                resend_window_start = existing_pending["resend_window_start"]
                if resend_count > MAX_RESENDS_PER_HOUR:
                    raise HTTPException(
                        status_code=429,
                        detail="Maximum verification email requests reached for this hour. Please try again later.",
                    )

    # Deliver email outside SQLite write lock so observability logging never contends
    # and failed deliveries never persist a pending registration.
    try:
        delivery_result = send_verification_email(
            to_email=email_clean,
            recipient_name=clean_name,
            otp_code=otp_code,
            expires_minutes=OTP_EXPIRY_SECONDS // 60,
        )
    except EmailDeliveryError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    with get_db(commit=True) as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "DELETE FROM pending_registrations WHERE email = ?",
            (email_clean,),
        )
        conn.execute(
            """
            INSERT INTO pending_registrations (
                id, pending_token, email, name, password_hash, target_role,
                otp_hmac, otp_expires_at, attempt_count, resend_count,
                resend_window_start, last_sent_at, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?)
            """,
            (
                pending_id,
                pending_token,
                email_clean,
                clean_name,
                pw_hash,
                clean_role,
                otp_hmac,
                expires_iso,
                resend_count,
                resend_window_start,
                now_iso,
                now_iso,
                now_iso,
            ),
        )

        row = conn.execute(
            "SELECT * FROM pending_registrations WHERE pending_token = ?",
            (pending_token,),
        ).fetchone()

    resp = _format_pending_response(row, now_dt)
    resp["delivery_status"] = delivery_result.status
    resp["delivery_correlation_id"] = delivery_result.correlation_id
    return resp


def get_pending_registration_status(pending_token: str) -> Dict[str, Any]:
    token = (pending_token or "").strip()
    if not token:
        raise HTTPException(status_code=404, detail="Pending registration session not found.")

    now_dt = _utc_now_dt()
    with get_db(commit=False) as conn:
        row = conn.execute(
            "SELECT * FROM pending_registrations WHERE pending_token = ?",
            (token,),
        ).fetchone()
        if not row:
            raise HTTPException(
                status_code=404,
                detail="This verification session has expired or was already completed. Please register again.",
            )
        return _format_pending_response(row, now_dt)


def cancel_pending_registration(pending_token: str) -> Dict[str, Any]:
    token = (pending_token or "").strip()
    if not token:
        return {"ok": True}
    with get_db(commit=True) as conn:
        conn.execute("DELETE FROM pending_registrations WHERE pending_token = ?", (token,))
    return {"ok": True}


def resend_pending_verification(pending_token: str) -> Dict[str, Any]:
    token = (pending_token or "").strip()
    if not token:
        raise HTTPException(status_code=404, detail="Verification session not found.")

    now_dt = _utc_now_dt()
    now_iso = now_dt.isoformat()
    new_expires_iso = (now_dt + timedelta(seconds=OTP_EXPIRY_SECONDS)).isoformat()
    new_otp = generate_otp_code()
    new_hmac = compute_otp_hmac(token, new_otp)

    with get_db(commit=True) as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT * FROM pending_registrations WHERE pending_token = ?",
            (token,),
        ).fetchone()
        if not row:
            raise HTTPException(
                status_code=404,
                detail="Verification session expired or not found. Please start registration again.",
            )

        last_sent_dt = _parse_iso(row["last_sent_at"])
        elapsed = (now_dt - last_sent_dt).total_seconds()
        if elapsed < RESEND_COOLDOWN_SECONDS:
            wait_secs = max(1, int(RESEND_COOLDOWN_SECONDS - elapsed))
            raise HTTPException(
                status_code=429,
                detail=f"Please wait {wait_secs} seconds before requesting another verification code.",
            )

        window_start = _parse_iso(row["resend_window_start"])
        if now_dt - window_start < timedelta(hours=1):
            next_resend_count = int(row["resend_count"]) + 1
            next_window_start = row["resend_window_start"]
            if next_resend_count > MAX_RESENDS_PER_HOUR:
                raise HTTPException(
                    status_code=429,
                    detail="Hourly resend limit reached (maximum 3 resends per hour). Please try again later.",
                )
        else:
            next_resend_count = 1
            next_window_start = now_iso

    # Deliver email outside SQLite write lock; only rotate OTP state if accepted.
    try:
        delivery_result = send_verification_email(
            to_email=row["email"],
            recipient_name=row["name"],
            otp_code=new_otp,
            expires_minutes=OTP_EXPIRY_SECONDS // 60,
        )
    except EmailDeliveryError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    with get_db(commit=True) as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            """
            UPDATE pending_registrations
            SET otp_hmac = ?,
                otp_expires_at = ?,
                attempt_count = 0,
                resend_count = ?,
                resend_window_start = ?,
                last_sent_at = ?,
                updated_at = ?
            WHERE pending_token = ?
            """,
            (
                new_hmac,
                new_expires_iso,
                next_resend_count,
                next_window_start,
                now_iso,
                now_iso,
                token,
            ),
        )

        updated = conn.execute(
            "SELECT * FROM pending_registrations WHERE pending_token = ?",
            (token,),
        ).fetchone()

    resp = _format_pending_response(updated, now_dt)
    resp["delivery_status"] = delivery_result.status
    resp["delivery_correlation_id"] = delivery_result.correlation_id
    return resp


def verify_pending_registration_otp(pending_token: str, otp_code: str) -> Dict[str, Any]:
    token = (pending_token or "").strip()
    clean_otp = (otp_code or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="Verification session is missing. Please register again.")
    if not re.fullmatch(r"\d{6}", clean_otp):
        raise HTTPException(status_code=400, detail="Please enter the exact 6-digit verification code.")

    now_dt = _utc_now_dt()
    now_iso = now_dt.isoformat()

    with get_db(commit=True) as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT * FROM pending_registrations WHERE pending_token = ?",
            (token,),
        ).fetchone()
        if not row:
            raise HTTPException(
                status_code=404,
                detail="Verification session expired or already used. Please sign in or register again.",
            )

        if not row["otp_hmac"] or int(row["attempt_count"]) >= MAX_OTP_ATTEMPTS:
            raise HTTPException(
                status_code=429,
                detail="This verification code has been invalidated after too many incorrect attempts. Request a new code.",
            )

        expires_dt = _parse_iso(row["otp_expires_at"])
        if now_dt > expires_dt:
            raise HTTPException(
                status_code=400,
                detail="This verification code has expired. Please request a new code.",
            )

        if not verify_otp_hmac(token, clean_otp, row["otp_hmac"]):
            next_attempts = int(row["attempt_count"]) + 1
            if next_attempts >= MAX_OTP_ATTEMPTS:
                conn.execute(
                    """
                    UPDATE pending_registrations
                    SET attempt_count = ?, otp_hmac = '', updated_at = ?
                    WHERE pending_token = ?
                    """,
                    (next_attempts, now_iso, token),
                )
                conn.commit()
                raise HTTPException(
                    status_code=429,
                    detail="Too many incorrect attempts. This code is now invalid — please request a new code.",
                )
            conn.execute(
                """
                UPDATE pending_registrations
                SET attempt_count = ?, updated_at = ?
                WHERE pending_token = ?
                """,
                (next_attempts, now_iso, token),
            )
            conn.commit()
            remaining = MAX_OTP_ATTEMPTS - next_attempts
            raise HTTPException(
                status_code=400,
                detail=f"Incorrect verification code. {remaining} attempt{'s' if remaining != 1 else ''} remaining.",
            )

        # OTP verified! Check unique email and atomically create permanent user.
        existing_user = conn.execute(
            "SELECT id FROM users WHERE email = ?",
            (row["email"],),
        ).fetchone()
        if existing_user:
            conn.execute("DELETE FROM pending_registrations WHERE pending_token = ?", (token,))
            conn.commit()
            raise HTTPException(
                status_code=409,
                detail="An account with this email already exists. Please sign in.",
            )

        user_id = new_id("usr")
        colors = ["#6366f1", "#38bdf8", "#8b5cf6", "#10b981", "#f59e0b"]
        color = colors[len(row["email"]) % len(colors)]

        conn.execute(
            """
            INSERT INTO users (
                id, email, name, password_hash, role, target_role,
                bio, avatar_color, email_verified, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, 'student', ?, '', ?, 1, ?, ?)
            """,
            (
                user_id,
                row["email"],
                row["name"],
                row["password_hash"],
                row["target_role"],
                color,
                now_iso,
                now_iso,
            ),
        )
        prefs = ensure_user_preferences(conn, user_id)
        log_activity(conn, user_id, "signup", "user", user_id, "Verified email and created BRAINOVA account", 2)

        # Consume pending registration so the OTP can never be reused.
        conn.execute("DELETE FROM pending_registrations WHERE pending_token = ?", (token,))

        user_row = conn.execute(
            "SELECT id, email, name, role, target_role, bio, avatar_color, email_verified, created_at, updated_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        user_row["preferences"] = sanitize_preferences_for_client(prefs)

    access_token = create_access_token(user_id, user_row["email"])
    return {"token": access_token, "user": user_row}

