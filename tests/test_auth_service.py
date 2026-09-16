import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-do-not-use-in-prod")

from app.services.auth_service import hash_password, verify_password


class PasswordHashingTest(unittest.TestCase):
    def test_verify_password_with_correct_password_returns_true(self):
        hashed = hash_password("correct-horse-battery")
        self.assertTrue(verify_password("correct-horse-battery", hashed))

    def test_verify_password_with_wrong_password_returns_false(self):
        hashed = hash_password("correct-horse-battery")
        self.assertFalse(verify_password("wrong-password", hashed))

    def test_hash_password_does_not_return_plaintext(self):
        hashed = hash_password("correct-horse-battery")
        self.assertNotEqual(hashed, "correct-horse-battery")


from datetime import datetime, timedelta, timezone

from app.services.auth_service import (
    create_access_token,
    decode_access_token,
    get_cookie_settings,
)


class JWTTest(unittest.TestCase):
    def test_decode_access_token_returns_user_id_from_valid_token(self):
        token = create_access_token("user-123")
        self.assertEqual(decode_access_token(token), "user-123")

    def test_decode_access_token_returns_none_for_garbage_token(self):
        self.assertIsNone(decode_access_token("not-a-real-token"))

    def test_decode_access_token_returns_none_for_expired_token(self):
        import jwt as pyjwt
        from app.services.auth_service import JWT_ALGORITHM, JWT_SECRET_KEY

        expired_payload = {
            "sub": "user-123",
            "iat": datetime.now(timezone.utc) - timedelta(days=8),
            "exp": datetime.now(timezone.utc) - timedelta(days=1),
        }
        expired_token = pyjwt.encode(expired_payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
        self.assertIsNone(decode_access_token(expired_token))


class CookieSettingsTest(unittest.TestCase):
    def test_no_frontend_url_returns_dev_settings(self):
        self.assertEqual(get_cookie_settings(None), {"secure": False, "samesite": "lax"})

    def test_frontend_url_set_returns_prod_settings(self):
        self.assertEqual(
            get_cookie_settings("https://edututor.example.com"),
            {"secure": True, "samesite": "none"},
        )


if __name__ == "__main__":
    unittest.main()
