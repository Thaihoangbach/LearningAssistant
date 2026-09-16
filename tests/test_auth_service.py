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


if __name__ == "__main__":
    unittest.main()
