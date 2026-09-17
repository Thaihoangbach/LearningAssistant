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
from app.models import Conversation, Document, User
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
            self.convo_id = str(uuid.uuid4())
            db.add(Conversation(id=self.convo_id, user_id=self.owner_id, course_name=None))
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

    def test_attacker_cannot_reuse_owners_conversation_via_chat_ask(self):
        """Final review Fix 1 (Critical IDOR) — trước fix, assemble_context()
        tin thẳng req.conversation_id không kiểm chủ sở hữu, cho phép attacker
        đọc/ghi vào hội thoại của owner chỉ bằng cách biết ID. Dùng câu hỏi
        khớp năng lực "flashcard_due" (needs_document_scope=False) để chắc
        chắn đi thẳng tới bước kiểm chủ sở hữu hội thoại trong
        assemble_context() mà không rơi vào nhánh 400 "chưa có tài liệu" (vì
        attacker không có tài liệu nào) và không cần gọi LLM thật."""
        res = self.client.post(
            "/chat/ask",
            json={"question": "Tôi còn thẻ nào đến hạn ôn không?", "conversation_id": self.convo_id},
        )
        self.assertEqual(res.status_code, 404)

        # Hội thoại của owner không bị attacker ghi thêm message nào vào.
        db = self.SessionLocal()
        try:
            convo = db.query(Conversation).filter(Conversation.id == self.convo_id).first()
            self.assertIsNotNone(convo)
            self.assertEqual(convo.user_id, self.owner_id)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
