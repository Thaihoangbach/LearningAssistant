"""Integration test cho POST /chat/ask, GET /chat/conversations — trước đây
chỉ có test hành vi capability riêng lẻ (test_chat_study_plan_redirect.py),
chưa có test cấp route xác nhận Depends(get_current_user) hoạt động đúng và
cô lập đúng giữa 2 user."""
import os
import sys
import unittest
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, os.path.dirname(__file__))

from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models import Conversation, User
from app.routers.auth import get_current_user
from pg_test_helpers import fresh_test_session_factory


class ChatRouteTest(unittest.TestCase):
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

        self.user_id = str(uuid.uuid4())
        self.other_user_id = str(uuid.uuid4())
        db = self.SessionLocal()
        try:
            # fresh_test_session_factory() chỉ dựng lại schema MỘT LẦN cho cả
            # class (setUpClass), còn setUp chạy lại trước TỪNG test — id hội
            # thoại cố định ở đây sẽ đụng khoá chính từ test trước nếu không
            # dọn. (User dùng uuid ngẫu nhiên nên không cần dọn.)
            db.query(Conversation).filter(
                Conversation.id.in_(["convo-mine", "convo-other"])
            ).delete(synchronize_session=False)
            db.add(User(id=self.user_id, email=f"{self.user_id}@test.local", password_hash="x", display_name="Hoa"))
            db.add(
                User(
                    id=self.other_user_id,
                    email=f"{self.other_user_id}@test.local",
                    password_hash="x",
                    display_name="Khac",
                )
            )
            db.add(Conversation(id="convo-mine", user_id=self.user_id, course_name=None))
            db.add(Conversation(id="convo-other", user_id=self.other_user_id, course_name=None))
            db.commit()
        finally:
            db.close()

        # Object dùng để override get_current_user PHẢI là instance riêng,
        # KHÔNG tái dùng object đã db.add() ở trên (bị SQLAlchemy expire sau
        # commit) — ở đây chỉ cần một User "giả" mang đúng id để router đọc
        # current_user.id.
        self.current_user = User(
            id=self.user_id, email=f"{self.user_id}@test.local", password_hash="x", display_name="Hoa"
        )
        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = lambda: self.current_user
        self.client = TestClient(app)
        self.addCleanup(app.dependency_overrides.clear)

    def test_list_conversations_only_returns_current_user_conversations(self):
        res = self.client.get("/chat/conversations")
        self.assertEqual(res.status_code, 200)
        ids = [c["id"] for c in res.json()]
        self.assertEqual(ids, ["convo-mine"])

    def test_get_conversation_of_other_user_returns_404(self):
        res = self.client.get("/chat/conversations/convo-other")
        self.assertEqual(res.status_code, 404)

    def test_ask_without_ready_documents_returns_400(self):
        res = self.client.post("/chat/ask", json={"question": "test?"})
        self.assertEqual(res.status_code, 400)


if __name__ == "__main__":
    unittest.main()
