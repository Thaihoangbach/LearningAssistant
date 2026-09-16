import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy.exc import IntegrityError

from app.models import User
from pg_test_helpers import fresh_test_session_factory


class UserModelTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine, cls.SessionLocal = fresh_test_session_factory()

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()

    def test_password_hash_is_required(self):
        db = self.SessionLocal()
        try:
            db.add(User(id="u1", email="a@test.local", display_name="A"))
            with self.assertRaises(IntegrityError):
                db.commit()
        finally:
            db.rollback()
            db.close()

    def test_user_can_be_created_with_password_hash(self):
        db = self.SessionLocal()
        try:
            db.add(User(id="u2", email="b@test.local", display_name="B", password_hash="hashed"))
            db.commit()
            saved = db.query(User).filter(User.id == "u2").first()
            self.assertEqual(saved.password_hash, "hashed")
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
