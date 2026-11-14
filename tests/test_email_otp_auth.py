"""Socket-free unit and route-handler tests for BRAINOVA strict Email OTP registration gate."""

import os
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

OTP_TEST_DIR = tempfile.mkdtemp(prefix="brainova_otp_auth_")
os.environ["AETHER_DB_PATH"] = os.path.join(OTP_TEST_DIR, "otp_auth.db")
os.environ["BRAINOVA_MASTER_KEY_FILE"] = os.path.join(OTP_TEST_DIR, ".otp_master_key")
os.environ["BRAINOVA_OTP_SECRET"] = "unit-test-otp-hmac-secret-at-least-32-chars"
os.environ.setdefault("AETHER_JWT_SECRET", "unit-test-jwt-secret-with-at-least-32-chars")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from fastapi import HTTPException
from starlette.requests import Request

from backend.auth import get_current_user, hash_password
from backend.database import get_db, init_db, run_migrations, utc_now
from backend.email_service import (
    DELIVERY_STATUS_ACCEPTED,
    DELIVERY_STATUS_BOUNCED,
    DELIVERY_STATUS_DELIVERED,
    DELIVERY_STATUS_FAILED,
    DELIVERY_STATUS_REJECTED,
    EmailDeliveryError,
    is_smtp_configured,
    load_local_env_file,
    record_provider_webhook_event,
    send_verification_email,
    set_email_sender_for_tests,
    validate_smtp_configuration,
)
from backend.main import (
    LoginRequest,
    ResendVerificationRequest,
    SignupRequest,
    VerifyEmailRequest,
    delete_pending_registration,
    get_pending_registration,
    login,
    receive_email_provider_webhook,
    register_account,
    resend_email_otp,
    verify_email_otp,
)
from backend.otp_auth import (
    MAX_OTP_ATTEMPTS,
    MAX_REGISTRATIONS_PER_HOUR,
    MAX_RESENDS_PER_HOUR,
    OTP_EXPIRY_SECONDS,
    RESEND_COOLDOWN_SECONDS,
    compute_otp_hmac,
    generate_otp_code,
    mask_email,
    verify_otp_hmac,
    verify_pending_registration_otp,
)


def _dummy_request(bearer_token: str = "", client_ip: str = "127.0.0.1") -> Request:
    headers = []
    if bearer_token:
        headers.append((b"authorization", f"Bearer {bearer_token}".encode("latin-1")))
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/",
            "query_string": b"",
            "headers": headers,
            "client": (client_ip, 12345),
        }
    )


class EmailOtpAuthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.sent_emails = []
        set_email_sender_for_tests(self._capture_email)
        with get_db(commit=True) as conn:
            conn.execute("DELETE FROM pending_registrations")
            conn.execute("DELETE FROM registration_rate_limits")
            conn.execute("DELETE FROM email_delivery_logs")
            conn.execute("DELETE FROM email_suppressions")
            conn.execute("DELETE FROM email_webhook_events")
            conn.execute("DELETE FROM activity_logs")
            conn.execute("DELETE FROM users")

    def tearDown(self):
        set_email_sender_for_tests(None)

    def _capture_email(self, to_email: str, recipient_name: str, otp_code: str, expires_minutes: int):
        self.sent_emails.append(
            {
                "to_email": to_email,
                "recipient_name": recipient_name,
                "otp_code": otp_code,
                "expires_minutes": expires_minutes,
            }
        )

    def _register(self, email="siddharth@example.com", password="StrongPassword123!", name="Siddharth"):
        req = SignupRequest(
            name=name,
            email=email,
            password=password,
            confirm_password=password,
            target_role="ML Engineer",
        )
        return register_account(req, _dummy_request())

    def test_otp_generation_leading_zeros_and_hmac_verification(self):
        with patch("backend.otp_auth.secrets.randbelow", return_value=42):
            code = generate_otp_code()
        self.assertEqual(code, "000042")
        self.assertEqual(len(code), 6)

        digest = compute_otp_hmac("pending-123", code)
        self.assertNotIn(code, digest)
        self.assertTrue(verify_otp_hmac("pending-123", "000042", digest))
        self.assertFalse(verify_otp_hmac("pending-123", "000043", digest))
        self.assertEqual(mask_email("siddharth@gmail.com"), "sidd****@gmail.com")

    def test_registration_does_not_create_user_or_jwt_before_verification(self):
        data = self._register()
        self.assertEqual(data["status"], "verification_required")
        self.assertEqual(data["masked_email"], "sidd****@example.com")
        self.assertNotIn("token", data)
        self.assertNotIn("user", data)
        self.assertEqual(len(self.sent_emails), 1)
        otp_code = self.sent_emails[0]["otp_code"]
        self.assertRegex(otp_code, r"^\d{6}$")

        # Protected route dependency remains inaccessible without a valid JWT
        with self.assertRaises(HTTPException) as ctx:
            get_current_user(_dummy_request(), authorization=None)
        self.assertEqual(ctx.exception.status_code, 401)

        # No permanent user exists yet, and plaintext OTP is not stored in SQLite
        with get_db() as conn:
            user_count = conn.execute("SELECT COUNT(*) AS cnt FROM users").fetchone()["cnt"]
            self.assertEqual(user_count, 0)
            pending_row = conn.execute(
                "SELECT otp_hmac, password_hash FROM pending_registrations WHERE pending_token = ?",
                (data["pending_token"],),
            ).fetchone()
            self.assertIsNotNone(pending_row)
            self.assertNotEqual(pending_row["otp_hmac"], otp_code)
            self.assertNotIn(otp_code, pending_row["otp_hmac"])
            self.assertNotIn("StrongPassword123!", pending_row["password_hash"])

        # Login before verification must fail
        with self.assertRaises(HTTPException) as login_ctx:
            login(LoginRequest(email="siddharth@example.com", password="StrongPassword123!"))
        self.assertEqual(login_ctx.exception.status_code, 401)

    def test_verify_email_activates_user_and_rejects_otp_reuse(self):
        reg = self._register()
        otp_code = self.sent_emails[0]["otp_code"]

        verify_data = verify_email_otp(
            VerifyEmailRequest(pending_token=reg["pending_token"], otp_code=otp_code)
        )
        self.assertIn("token", verify_data)
        self.assertEqual(verify_data["user"]["email"], "siddharth@example.com")
        self.assertEqual(verify_data["user"]["email_verified"], 1)

        # Protected dependency now authenticates with returned JWT
        current_user = get_current_user(
            _dummy_request(bearer_token=verify_data["token"]),
            authorization=f"Bearer {verify_data['token']}",
        )
        self.assertEqual(current_user["email"], "siddharth@example.com")

        # Reusing the same OTP / pending_token fails
        with self.assertRaises(HTTPException) as reuse_ctx:
            verify_email_otp(
                VerifyEmailRequest(pending_token=reg["pending_token"], otp_code=otp_code)
            )
        self.assertEqual(reuse_ctx.exception.status_code, 404)

    def test_otp_expiry_after_5_minutes_is_rejected(self):
        reg = self._register()
        otp_code = self.sent_emails[0]["otp_code"]

        past = (datetime.now(timezone.utc) - timedelta(seconds=OTP_EXPIRY_SECONDS + 5)).isoformat()
        with get_db(commit=True) as conn:
            conn.execute(
                "UPDATE pending_registrations SET otp_expires_at = ? WHERE pending_token = ?",
                (past, reg["pending_token"]),
            )

        with self.assertRaises(HTTPException) as ctx:
            verify_email_otp(
                VerifyEmailRequest(pending_token=reg["pending_token"], otp_code=otp_code)
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("expired", ctx.exception.detail.lower())

        with get_db() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) AS cnt FROM users").fetchone()["cnt"], 0)

    def test_five_incorrect_attempts_invalidate_code(self):
        reg = self._register()
        real_otp = self.sent_emails[0]["otp_code"]
        wrong_otp = "999999" if real_otp != "999999" else "111111"

        for i in range(MAX_OTP_ATTEMPTS):
            with self.assertRaises(HTTPException) as bad_ctx:
                verify_email_otp(
                    VerifyEmailRequest(pending_token=reg["pending_token"], otp_code=wrong_otp)
                )
            expected_status = 429 if i == MAX_OTP_ATTEMPTS - 1 else 400
            self.assertEqual(bad_ctx.exception.status_code, expected_status)

        # Even the real OTP must now fail after max attempts reached
        with self.assertRaises(HTTPException) as locked_ctx:
            verify_email_otp(
                VerifyEmailRequest(pending_token=reg["pending_token"], otp_code=real_otp)
            )
        self.assertEqual(locked_ctx.exception.status_code, 429)
        self.assertIn("invalid", locked_ctx.exception.detail.lower())

    def test_resend_cooldown_invalidates_old_code_and_enforces_hourly_limit(self):
        reg = self._register()
        first_otp = self.sent_emails[0]["otp_code"]

        # Immediate resend blocked by 60s cooldown
        with self.assertRaises(HTTPException) as too_soon:
            resend_email_otp(ResendVerificationRequest(pending_token=reg["pending_token"]))
        self.assertEqual(too_soon.exception.status_code, 429)

        # Perform MAX_RESENDS_PER_HOUR valid resends by shifting last_sent_at back
        latest_otp = first_otp
        for _ in range(MAX_RESENDS_PER_HOUR):
            past = (datetime.now(timezone.utc) - timedelta(seconds=RESEND_COOLDOWN_SECONDS + 2)).isoformat()
            with get_db(commit=True) as conn:
                conn.execute(
                    "UPDATE pending_registrations SET last_sent_at = ? WHERE pending_token = ?",
                    (past, reg["pending_token"]),
                )
            resend_resp = resend_email_otp(
                ResendVerificationRequest(pending_token=reg["pending_token"])
            )
            self.assertEqual(resend_resp["pending_token"], reg["pending_token"])
            latest_otp = self.sent_emails[-1]["otp_code"]

        # Exceeding hourly resend limit fails even after cooldown
        past = (datetime.now(timezone.utc) - timedelta(seconds=RESEND_COOLDOWN_SECONDS + 2)).isoformat()
        with get_db(commit=True) as conn:
            conn.execute(
                "UPDATE pending_registrations SET last_sent_at = ? WHERE pending_token = ?",
                (past, reg["pending_token"]),
            )
        with self.assertRaises(HTTPException) as over_limit:
            resend_email_otp(ResendVerificationRequest(pending_token=reg["pending_token"]))
        self.assertEqual(over_limit.exception.status_code, 429)

        # Old code must be rejected if different from latest_otp
        if first_otp != latest_otp:
            with self.assertRaises(HTTPException) as old_ctx:
                verify_email_otp(
                    VerifyEmailRequest(pending_token=reg["pending_token"], otp_code=first_otp)
                )
            self.assertEqual(old_ctx.exception.status_code, 400)

        # Latest code succeeds
        ok_resp = verify_email_otp(
            VerifyEmailRequest(pending_token=reg["pending_token"], otp_code=latest_otp)
        )
        self.assertIn("token", ok_resp)

    def test_concurrent_verification_creates_only_one_user(self):
        reg = self._register()
        otp_code = self.sent_emails[0]["otp_code"]

        def attempt():
            try:
                verify_pending_registration_otp(reg["pending_token"], otp_code)
                return 200
            except HTTPException as exc:
                return exc.status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(lambda _: attempt(), range(2)))

        self.assertEqual(sorted(statuses), [200, 404])
        with get_db() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) AS cnt FROM users").fetchone()["cnt"], 1)

    def test_email_delivery_failure_does_not_create_pending_or_permanent_user(self):
        def failing_sender(*_args, **_kwargs):
            raise EmailDeliveryError("SMTP unreachable")

        set_email_sender_for_tests(failing_sender)
        with self.assertRaises(HTTPException) as ctx:
            self._register()
        self.assertEqual(ctx.exception.status_code, 503)

        with get_db() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) AS cnt FROM users").fetchone()["cnt"], 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) AS cnt FROM pending_registrations").fetchone()["cnt"], 0)

    def test_registration_rate_limit_blocks_excessive_attempts(self):
        for i in range(MAX_REGISTRATIONS_PER_HOUR):
            r = self._register(email=f"user{i}@example.com")
            self.assertEqual(r["status"], "verification_required")

        with self.assertRaises(HTTPException) as blocked:
            self._register(email="blocked@example.com")
        self.assertEqual(blocked.exception.status_code, 429)

    def test_existing_user_migration_and_password_login_without_otp(self):
        now = utc_now()
        pw_hash = hash_password("ExistingPass123!")
        with get_db(commit=True) as conn:
            conn.execute(
                """
                INSERT INTO users (id, email, name, password_hash, role, target_role, bio, avatar_color, created_at, updated_at)
                VALUES ('usr_legacy_1', 'legacy@example.com', 'Legacy User', ?, 'student', 'Analyst', '', '#6366f1', ?, ?)
                """,
                (pw_hash, now, now),
            )
            run_migrations(conn)
            migrated = conn.execute(
                "SELECT email_verified FROM users WHERE id = 'usr_legacy_1'"
            ).fetchone()
            self.assertEqual(migrated["email_verified"], 1)

        data = login(LoginRequest(email="legacy@example.com", password="ExistingPass123!"))
        self.assertIn("token", data)
        self.assertEqual(data["user"]["id"], "usr_legacy_1")
        # No OTP email sent on login
        self.assertEqual(len(self.sent_emails), 0)

    def test_password_mismatch_and_pending_cancellation(self):
        with self.assertRaises(HTTPException) as mismatch:
            register_account(
                SignupRequest(
                    name="Mismatch User",
                    email="mismatch@example.com",
                    password="PasswordOne123!",
                    confirm_password="PasswordTwo123!",
                    target_role="Engineer",
                ),
                _dummy_request(),
            )
        self.assertEqual(mismatch.exception.status_code, 400)

        reg = self._register()
        status = get_pending_registration(reg["pending_token"])
        self.assertEqual(status["pending_token"], reg["pending_token"])

        cancel_resp = delete_pending_registration(reg["pending_token"])
        self.assertTrue(cancel_resp["ok"])

        with self.assertRaises(HTTPException) as after_cancel:
            get_pending_registration(reg["pending_token"])
        self.assertEqual(after_cancel.exception.status_code, 404)

    def test_smtp_configuration_validation_and_env_loading(self):
        set_email_sender_for_tests(None)
        smtp_keys = [
            "SMTP_HOST",
            "SMTP_PORT",
            "SMTP_USERNAME",
            "SMTP_PASSWORD",
            "SMTP_FROM_EMAIL",
            "SMTP_FROM_NAME",
            "SMTP_USE_TLS",
        ]
        with patch.dict(os.environ, {k: "" for k in smtp_keys}, clear=False):
            ok, msg = validate_smtp_configuration()
            self.assertFalse(ok)
            self.assertFalse(is_smtp_configured())
            self.assertIn("SMTP_HOST", msg)

            with self.assertRaises(EmailDeliveryError):
                send_verification_email("user@example.com", "User", "123456")

            # Missing credentials with remote Gmail host
            os.environ["SMTP_HOST"] = "smtp.gmail.com"
            os.environ["SMTP_PORT"] = "587"
            os.environ["SMTP_FROM_EMAIL"] = "admin@gmail.com"
            ok_no_auth, msg_no_auth = validate_smtp_configuration()
            self.assertFalse(ok_no_auth)
            self.assertIn("SMTP_USERNAME", msg_no_auth)

            # Incomplete credentials (username without password)
            os.environ["SMTP_USERNAME"] = "admin@gmail.com"
            ok_half, msg_half = validate_smtp_configuration()
            self.assertFalse(ok_half)
            self.assertIn("incomplete", msg_half.lower())

            # Invalid port
            os.environ["SMTP_PASSWORD"] = "app-pass-placeholder"
            os.environ["SMTP_PORT"] = "not-a-port"
            ok_port, _ = validate_smtp_configuration()
            self.assertFalse(ok_port)

            # Complete valid Gmail SMTP config
            os.environ["SMTP_PORT"] = "587"
            os.environ["SMTP_USE_TLS"] = "true"
            ok_valid, msg_valid = validate_smtp_configuration()
            self.assertTrue(ok_valid)
            self.assertEqual(msg_valid, "")
            self.assertTrue(is_smtp_configured())

        # Verify load_local_env_file loads missing keys without overriding existing env vars
        env_path = os.path.join(OTP_TEST_DIR, ".test.env")
        with open(env_path, "w", encoding="utf-8") as fh:
            fh.write('SMTP_HOST="smtp.gmail.com"\nSMTP_PORT=587\n')
        with patch.dict(os.environ, {"SMTP_HOST": "already-set.example"}, clear=False):
            os.environ.pop("SMTP_PORT", None)
            self.assertTrue(load_local_env_file(env_path))
            self.assertEqual(os.environ["SMTP_HOST"], "already-set.example")
            self.assertEqual(os.environ["SMTP_PORT"], "587")

    def test_mocked_smtp_multi_domain_delivery_headers_and_observability(self):
        import smtplib
        from email import message_from_string
        from unittest.mock import MagicMock

        set_email_sender_for_tests(None)
        env = {
            "EMAIL_PROVIDER": "",
            "SMTP_HOST": "smtp.gmail.com",
            "SMTP_PORT": "587",
            "SMTP_USERNAME": "admin@gmail.com",
            "SMTP_PASSWORD": "test-app-password-placeholder",
            "SMTP_FROM_EMAIL": "admin@gmail.com",
            "SMTP_FROM_NAME": "BRAINOVA",
            "SMTP_USE_TLS": "true",
        }
        domains = [
            "user1@gmail.com",
            "user2@outlook.com",
            "user3@yahoo.com",
            "user4@icloud.com",
            "student@stanford.edu",
            "dev@acme-corp.com",
        ]
        sent_calls = []

        class FakeSmtp:
            def __init__(self, host, port, timeout=8):
                self.host = host
                self.port = port
                self.timeout = timeout

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def ehlo(self):
                return (250, b"OK")

            def starttls(self):
                return (220, b"Ready")

            def login(self, user, pw):
                return (235, b"Accepted")

            def sendmail(self, from_addr, to_addrs, msg_str):
                sent_calls.append((from_addr, to_addrs, msg_str))
                return {}

        with patch.dict(os.environ, env, clear=False), patch.object(smtplib, "SMTP", FakeSmtp):
            for addr in domains:
                result = send_verification_email(addr, "Learner", "012345")
                self.assertEqual(result.status, DELIVERY_STATUS_ACCEPTED)
                self.assertEqual(result.provider, "gmail_smtp")
                self.assertEqual(result.recipient_domain, addr.split("@")[1])
                self.assertEqual(result.smtp_code, 250)

        self.assertEqual(len(sent_calls), len(domains))
        for addr, (from_addr, to_addrs, raw_msg) in zip(domains, sent_calls):
            self.assertEqual(from_addr, "admin@gmail.com")
            self.assertEqual(to_addrs, [addr])
            parsed = message_from_string(raw_msg)
            self.assertEqual(parsed["To"], addr)
            self.assertIsNotNone(parsed["Date"])
            self.assertIsNotNone(parsed["Message-ID"])
            self.assertIsNotNone(parsed["Reply-To"])

        with get_db() as conn:
            logs = conn.execute("SELECT * FROM email_delivery_logs").fetchall()
            self.assertEqual(len(logs), len(domains))
            for row in logs:
                self.assertNotIn("@", row["recipient_domain"])
                self.assertEqual(row["status"], DELIVERY_STATUS_ACCEPTED)

    def test_mocked_smtp_rejections_auth_failure_timeout_delay_and_suppression(self):
        import smtplib
        import time

        set_email_sender_for_tests(None)
        env = {
            "EMAIL_PROVIDER": "",
            "SMTP_HOST": "smtp.gmail.com",
            "SMTP_PORT": "587",
            "SMTP_USERNAME": "admin@gmail.com",
            "SMTP_PASSWORD": "test-app-password-placeholder",
            "SMTP_FROM_EMAIL": "admin@gmail.com",
            "SMTP_USE_TLS": "true",
        }

        # 1. Partial recipient rejection via sendmail() return dict
        class PartialRefusalSmtp:
            def __init__(self, *a, **kw): pass
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def ehlo(self): pass
            def starttls(self): pass
            def login(self, u, p): pass
            def sendmail(self, from_addr, to_addrs, msg):
                return {to_addrs[0]: (550, b"5.1.1 User unknown")}

        with patch.dict(os.environ, env, clear=False), patch.object(smtplib, "SMTP", PartialRefusalSmtp):
            with self.assertRaises(HTTPException) as exc:
                self._register(email="baduser@outlook.com")
            self.assertEqual(exc.exception.status_code, 503)

        with get_db() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) AS cnt FROM users").fetchone()["cnt"], 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) AS cnt FROM pending_registrations").fetchone()["cnt"], 0)
            last_log = conn.execute("SELECT * FROM email_delivery_logs ORDER BY created_at DESC LIMIT 1").fetchone()
            self.assertEqual(last_log["status"], DELIVERY_STATUS_REJECTED)
            self.assertEqual(last_log["error_category"], "recipient_rejected")
            self.assertEqual(last_log["smtp_code"], 550)

        # 2. Full SMTPRecipientsRefused
        class RefusedSmtp(PartialRefusalSmtp):
            def sendmail(self, from_addr, to_addrs, msg):
                raise smtplib.SMTPRecipientsRefused({to_addrs[0]: (550, b"Rejected")})

        with patch.dict(os.environ, env, clear=False), patch.object(smtplib, "SMTP", RefusedSmtp):
            with self.assertRaises(EmailDeliveryError):
                send_verification_email("nobody@yahoo.com", "Nobody", "123456")

        # 3. Authentication failure
        class AuthFailSmtp(PartialRefusalSmtp):
            def login(self, u, p):
                raise smtplib.SMTPAuthenticationError(535, b"5.7.8 Username and Password not accepted")

        with patch.dict(os.environ, env, clear=False), patch.object(smtplib, "SMTP", AuthFailSmtp):
            with self.assertRaises(EmailDeliveryError):
                send_verification_email("user@gmail.com", "User", "123456")

        # 4. Connection timeout
        class TimeoutSmtp:
            def __init__(self, *a, **kw):
                raise TimeoutError("timed out")

        with patch.dict(os.environ, env, clear=False), patch.object(smtplib, "SMTP", TimeoutSmtp):
            with self.assertRaises(EmailDeliveryError):
                send_verification_email("user@icloud.com", "User", "123456")

        # 5. Delayed response latency measurement + webhook delivered/bounced + suppression
        class DelayedSmtp(PartialRefusalSmtp):
            def sendmail(self, from_addr, to_addrs, msg):
                time.sleep(0.05)
                return {}

        with patch.dict(os.environ, env, clear=False), patch.object(smtplib, "SMTP", DelayedSmtp):
            res = send_verification_email("delayed@university.edu", "Student", "654321")
            self.assertGreaterEqual(res.submit_duration_ms, 40.0)
            record_provider_webhook_event(correlation_id=res.correlation_id, event_type="delivered", provider="webhook")
            with get_db() as conn:
                row = conn.execute(
                    "SELECT status FROM email_delivery_logs WHERE correlation_id = ?",
                    (res.correlation_id,),
                ).fetchone()
                self.assertEqual(row["status"], DELIVERY_STATUS_DELIVERED)

            # Bounce adds address hash to suppression list and blocks future sends
            res_bounce = send_verification_email("bounced@corp.com", "Corp", "654321")
            record_provider_webhook_event(
                correlation_id=res_bounce.correlation_id,
                event_type="bounced",
                recipient_email="bounced@corp.com",
                provider="webhook",
            )
            with self.assertRaises(EmailDeliveryError):
                send_verification_email("bounced@corp.com", "Corp", "111111")

    def test_resend_provider_delivery_rejections_rate_limit_timeout_and_duplicate_webhooks(self):
        import io
        import json
        import urllib.error
        import urllib.request

        set_email_sender_for_tests(None)
        env = {
            "EMAIL_PROVIDER": "resend",
            "EMAIL_API_KEY": "re_test_placeholder_key",
            "EMAIL_SENDER_DOMAIN": "mail.brainova.example",
            "SMTP_FROM_EMAIL": "noreply@mail.brainova.example",
            "SMTP_FROM_NAME": "BRAINOVA",
            "EMAIL_WEBHOOK_SECRET": "webhook-secret-test",
        }

        class FakeResp:
            def __init__(self, status, body_dict):
                self.status = status
                self._body = json.dumps(body_dict).encode("utf-8")

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return self._body

        with patch.dict(os.environ, env, clear=False):
            self.assertTrue(is_smtp_configured())

            # 1. Successful Resend API submission
            with patch.object(urllib.request, "urlopen", return_value=FakeResp(200, {"id": "re_msg_999"})):
                reg = self._register(email="newuser@outlook.com")
            self.assertEqual(reg["delivery_status"], DELIVERY_STATUS_ACCEPTED)
            self.assertNotIn("otp_code", reg)

            # 2. Webhook delivered by provider_message_id + duplicate event deduplication
            wh_req = Request(
                {
                    "type": "http",
                    "method": "POST",
                    "path": "/api/email/webhook",
                    "query_string": b"",
                    "headers": [
                        (b"x-email-webhook-secret", b"webhook-secret-test"),
                        (b"svix-id", b"evt_resend_1"),
                    ],
                    "client": ("127.0.0.1", 12345),
                }
            )
            wh_payload = {"type": "email.delivered", "data": {"email_id": "re_msg_999"}}
            wh1 = receive_email_provider_webhook(wh_payload, wh_req)
            self.assertFalse(wh1["duplicate"])
            self.assertEqual(wh1["status"], DELIVERY_STATUS_DELIVERED)

            wh2 = receive_email_provider_webhook(wh_payload, wh_req)
            self.assertTrue(wh2["duplicate"])

            # 3. 422 rejected, 429 rate limit, and TimeoutError
            err_422 = urllib.error.HTTPError("https://api.resend.com/emails", 422, "Unprocessable", {}, io.BytesIO(b"{}"))
            with patch.object(urllib.request, "urlopen", side_effect=err_422):
                with self.assertRaises(EmailDeliveryError):
                    send_verification_email("bad@yahoo.com", "Bad", "123456")

            err_429 = urllib.error.HTTPError("https://api.resend.com/emails", 429, "Too Many Requests", {}, io.BytesIO(b"{}"))
            with patch.object(urllib.request, "urlopen", side_effect=err_429):
                with self.assertRaises(EmailDeliveryError):
                    send_verification_email("rate@gmail.com", "Rate", "123456")

            with patch.object(urllib.request, "urlopen", side_effect=TimeoutError("timed out")):
                with self.assertRaises(EmailDeliveryError):
                    send_verification_email("slow@icloud.com", "Slow", "123456")

        # 4. Subsequent login after registration does not require OTP
        set_email_sender_for_tests(self._capture_email)
        reg2 = self._register(email="returning@stanford.edu")
        otp2 = self.sent_emails[-1]["otp_code"]
        verify_email_otp(VerifyEmailRequest(pending_token=reg2["pending_token"], otp_code=otp2))
        self.sent_emails.clear()
        login_res = login(LoginRequest(email="returning@stanford.edu", password="StrongPassword123!"))
        self.assertIn("token", login_res)
        self.assertEqual(len(self.sent_emails), 0)


if __name__ == "__main__":
    unittest.main()
