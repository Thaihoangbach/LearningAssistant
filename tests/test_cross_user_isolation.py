"""Regression Phase 3 — user A không được đọc/sửa/xoá resource của user B dù
biết ID, kể cả sau khi mọi router đã đổi sang Depends(get_current_user)."""
import os
import sys
import unittest
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, os.path.dirname(__file__))

from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models import Document, User
from app.routers.auth import get_current_user
from pg_test_helpers import fresh_test_session_factory


class CrossUserIsolationTest(unittest.TestCase):
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

        self.owner_id = str(uuid.uuid4())
        self.attacker_id = str(uuid.uuid4())
        db = self.SessionLocal()
        try:
            db.add(User(id=self.owner_id, email=f"{self.owner_id}@test.local", password_hash="x", display_name="Chủ"))
            db.add(User(id=self.attacker_id, email=f"{self.attacker_id}@test.local", password_hash="x", display_name="Kẻ khác"))
            db.flush()
            self.doc_id = str(uuid.uuid4())
            db.add(Document(id=self.doc_id, user_id=self.owner_id, file_name="bimat.pdf", status="sẵn sàng"))
            db.commit()
        finally:
            db.close()

        self.attacker = User(
            id=self.attacker_id, email=f"{self.attacker_id}@test.local", password_hash="x", display_name="Kẻ khác"
        )
        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = lambda: self.attacker
        self.client = TestClient(app)
        self.addCleanup(app.dependency_overrides.clear)

    def test_attacker_cannot_see_owners_document_in_list(self):
        res = self.client.get("/documents")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), [])

    def test_attacker_cannot_fetch_owners_document_outline_by_id(self):
        res = self.client.get(f"/documents/{self.doc_id}/outline")
        self.assertEqual(res.status_code, 404)

    def test_attacker_cannot_delete_owners_document_by_id(self):
        res = self.client.delete(f"/documents/{self.doc_id}")
        self.assertEqual(res.status_code, 404)

        db = self.SessionLocal()
        try:
            self.assertIsNotNone(db.query(Document).filter(Document.id == self.doc_id).first())
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
