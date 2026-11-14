"""
BRAINOVA — Email Verification Delivery Service
Provider-independent transactional email delivery supporting SMTP (Gmail / Generic),
Resend HTTPS API (production transactional email), and optional HTTP webhook relay.
Tracks delivery lifecycle states, provider message IDs, latencies, and suppression
lists without ever logging full email addresses, OTP codes, or credentials.
"""

import hashlib
import html
import json
import logging
import os
import smtplib
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate, make_msgid
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Protocol

from backend.database import get_db, new_id, utc_now

_logger = logging.getLogger("brainova.email")

DELIVERY_STATUS_QUEUED = "queued"
DELIVERY_STATUS_ACCEPTED = "accepted_by_provider"
DELIVERY_STATUS_DELIVERED = "delivered"
DELIVERY_STATUS_BOUNCED = "bounced"
DELIVERY_STATUS_REJECTED = "rejected"
DELIVERY_STATUS_FAILED = "failed"

RESEND_API_URL = "https://api.resend.com/emails"


class EmailDeliveryError(Exception):
    """Controlled error raised when verification email delivery cannot be completed."""


@dataclass
class EmailDeliveryResult:
    correlation_id: str
    status: str
    provider: str
    recipient_domain: str
    provider_message_id: str = ""
    connect_duration_ms: float = 0.0
    submit_duration_ms: float = 0.0
    total_duration_ms: float = 0.0
    smtp_code: Optional[int] = None
    error_category: str = ""


class EmailTransport(Protocol):
    """Provider-independent interface for transactional email delivery."""

    provider_name: str

    def send(
        self,
        *,
        correlation_id: str,
        to_email: str,
        recipient_name: str,
        subject: str,
        text_body: str,
        html_body: str,
    ) -> EmailDeliveryResult: ...


_TEST_EMAIL_SENDER: Optional[Callable[[str, str, str, int], None]] = None
_DEFAULT_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def load_local_env_file(env_path: Optional[str] = None) -> bool:
    """Load key=value pairs from .env without overriding existing process env vars."""
    target = Path(env_path) if env_path else _DEFAULT_ENV_PATH
    if not target.is_file():
        return False
    try:
        content = target.read_text(encoding="utf-8")
    except OSError:
        return False

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        key, _, val = line.partition("=")
        key = key.strip()
        if not key:
            continue
        val = val.strip()
        if len(val) >= 2 and ((val[0] == val[-1] == '"') or (val[0] == val[-1] == "'")):
            val = val[1:-1]
        os.environ.setdefault(key, val)
    return True


def set_email_sender_for_tests(
    sender: Optional[Callable[[str, str, str, int], None]],
) -> None:
    """Register or clear an in-memory email sender for automated unit tests."""
    global _TEST_EMAIL_SENDER
    _TEST_EMAIL_SENDER = sender


def extract_email_domain(email: str) -> str:
    clean = (email or "").strip().lower()
    if "@" not in clean:
        return "invalid"
    return clean.rsplit("@", 1)[-1] or "invalid"


def _hash_email_for_suppression(email: str) -> str:
    clean = (email or "").strip().lower()
    return hashlib.sha256(clean.encode("utf-8")).hexdigest()


def _detect_smtp_provider_name(host: str) -> str:
    low = (host or "").strip().lower()
    if "gmail" in low or "google" in low:
        return "gmail_smtp"
    if "brevo" in low or "sendinblue" in low:
        return "brevo_smtp"
    return "generic_smtp"


def _get_timeout_seconds() -> float:
    raw = os.environ.get("SMTP_TIMEOUT_SECONDS", "8").strip()
    try:
        val = float(raw)
        return min(max(val, 2.0), 15.0)
    except ValueError:
        return 8.0


_CONSUMER_EMAIL_DOMAINS = {
    "gmail.com",
    "googlemail.com",
    "yahoo.com",
    "outlook.com",
    "hotmail.com",
    "icloud.com",
    "aol.com",
    "live.com",
}


def _resolve_email_provider_mode() -> str:
    explicit = os.environ.get("EMAIL_PROVIDER", "").strip().lower()
    has_resend = bool(os.environ.get("EMAIL_API_KEY", "").strip())
    has_smtp = bool(os.environ.get("SMTP_HOST", "").strip())
    if explicit == "resend":
        if not has_resend and has_smtp:
            return "smtp"
        return "resend"
    if explicit in {"smtp", "gmail"}:
        if not has_smtp and has_resend:
            return "resend"
        return explicit
    if not explicit:
        if has_resend and not has_smtp:
            return "resend"
        return "smtp"
    return explicit


def _resolve_api_from_email(provider_mode: str = "") -> str:
    mode = (provider_mode or _resolve_email_provider_mode()).strip().lower()
    explicit = (
        os.environ.get("RESEND_FROM_EMAIL", "").strip()
        or os.environ.get("SMTP_FROM_EMAIL", "").strip()
    )
    sender_domain = os.environ.get("EMAIL_SENDER_DOMAIN", "").strip().lstrip("@").lower()
    if mode == "resend":
        if sender_domain and sender_domain not in _CONSUMER_EMAIL_DOMAINS:
            if explicit and extract_email_domain(explicit) == sender_domain:
                return explicit
            return f"noreply@{sender_domain}"
        if explicit and extract_email_domain(explicit) not in _CONSUMER_EMAIL_DOMAINS:
            return explicit
        return "onboarding@resend.dev"
    if explicit:
        return explicit
    if sender_domain:
        return f"noreply@{sender_domain}"
    return ""


def validate_smtp_configuration() -> tuple[bool, str]:
    """Validate configured email delivery settings without exposing credentials."""
    if _TEST_EMAIL_SENDER is not None:
        return True, ""

    provider_mode = _resolve_email_provider_mode()

    if provider_mode == "resend":
        api_key = os.environ.get("EMAIL_API_KEY", "").strip()
        from_email = _resolve_api_from_email("resend")
        if not api_key or not from_email:
            return (
                False,
                "Email verification service (Resend) is not configured. Set EMAIL_API_KEY in environment variables.",
            )
        return True, ""

    if provider_mode == "webhook":
        webhook_url = os.environ.get("EMAIL_WEBHOOK_URL", "").strip()
        from_email = _resolve_api_from_email()
        if not webhook_url or not from_email:
            return (
                False,
                "Email verification webhook provider is not configured. Set EMAIL_WEBHOOK_URL and SMTP_FROM_EMAIL.",
            )
        return True, ""

    if provider_mode not in {"smtp", "gmail"}:
        return False, f"Unsupported EMAIL_PROVIDER '{provider_mode}'. Use 'smtp' or 'resend'."

    host = os.environ.get("SMTP_HOST", "").strip()
    port_raw = os.environ.get("SMTP_PORT", "587").strip()
    username = os.environ.get("SMTP_USERNAME", "").strip()
    password = os.environ.get("SMTP_PASSWORD", "")
    from_email = os.environ.get("SMTP_FROM_EMAIL", "").strip()

    if not host or not from_email:
        return (
            False,
            "Email verification service is not configured. Set SMTP_HOST, SMTP_FROM_EMAIL, SMTP_USERNAME, and SMTP_PASSWORD (or configure EMAIL_PROVIDER=resend).",
        )

    try:
        port = int(port_raw)
    except ValueError:
        return False, "Email verification service SMTP_PORT configuration is invalid."
    if port < 1 or port > 65535:
        return False, "Email verification service SMTP_PORT must be between 1 and 65535."

    if bool(username) != bool(password):
        return (
            False,
            "Email verification service SMTP credentials are incomplete. Set both SMTP_USERNAME and SMTP_PASSWORD.",
        )

    if host.lower() not in {"localhost", "127.0.0.1", "::1"} and not (username and password):
        return (
            False,
            "Email verification service requires SMTP_USERNAME and SMTP_PASSWORD for authenticated SMTP delivery.",
        )

    return True, ""


def is_smtp_configured() -> bool:
    configured, _ = validate_smtp_configuration()
    return configured


def _log_delivery_event(result: EmailDeliveryResult) -> None:
    """Emit safe structured log and persist delivery status without PII or secrets."""
    timestamp = utc_now()
    payload = {
        "event": "email_delivery",
        "correlation_id": result.correlation_id,
        "provider_message_id": result.provider_message_id,
        "recipient_domain": result.recipient_domain,
        "provider": result.provider,
        "status": result.status,
        "smtp_code": result.smtp_code,
        "connect_duration_ms": round(result.connect_duration_ms, 2),
        "submit_duration_ms": round(result.submit_duration_ms, 2),
        "total_duration_ms": round(result.total_duration_ms, 2),
        "error_category": result.error_category,
        "timestamp": timestamp,
    }
    _logger.info(json.dumps(payload, sort_keys=True))

    try:
        with get_db(commit=True) as conn:
            existing = conn.execute(
                "SELECT id FROM email_delivery_logs WHERE correlation_id = ?",
                (result.correlation_id,),
            ).fetchone()
            if existing:
                conn.execute(
                    """
                    UPDATE email_delivery_logs
                    SET provider_message_id = CASE WHEN ? != '' THEN ? ELSE provider_message_id END,
                        status = ?, smtp_code = ?, connect_duration_ms = ?,
                        submit_duration_ms = ?, total_duration_ms = ?,
                        error_category = ?, updated_at = ?
                    WHERE correlation_id = ?
                    """,
                    (
                        result.provider_message_id,
                        result.provider_message_id,
                        result.status,
                        result.smtp_code,
                        round(result.connect_duration_ms, 2),
                        round(result.submit_duration_ms, 2),
                        round(result.total_duration_ms, 2),
                        result.error_category,
                        timestamp,
                        result.correlation_id,
                    ),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO email_delivery_logs (
                        id, correlation_id, provider_message_id, recipient_domain,
                        provider, status, smtp_code, connect_duration_ms,
                        submit_duration_ms, total_duration_ms, error_category,
                        created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        new_id("edl"),
                        result.correlation_id,
                        result.provider_message_id,
                        result.recipient_domain,
                        result.provider,
                        result.status,
                        result.smtp_code,
                        round(result.connect_duration_ms, 2),
                        round(result.submit_duration_ms, 2),
                        round(result.total_duration_ms, 2),
                        result.error_category,
                        timestamp,
                        timestamp,
                    ),
                )
    except Exception:
        # Never crash delivery flow or leak secrets if observability table is unavailable.
        pass


def is_email_suppressed(email: str) -> Optional[str]:
    email_hash = _hash_email_for_suppression(email)
    try:
        with get_db(commit=False) as conn:
            row = conn.execute(
                "SELECT reason FROM email_suppressions WHERE email_hash = ?",
                (email_hash,),
            ).fetchone()
            return row["reason"] if row else None
    except Exception:
        return None


def record_provider_webhook_event(
    *,
    correlation_id: str = "",
    provider_message_id: str = "",
    event_type: str,
    event_id: str = "",
    recipient_email: Optional[str] = None,
    provider: str = "webhook",
) -> Dict[str, Any]:
    """Update delivery status idempotently from an authenticated provider webhook."""
    norm_event = (event_type or "").strip().lower()
    if norm_event in {"delivered", "delivery", "email.delivered"}:
        next_status = DELIVERY_STATUS_DELIVERED
    elif norm_event in {"bounce", "bounced", "hard_bounce", "complained", "complaint", "email.bounced", "email.complained"}:
        next_status = DELIVERY_STATUS_BOUNCED
    elif norm_event in {"rejected", "email.rejected"}:
        next_status = DELIVERY_STATUS_REJECTED
    elif norm_event in {"failed", "dropped", "email.failed"}:
        next_status = DELIVERY_STATUS_FAILED
    elif norm_event in {"sent", "email.sent", "accepted"}:
        next_status = DELIVERY_STATUS_ACCEPTED
    else:
        raise ValueError(f"Unsupported email webhook event type: {event_type}")

    now_iso = utc_now()
    with get_db(commit=True) as conn:
        if event_id:
            existing_evt = conn.execute(
                "SELECT event_id FROM email_webhook_events WHERE event_id = ?",
                (event_id,),
            ).fetchone()
            if existing_evt:
                return {
                    "ok": True,
                    "duplicate": True,
                    "event_id": event_id,
                    "status": next_status,
                }

        target_corr = correlation_id.strip()
        if not target_corr and provider_message_id:
            matched = conn.execute(
                "SELECT correlation_id FROM email_delivery_logs WHERE provider_message_id = ?",
                (provider_message_id.strip(),),
            ).fetchone()
            if matched:
                target_corr = matched["correlation_id"]

        if event_id:
            conn.execute(
                """
                INSERT INTO email_webhook_events (event_id, correlation_id, event_type, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (event_id, target_corr, norm_event, now_iso),
            )

        if target_corr:
            conn.execute(
                """
                UPDATE email_delivery_logs
                SET status = ?, error_category = ?, updated_at = ?
                WHERE correlation_id = ?
                """,
                (
                    next_status,
                    norm_event if next_status not in {DELIVERY_STATUS_DELIVERED, DELIVERY_STATUS_ACCEPTED} else "",
                    now_iso,
                    target_corr,
                ),
            )

        if next_status in {DELIVERY_STATUS_BOUNCED, DELIVERY_STATUS_REJECTED} and recipient_email:
            conn.execute(
                """
                INSERT OR REPLACE INTO email_suppressions (
                    email_hash, recipient_domain, reason, provider, created_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    _hash_email_for_suppression(recipient_email),
                    extract_email_domain(recipient_email),
                    "hard_bounce" if next_status == DELIVERY_STATUS_BOUNCED else "provider_rejected",
                    provider,
                    now_iso,
                ),
            )

    return {
        "ok": True,
        "duplicate": False,
        "correlation_id": target_corr,
        "status": next_status,
    }


def build_verification_email_bodies(
    recipient_name: str,
    otp_code: str,
    expires_minutes: int = 5,
) -> tuple[str, str]:
    safe_name = html.escape((recipient_name or "Learner").strip() or "Learner")
    safe_code = html.escape(otp_code)

    text_body = (
        f"BRAINOVA — LEARN SMARTER. THINK BIGGER.\n\n"
        f"Hi {recipient_name or 'Learner'},\n\n"
        f"Your BRAINOVA email verification code is: {otp_code}\n\n"
        f"This code expires in {expires_minutes} minutes.\n"
        f"For your security, never share this verification code with anyone.\n"
        f"If you did not request a BRAINOVA account, you can safely ignore this email.\n"
    )

    html_body = f"""\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Verify Your BRAINOVA Email</title>
</head>
<body style="margin:0;padding:24px;background-color:#070a14;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#f8fafc;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:540px;margin:0 auto;background:linear-gradient(160deg,#0f172a 0%,#111827 100%);border:1px solid rgba(56,189,248,0.28);border-radius:16px;overflow:hidden;">
    <tr>
      <td style="padding:28px 28px 18px;border-bottom:1px solid rgba(148,163,184,0.14);">
        <div style="font-size:20px;font-weight:800;letter-spacing:0.06em;color:#f8fafc;">BRAINOVA</div>
        <div style="font-size:11px;font-weight:700;letter-spacing:0.12em;color:#38bdf8;margin-top:4px;">LEARN SMARTER. THINK BIGGER.</div>
      </td>
    </tr>
    <tr>
      <td style="padding:28px;">
        <h1 style="margin:0 0 12px;font-size:22px;font-weight:700;color:#ffffff;">Verify Your Email Address</h1>
        <p style="margin:0 0 20px;font-size:14px;line-height:1.6;color:#cbd5e1;">
          Hi {safe_name},<br /><br />
          Enter the six-digit verification code below to activate your BRAINOVA account:
        </p>
        <div style="margin:0 0 22px;padding:18px 20px;text-align:center;border-radius:12px;background-color:#070b14;border:1px solid rgba(99,102,241,0.45);">
          <span style="font-size:32px;font-weight:800;letter-spacing:0.28em;color:#67e8f9;font-family:'Courier New',monospace;">{safe_code}</span>
        </div>
        <p style="margin:0 0 12px;font-size:13px;line-height:1.5;color:#94a3b8;">
          <strong style="color:#e2e8f0;">Expires in {expires_minutes} minutes.</strong>
          This code can only be used once.
        </p>
        <div style="padding:12px 14px;border-radius:10px;background-color:rgba(245,158,11,0.1);border:1px solid rgba(245,158,11,0.28);font-size:12px;line-height:1.5;color:#fcd34d;">
          <strong>Security Notice:</strong> Never share this verification code with anyone. BRAINOVA will never ask for this code outside the verification screen.
        </div>
      </td>
    </tr>
    <tr>
      <td style="padding:16px 28px;border-top:1px solid rgba(148,163,184,0.14);font-size:12px;color:#64748b;">
        If you did not request a BRAINOVA account, you may safely ignore this email.
      </td>
    </tr>
  </table>
</body>
</html>
"""
    return text_body, html_body


def _build_mime_message(
    *,
    from_name: str,
    from_email: str,
    to_email: str,
    subject: str,
    text_body: str,
    html_body: str,
) -> tuple[MIMEMultipart, str]:
    from_domain = extract_email_domain(from_email)
    msg_id = make_msgid(domain=from_domain if from_domain != "invalid" else None)
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = formataddr((from_name, from_email))
    msg["To"] = to_email
    msg["Reply-To"] = from_email
    msg["Date"] = formatdate(localtime=False)
    msg["Message-ID"] = msg_id
    msg["X-Auto-Response-Suppress"] = "OOF, AutoReply"
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    return msg, msg_id


class SmtpEmailTransport:
    """SMTP transport supporting Gmail SMTP (STARTTLS/SSL) and generic SMTP servers."""

    def __init__(self) -> None:
        self.host = os.environ.get("SMTP_HOST", "").strip()
        self.port = int(os.environ.get("SMTP_PORT", "587").strip())
        self.username = os.environ.get("SMTP_USERNAME", "").strip()
        self.password = os.environ.get("SMTP_PASSWORD", "")
        self.from_email = os.environ.get("SMTP_FROM_EMAIL", "").strip()
        self.from_name = os.environ.get("SMTP_FROM_NAME", "BRAINOVA").strip() or "BRAINOVA"
        use_tls_raw = os.environ.get("SMTP_USE_TLS", "true").strip().lower()
        self.use_tls = use_tls_raw not in {"0", "false", "no", "off"}
        self.timeout = _get_timeout_seconds()
        self.provider_name = _detect_smtp_provider_name(self.host)

    def send(
        self,
        *,
        correlation_id: str,
        to_email: str,
        recipient_name: str,
        subject: str,
        text_body: str,
        html_body: str,
    ) -> EmailDeliveryResult:
        domain = extract_email_domain(to_email)
        msg, msg_id = _build_mime_message(
            from_name=self.from_name,
            from_email=self.from_email,
            to_email=to_email,
            subject=subject,
            text_body=text_body,
            html_body=html_body,
        )

        _log_delivery_event(
            EmailDeliveryResult(
                correlation_id=correlation_id,
                status=DELIVERY_STATUS_QUEUED,
                provider=self.provider_name,
                recipient_domain=domain,
                provider_message_id=msg_id,
            )
        )

        started_at = time.perf_counter()
        connect_ms = 0.0
        submit_ms = 0.0

        try:
            smtp_cls = smtplib.SMTP_SSL if self.port == 465 else smtplib.SMTP
            with smtp_cls(self.host, self.port, timeout=self.timeout) as server:
                if self.port != 465:
                    server.ehlo()
                    if self.use_tls:
                        server.starttls()
                        server.ehlo()
                if self.username and self.password:
                    server.login(self.username, self.password)
                connect_done = time.perf_counter()
                connect_ms = (connect_done - started_at) * 1000.0

                refused = server.sendmail(self.from_email, [to_email], msg.as_string())
                submit_done = time.perf_counter()
                submit_ms = (submit_done - connect_done) * 1000.0

                if refused:
                    first_code = next(iter(refused.values()))[0]
                    total_ms = (submit_done - started_at) * 1000.0
                    _log_delivery_event(
                        EmailDeliveryResult(
                            correlation_id=correlation_id,
                            status=DELIVERY_STATUS_REJECTED,
                            provider=self.provider_name,
                            recipient_domain=domain,
                            provider_message_id=msg_id,
                            connect_duration_ms=connect_ms,
                            submit_duration_ms=submit_ms,
                            total_duration_ms=total_ms,
                            smtp_code=int(first_code),
                            error_category="recipient_rejected",
                        )
                    )
                    raise EmailDeliveryError(
                        "The recipient email address was rejected by the mail server. Please verify the address and try again."
                    )

            total_ms = (time.perf_counter() - started_at) * 1000.0
            result = EmailDeliveryResult(
                correlation_id=correlation_id,
                status=DELIVERY_STATUS_ACCEPTED,
                provider=self.provider_name,
                recipient_domain=domain,
                provider_message_id=msg_id,
                connect_duration_ms=connect_ms,
                submit_duration_ms=submit_ms,
                total_duration_ms=total_ms,
                smtp_code=250,
            )
            _log_delivery_event(result)
            return result

        except EmailDeliveryError:
            raise
        except smtplib.SMTPAuthenticationError as exc:
            total_ms = (time.perf_counter() - started_at) * 1000.0
            _log_delivery_event(
                EmailDeliveryResult(
                    correlation_id=correlation_id,
                    status=DELIVERY_STATUS_FAILED,
                    provider=self.provider_name,
                    recipient_domain=domain,
                    provider_message_id=msg_id,
                    connect_duration_ms=connect_ms,
                    submit_duration_ms=submit_ms,
                    total_duration_ms=total_ms,
                    smtp_code=getattr(exc, "smtp_code", 535),
                    error_category="smtp_authentication_failed",
                )
            )
            raise EmailDeliveryError(
                "Email verification service authentication failed. Please check SMTP_USERNAME and SMTP_PASSWORD."
            ) from exc
        except smtplib.SMTPRecipientsRefused as exc:
            total_ms = (time.perf_counter() - started_at) * 1000.0
            first_code = next(iter(exc.recipients.values()))[0] if exc.recipients else 550
            _log_delivery_event(
                EmailDeliveryResult(
                    correlation_id=correlation_id,
                    status=DELIVERY_STATUS_REJECTED,
                    provider=self.provider_name,
                    recipient_domain=domain,
                    provider_message_id=msg_id,
                    connect_duration_ms=connect_ms,
                    submit_duration_ms=submit_ms,
                    total_duration_ms=total_ms,
                    smtp_code=int(first_code),
                    error_category="recipient_rejected",
                )
            )
            raise EmailDeliveryError(
                "The recipient email address was rejected by the mail server. Please verify the address and try again."
            ) from exc
        except smtplib.SMTPDataError as exc:
            total_ms = (time.perf_counter() - started_at) * 1000.0
            code = getattr(exc, "smtp_code", 554)
            is_rate_limit = code in {421, 450, 451, 452}
            _log_delivery_event(
                EmailDeliveryResult(
                    correlation_id=correlation_id,
                    status=DELIVERY_STATUS_FAILED if is_rate_limit else DELIVERY_STATUS_REJECTED,
                    provider=self.provider_name,
                    recipient_domain=domain,
                    provider_message_id=msg_id,
                    connect_duration_ms=connect_ms,
                    submit_duration_ms=submit_ms,
                    total_duration_ms=total_ms,
                    smtp_code=code,
                    error_category="rate_limited" if is_rate_limit else "smtp_data_rejected",
                )
            )
            raise EmailDeliveryError(
                "Unable to deliver verification email right now. Please try again shortly."
            ) from exc
        except smtplib.SMTPException as exc:
            total_ms = (time.perf_counter() - started_at) * 1000.0
            _log_delivery_event(
                EmailDeliveryResult(
                    correlation_id=correlation_id,
                    status=DELIVERY_STATUS_FAILED,
                    provider=self.provider_name,
                    recipient_domain=domain,
                    provider_message_id=msg_id,
                    connect_duration_ms=connect_ms,
                    submit_duration_ms=submit_ms,
                    total_duration_ms=total_ms,
                    smtp_code=getattr(exc, "smtp_code", None),
                    error_category="smtp_error",
                )
            )
            raise EmailDeliveryError(
                "Unable to deliver verification email right now. Please try again shortly."
            ) from exc
        except (TimeoutError, OSError) as exc:
            total_ms = (time.perf_counter() - started_at) * 1000.0
            is_timeout = isinstance(exc, TimeoutError) or "timed out" in str(exc).lower()
            _log_delivery_event(
                EmailDeliveryResult(
                    correlation_id=correlation_id,
                    status=DELIVERY_STATUS_FAILED,
                    provider=self.provider_name,
                    recipient_domain=domain,
                    provider_message_id=msg_id,
                    connect_duration_ms=connect_ms,
                    submit_duration_ms=submit_ms,
                    total_duration_ms=total_ms,
                    error_category="connection_timeout" if is_timeout else "network_error",
                )
            )
            raise EmailDeliveryError(
                "Unable to connect to the verification email server in time. Please try again shortly."
            ) from exc


class ResendEmailTransport:
    """Production transactional email API transport using Resend HTTPS REST API."""

    provider_name = "resend"

    def __init__(self) -> None:
        self.api_key = os.environ.get("EMAIL_API_KEY", "").strip()
        self.from_email = _resolve_api_from_email("resend")
        self.from_name = os.environ.get("SMTP_FROM_NAME", "BRAINOVA").strip() or "BRAINOVA"
        self.timeout = _get_timeout_seconds()

    def send(
        self,
        *,
        correlation_id: str,
        to_email: str,
        recipient_name: str,
        subject: str,
        text_body: str,
        html_body: str,
    ) -> EmailDeliveryResult:
        domain = extract_email_domain(to_email)
        _log_delivery_event(
            EmailDeliveryResult(
                correlation_id=correlation_id,
                status=DELIVERY_STATUS_QUEUED,
                provider=self.provider_name,
                recipient_domain=domain,
            )
        )

        started_at = time.perf_counter()
        payload = json.dumps(
            {
                "from": formataddr((self.from_name, self.from_email)),
                "to": [to_email],
                "reply_to": self.from_email,
                "subject": subject,
                "text": text_body,
                "html": html_body,
                "headers": {"X-Entity-Ref-ID": correlation_id},
            }
        ).encode("utf-8")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "resend-python/2.1.0",
            "Idempotency-Key": correlation_id,
        }
        req = urllib.request.Request(RESEND_API_URL, data=payload, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                status_code = int(getattr(resp, "status", 200))
                raw_body = resp.read().decode("utf-8", errors="replace")
            total_ms = (time.perf_counter() - started_at) * 1000.0
            parsed = json.loads(raw_body) if raw_body else {}
            provider_msg_id = str(parsed.get("id", "")).strip()

            result = EmailDeliveryResult(
                correlation_id=correlation_id,
                status=DELIVERY_STATUS_ACCEPTED,
                provider=self.provider_name,
                recipient_domain=domain,
                provider_message_id=provider_msg_id,
                submit_duration_ms=total_ms,
                total_duration_ms=total_ms,
                smtp_code=status_code,
            )
            _log_delivery_event(result)
            return result
        except urllib.error.HTTPError as exc:
            total_ms = (time.perf_counter() - started_at) * 1000.0
            code = int(getattr(exc, "code", 500))
            if code in {401, 403}:
                status = DELIVERY_STATUS_FAILED
                category = "provider_authentication_failed"
                user_msg = "Email verification service authentication failed. Please check EMAIL_API_KEY."
            elif code == 429:
                status = DELIVERY_STATUS_FAILED
                category = "provider_rate_limited"
                user_msg = "Email verification service is temporarily rate limited. Please try again shortly."
            elif code in {400, 422}:
                status = DELIVERY_STATUS_REJECTED
                category = "provider_rejected"
                user_msg = "The recipient email address or sender domain was rejected by the email provider."
            else:
                status = DELIVERY_STATUS_FAILED
                category = "provider_temporary_error" if code >= 500 else "provider_http_error"
                user_msg = "Unable to deliver verification email right now. Please try again shortly."

            _log_delivery_event(
                EmailDeliveryResult(
                    correlation_id=correlation_id,
                    status=status,
                    provider=self.provider_name,
                    recipient_domain=domain,
                    total_duration_ms=total_ms,
                    smtp_code=code,
                    error_category=category,
                )
            )
            raise EmailDeliveryError(user_msg) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            total_ms = (time.perf_counter() - started_at) * 1000.0
            is_timeout = isinstance(exc, TimeoutError) or "timed out" in str(exc).lower()
            _log_delivery_event(
                EmailDeliveryResult(
                    correlation_id=correlation_id,
                    status=DELIVERY_STATUS_FAILED,
                    provider=self.provider_name,
                    recipient_domain=domain,
                    total_duration_ms=total_ms,
                    error_category="connection_timeout" if is_timeout else "network_error",
                )
            )
            raise EmailDeliveryError(
                "Unable to connect to the verification email provider in time. Please try again shortly."
            ) from exc


class WebhookEmailTransport:
    """Optional provider-independent HTTP transactional email relay."""

    provider_name = "webhook_provider"

    def __init__(self) -> None:
        self.url = os.environ.get("EMAIL_WEBHOOK_URL", "").strip()
        self.api_key = os.environ.get("EMAIL_WEBHOOK_API_KEY", "").strip()
        self.from_email = _resolve_api_from_email()
        self.from_name = os.environ.get("SMTP_FROM_NAME", "BRAINOVA").strip() or "BRAINOVA"
        self.timeout = _get_timeout_seconds()

    def send(
        self,
        *,
        correlation_id: str,
        to_email: str,
        recipient_name: str,
        subject: str,
        text_body: str,
        html_body: str,
    ) -> EmailDeliveryResult:
        domain = extract_email_domain(to_email)
        started_at = time.perf_counter()
        payload = json.dumps(
            {
                "correlation_id": correlation_id,
                "from": {"email": self.from_email, "name": self.from_name},
                "to": [{"email": to_email, "name": recipient_name}],
                "subject": subject,
                "text": text_body,
                "html": html_body,
            }
        ).encode("utf-8")

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        req = urllib.request.Request(self.url, data=payload, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                status_code = int(getattr(resp, "status", 200))
            total_ms = (time.perf_counter() - started_at) * 1000.0
            if status_code >= 400:
                raise EmailDeliveryError("Email provider rejected the verification message.")
            result = EmailDeliveryResult(
                correlation_id=correlation_id,
                status=DELIVERY_STATUS_ACCEPTED,
                provider=self.provider_name,
                recipient_domain=domain,
                submit_duration_ms=total_ms,
                total_duration_ms=total_ms,
                smtp_code=status_code,
            )
            _log_delivery_event(result)
            return result
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            total_ms = (time.perf_counter() - started_at) * 1000.0
            _log_delivery_event(
                EmailDeliveryResult(
                    correlation_id=correlation_id,
                    status=DELIVERY_STATUS_FAILED,
                    provider=self.provider_name,
                    recipient_domain=domain,
                    total_duration_ms=total_ms,
                    error_category="provider_http_error",
                )
            )
            raise EmailDeliveryError(
                "Unable to deliver verification email right now. Please try again shortly."
            ) from exc


def get_email_transport() -> EmailTransport:
    provider_mode = _resolve_email_provider_mode()
    if provider_mode == "resend":
        return ResendEmailTransport()
    if provider_mode == "webhook":
        return WebhookEmailTransport()
    return SmtpEmailTransport()


def send_verification_email(
    to_email: str,
    recipient_name: str,
    otp_code: str,
    expires_minutes: int = 5,
    correlation_id: Optional[str] = None,
) -> EmailDeliveryResult:
    """Send the 6-digit OTP verification email via configured transport or test hook."""
    corr_id = correlation_id or f"otp_{uuid.uuid4().hex[:16]}"
    domain = extract_email_domain(to_email)

    if _TEST_EMAIL_SENDER is not None:
        started_at = time.perf_counter()
        _TEST_EMAIL_SENDER(to_email, recipient_name, otp_code, expires_minutes)
        total_ms = (time.perf_counter() - started_at) * 1000.0
        return EmailDeliveryResult(
            correlation_id=corr_id,
            status=DELIVERY_STATUS_ACCEPTED,
            provider="test_hook",
            recipient_domain=domain,
            submit_duration_ms=total_ms,
            total_duration_ms=total_ms,
            smtp_code=250,
        )

    suppression_reason = is_email_suppressed(to_email)
    if suppression_reason:
        _log_delivery_event(
            EmailDeliveryResult(
                correlation_id=corr_id,
                status=DELIVERY_STATUS_REJECTED,
                provider="suppression_list",
                recipient_domain=domain,
                error_category=f"suppressed_{suppression_reason}",
            )
        )
        raise EmailDeliveryError(
            "Verification emails to this address were previously bounced or rejected. Please use a different email address."
        )

    is_valid, error_message = validate_smtp_configuration()
    if not is_valid:
        raise EmailDeliveryError(error_message)

    text_body, html_body = build_verification_email_bodies(
        recipient_name=recipient_name,
        otp_code=otp_code,
        expires_minutes=expires_minutes,
    )

    transport = get_email_transport()
    return transport.send(
        correlation_id=corr_id,
        to_email=to_email,
        recipient_name=recipient_name,
        subject="Your BRAINOVA Verification Code",
        text_body=text_body,
        html_body=html_body,
    )
