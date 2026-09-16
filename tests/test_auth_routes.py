import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-do-not-use-in-prod")

from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from pg_test_helpers import fresh_test_session_factory


class RegisterRouteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine, cls.SessionLocal = fresh_test_session_factory()

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()

    def setUp(self):
        def override_get_db():
            db = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)
        self.addCleanup(app.dependency_overrides.clear)

    def test_register_with_new_email_returns_201_and_sets_cookie(self):
        res = self.client.post(
            "/auth/register",
            json={"email": "Bach@Example.com", "password": "matkhau123", "display_name": "Bách"},
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()["email"], "bach@example.com")
        self.assertNotIn("password_hash", res.json())
        self.assertIn("access_token", res.cookies)

    def test_register_with_duplicate_email_returns_409(self):
        payload = {"email": "dup@example.com", "password": "matkhau123", "display_name": "A"}
        self.client.post("/auth/register", json=payload)
        res = self.client.post("/auth/register", json=payload)
        self.assertEqual(res.status_code, 409)

    def test_register_with_short_password_returns_422(self):
        res = self.client.post(
            "/auth/register",
            json={"email": "short@example.com", "password": "abc", "display_name": "A"},
        )
        self.assertEqual(res.status_code, 422)


if __name__ == "__main__":
    unittest.main()
