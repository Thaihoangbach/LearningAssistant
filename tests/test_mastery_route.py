"""Integration test cho GET /mastery, /mastery/mistakes — trước đây router
này chỉ có unit test cho service (tests/test_mastery.py), chưa có test cấp
route qua TestClient."""
import os
import sys
import unittest
import uuid
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, os.path.dirname(__file__))

from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models import Attempt, Document, MasteryScore, Quiz, QuizItem, Topic, User
from app.routers.auth import get_current_user
from pg_test_helpers import fresh_test_session_factory


class MasteryRouteTest(unittest.TestCase):
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
            db.add(User(id=self.user_id, email=f"{self.user_id}@test.local", password_hash="x", display_name="Hoa"))
            db.add(User(id=self.other_user_id, email=f"{self.other_user_id}@test.local", password_hash="x", display_name="Khac"))
            db.flush()
            topic = Topic(user_id=self.user_id, name="Chuẩn hoá CSDL", course_name="CSDL")
            db.add(topic)
            db.flush()
            db.add(MasteryScore(user_id=self.user_id, topic_id=topic.id, score=0.4, updated_at=datetime.utcnow()))
            document = Document(user_id=self.user_id, file_name="a.pdf", status="sẵn sàng")
            db.add(document)
            db.flush()
            quiz = Quiz(user_id=self.user_id, document_id=document.id)
            db.add(quiz)
            db.flush()
            item = QuizItem(
                quiz_id=quiz.id, topic_id=topic.id, question="Q1?", options="[]",
                correct_answer="A", explanation="vì A đúng",
            )
            db.add(item)
            db.flush()
            db.add(Attempt(user_id=self.user_id, quiz_item_id=item.id, topic_id=topic.id, is_correct=False, selected_answer="B"))

            # Chủ đề + điểm mastery của NGƯỜI DÙNG KHÁC — thiếu 2 dòng này thì
            # test isolation phía dưới pass ngay cả khi filter user_id bị xoá
            # hoàn toàn, vì chẳng có gì của other_user_id để lộ ra (final
            # review Fix 9).
            other_topic = Topic(user_id=self.other_user_id, name="Chủ đề của người khác", course_name="CSDL")
            db.add(other_topic)
            db.flush()
            db.add(MasteryScore(user_id=self.other_user_id, topic_id=other_topic.id, score=0.9, updated_at=datetime.utcnow()))
            db.commit()
        finally:
            db.close()

        self.current_user = User(
            id=self.user_id, email=f"{self.user_id}@test.local", password_hash="x", display_name="Hoa"
        )
        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = lambda: self.current_user
        self.client = TestClient(app)
        self.addCleanup(app.dependency_overrides.clear)

    def test_get_mastery_returns_only_current_user_topics(self):
        res = self.client.get("/mastery")
        self.assertEqual(res.status_code, 200)
        names = [t["topic_name"] for t in res.json()["topics"]]
        self.assertEqual(names, ["Chuẩn hoá CSDL"])

    def test_get_mistakes_returns_wrong_attempt(self):
        res = self.client.get("/mastery/mistakes")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json()["mistakes"]), 1)
        self.assertEqual(res.json()["mistakes"][0]["question"], "Q1?")


if __name__ == "__main__":
    unittest.main()
