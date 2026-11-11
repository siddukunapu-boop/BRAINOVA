"""Focused, socket-free tests for authentication and private audio playback tokens."""

import os
import sys
import unittest

os.environ.setdefault("AETHER_JWT_SECRET", "unit-test-signing-key-with-at-least-32-chars")
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from fastapi import HTTPException

from backend.auth import (
    create_audio_playback_token,
    create_access_token,
    decode_audio_playback_token,
    decode_access_token,
)


class AuthenticationSecurityUnitTests(unittest.TestCase):
    def test_regular_session_token_round_trips(self):
        token = create_access_token("usr_test", "student@example.edu")
        decoded = decode_access_token(token)
        self.assertEqual(decoded["sub"], "usr_test")
        self.assertEqual(decoded["email"], "student@example.edu")

    def test_audio_token_is_scoped_to_one_owner_and_output(self):
        token = create_audio_playback_token("usr_test", "std_audio_test")
        self.assertEqual(decode_audio_playback_token(token, "std_audio_test"), "usr_test")
        with self.assertRaises(HTTPException) as wrong_output:
            decode_audio_playback_token(token, "std_other_output")
        self.assertEqual(wrong_output.exception.status_code, 401)

    def test_regular_session_token_cannot_authorize_audio(self):
        token = create_access_token("usr_test", "student@example.edu")
        with self.assertRaises(HTTPException) as invalid_scope:
            decode_audio_playback_token(token, "std_audio_test")
        self.assertEqual(invalid_scope.exception.status_code, 401)


if __name__ == "__main__":
    unittest.main(verbosity=2)
