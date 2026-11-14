"""Focused, socket-free unit tests for Phase 1 authentication, revocation, scoped tokens, and AES-256-GCM encryption."""

import datetime
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

UNIT_TEST_DIR = tempfile.mkdtemp(prefix="brainova_unit_security_")
os.environ["AETHER_DB_PATH"] = os.path.join(UNIT_TEST_DIR, "unit_security.db")
os.environ["BRAINOVA_MASTER_KEY_FILE"] = os.path.join(UNIT_TEST_DIR, ".unit_master_key")
os.environ.setdefault("AETHER_JWT_SECRET", "unit-test-signing-key-with-at-least-32-chars")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import jwt
from fastapi import HTTPException
from starlette.requests import Request

from backend.ai_engine import call_llm_json
from backend.auth import (
    JWT_ALGORITHM,
    JWT_SECRET,
    create_access_token,
    create_audio_playback_token,
    create_video_playback_token,
    decode_access_token,
    decode_audio_playback_token,
    decode_video_playback_token,
    extract_bearer_token,
    is_token_revoked,
    revoke_access_token,
)
from backend.crypto import (
    CredentialEncryptionError,
    CredentialKeyUnavailableError,
    decrypt_credential,
    encrypt_credential,
    is_encrypted_credential,
    parse_keyring_string,
    redact_sensitive_text,
)
from backend.database import get_db, init_db, utc_now


class AuthenticationSecurityUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        with get_db(commit=True) as conn:
            now = utc_now()
            for uid, email in (("usr_test", "student@example.edu"), ("usr_other", "other@example.edu")):
                conn.execute(
                    """
                    INSERT OR IGNORE INTO users (id, email, name, password_hash, role, target_role, bio, avatar_color, created_at, updated_at)
                    VALUES (?, ?, 'Test User', 'hash', 'student', 'Developer', '', '#6366f1', ?, ?)
                    """,
                    (uid, email, now, now),
                )

    def test_regular_session_token_round_trips_with_jti_and_scope(self):
        token = create_access_token("usr_test", "student@example.edu")
        decoded = decode_access_token(token)
        self.assertEqual(decoded["sub"], "usr_test")
        self.assertEqual(decoded["email"], "student@example.edu")
        self.assertEqual(decoded["scope"], "session")
        self.assertTrue(decoded.get("jti", "").startswith("jti_"))

    def test_legacy_token_without_jti_or_scope_is_handled_and_revocable(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        legacy_payload = {
            "sub": "usr_test",
            "email": "student@example.edu",
            "iat": int(now.timestamp()),
            "exp": int((now + datetime.timedelta(hours=1)).timestamp()),
        }
        legacy_token = jwt.encode(legacy_payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
        decoded = decode_access_token(legacy_token)
        self.assertEqual(decoded["sub"], "usr_test")

        # Revoking legacy token uses deterministic sha256 digest in revoked_tokens
        rev_info = revoke_access_token(legacy_token, expected_user_id="usr_test")
        self.assertTrue(rev_info["jti"].startswith("sha256:"))
        with self.assertRaises(HTTPException) as exc:
            decode_access_token(legacy_token)
        self.assertEqual(exc.exception.status_code, 401)

    def test_expired_and_tampered_tokens_are_rejected(self):
        expired = create_access_token(
            "usr_test",
            "student@example.edu",
            expires_delta=datetime.timedelta(seconds=-10),
        )
        with self.assertRaises(HTTPException) as exp_err:
            decode_access_token(expired)
        self.assertEqual(exp_err.exception.status_code, 401)

        valid = create_access_token("usr_test", "student@example.edu")
        tampered = valid[:-4] + ("AAAA" if not valid.endswith("AAAA") else "BBBB")
        with self.assertRaises(HTTPException) as tamp_err:
            decode_access_token(tampered)
        self.assertEqual(tamp_err.exception.status_code, 401)

    def test_token_revocation_and_cross_user_revocation_guard(self):
        token = create_access_token("usr_test", "student@example.edu")
        # Another user cannot revoke usr_test's token
        with self.assertRaises(HTTPException) as forbidden:
            revoke_access_token(token, expected_user_id="usr_other")
        self.assertEqual(forbidden.exception.status_code, 403)

        # Owner revokes own token
        rev = revoke_access_token(token, expected_user_id="usr_test")
        self.assertTrue(is_token_revoked(rev["jti"]))
        with self.assertRaises(HTTPException) as revoked_err:
            decode_access_token(token)
        self.assertEqual(revoked_err.exception.status_code, 401)

    def test_query_parameter_token_is_rejected(self):
        token = create_access_token("usr_test", "student@example.edu")
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/api/roadmaps",
            "query_string": f"token={token}".encode("utf-8"),
            "headers": [],
        }
        req = Request(scope)
        with self.assertRaises(HTTPException) as q_err:
            extract_bearer_token(req, authorization=f"Bearer {token}")
        self.assertEqual(q_err.exception.status_code, 401)

    def test_audio_and_video_tokens_are_scoped_and_isolated(self):
        aud_token = create_audio_playback_token("usr_test", "std_audio_test")
        vid_token = create_video_playback_token("usr_test", "std_video_test")
        self.assertEqual(decode_audio_playback_token(aud_token, "std_audio_test"), "usr_test")
        self.assertEqual(decode_video_playback_token(vid_token, "std_video_test"), "usr_test")

        with self.assertRaises(HTTPException) as wrong_output:
            decode_audio_playback_token(aud_token, "std_other_output")
        self.assertEqual(wrong_output.exception.status_code, 401)

        # Scoped playback tokens cannot be used as general API session tokens
        for media_tok in (aud_token, vid_token):
            with self.assertRaises(HTTPException) as media_as_session:
                decode_access_token(media_tok)
            self.assertEqual(media_as_session.exception.status_code, 401)

    def test_regular_session_token_cannot_authorize_audio_or_video(self):
        token = create_access_token("usr_test", "student@example.edu")
        with self.assertRaises(HTTPException) as invalid_aud:
            decode_audio_playback_token(token, "std_audio_test")
        self.assertEqual(invalid_aud.exception.status_code, 401)
        with self.assertRaises(HTTPException) as invalid_vid:
            decode_video_playback_token(token, "std_video_test")
        self.assertEqual(invalid_vid.exception.status_code, 401)

    def test_aes256_gcm_encryption_aad_tamper_and_jwt_secret_separation(self):
        # Master key must never reuse JWT secret
        with self.assertRaises(CredentialKeyUnavailableError):
            parse_keyring_string(JWT_SECRET, jwt_secret_to_forbid=JWT_SECRET)

        ct = encrypt_credential("AIzaSyUnitSecretKey987654321", aad_context="usr_test:gemini_api_key")
        self.assertTrue(is_encrypted_credential(ct))
        self.assertNotIn("AIzaSyUnitSecretKey987654321", ct)
        pt = decrypt_credential(ct, aad_context="usr_test:gemini_api_key")
        self.assertEqual(pt, "AIzaSyUnitSecretKey987654321")

        # Cross-user or cross-column AAD mismatch must fail
        with self.assertRaises(CredentialEncryptionError):
            decrypt_credential(ct, aad_context="usr_other:gemini_api_key")
        with self.assertRaises(CredentialEncryptionError):
            decrypt_credential(ct, aad_context="usr_test:openai_api_key")

        # Tampered ciphertext payload must fail GCM tag verification
        flipped = ct[:-2] + ("AA" if not ct.endswith("AA") else "BB")
        with self.assertRaises(CredentialEncryptionError):
            decrypt_credential(flipped, aad_context="usr_test:gemini_api_key")

    def test_gemini_uses_x_goog_api_key_header_and_redaction_strips_secrets(self):
        captured = {}

        class DummyResp:
            status_code = 200

            def json(self):
                return {"candidates": [{"content": {"parts": [{"text": '{"ok": true}'}]}}]}

        class DummyClient:
            def __init__(self, *args, **kwargs):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def post(self, url, **kwargs):
                captured["url"] = url
                captured["kwargs"] = kwargs
                return DummyResp()

        with patch("backend.ai_engine.httpx.Client", DummyClient):
            res, provider = call_llm_json(
                "System",
                "Prompt",
                user_prefs={
                    "ai_provider": "gemini",
                    "gemini_api_key": "AIzaSyTestHeaderOnlyKey1234567890",
                    "gemini_model": "gemini-2.5-flash",
                },
            )
        self.assertEqual(res, {"ok": True})
        self.assertNotIn("key=", captured["url"])
        self.assertNotIn("params", captured["kwargs"])
        self.assertEqual(
            captured["kwargs"]["headers"]["x-goog-api-key"],
            "AIzaSyTestHeaderOnlyKey1234567890",
        )

        # Verify sensitive error redaction preserves diagnostic context while scrubbing keys/tokens
        raw_err = (
            "HTTP 401 from provider: key=AIzaSySecretKey123456789012345 "
            "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test "
            "openai=sk-proj-1234567890abcdefghijklmnop"
        )
        redacted = redact_sensitive_text(raw_err)
        self.assertIn("HTTP 401 from provider", redacted)
        self.assertNotIn("AIzaSySecretKey", redacted)
        self.assertNotIn("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9", redacted)
        self.assertNotIn("sk-proj-1234567890", redacted)


if __name__ == "__main__":
    unittest.main(verbosity=2)
