"""Integration test cho GET/DELETE /profile sau khi bỏ weak_topics/mastered_topics
(chuyển hẳn sang Dashboard, xem app/routers/mastery.py) và thêm effective_level +
effective_level_source — dòng minh bạch "hệ thống đang dùng trình độ nào, từ đâu"
mà trước đây Profile không hiển thị.

DELETE /profile là bổ sung mới: đặt lại phần TỰ KHAI (preferred_level,
learning_goal) về rỗng, KHÔNG đụng MasteryScore/Attempt — ranh giới Profile vs
Learning State phải giữ đúng kể cả ở hành vi reset.
"""
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
from app.models import LearningProfile, MasteryScore, Topic, User
from pg_test_helpers import fresh_test_session_factory


class ProfileRouteTest(unittest.TestCase):
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

        self.user_id = str(uuid.uuid4())
        db = self.SessionLocal()
        try:
            db.add(User(id=self.user_id, email=f"{self.user_id}@test.local", display_name="Dana"))
            db.commit()
        finally:
            db.close()

    def test_get_profile_without_data_returns_all_none(self):
        res = self.client.get("/profile", params={"user_id": self.user_id})
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertIsNone(body["preferred_level"])
        self.assertIsNone(body["learning_goal"])
        self.assertIsNone(body["effective_level"])
        self.assertIsNone(body["effective_level_source"])

    def test_get_profile_no_longer_returns_weak_or_mastered_topics(self):
        res = self.client.get("/profile", params={"user_id": self.user_id})
        body = res.json()
        self.assertNotIn("weak_topics", body)
        self.assertNotIn("mastered_topics", body)

    def test_effective_level_declared_wins_and_is_marked_declared(self):
        db = self.SessionLocal()
        try:
            db.add(LearningProfile(user_id=self.user_id, preferred_level="advanced"))
            db.commit()
        finally:
            db.close()

        res = self.client.get("/profile", params={"user_id": self.user_id})
        body = res.json()
        self.assertEqual(body["preferred_level"], "advanced")
        self.assertEqual(body["effective_level"], "advanced")
        self.assertEqual(body["effective_level_source"], "declared")

    def test_effective_level_inferred_from_low_mastery_when_never_declared(self):
        db = self.SessionLocal()
        try:
            topic = Topic(user_id=self.user_id, name="Backpropagation")
            db.add(topic)
            db.commit()
            db.add(
                MasteryScore(
                    user_id=self.user_id,
                    topic_id=topic.id,
                    score=0.1,
                    updated_at=datetime.utcnow(),
                )
            )
            db.commit()
        finally:
            db.close()

        res = self.client.get("/profile", params={"user_id": self.user_id})
        body = res.json()
        self.assertIsNone(body["preferred_level"])
        self.assertEqual(body["effective_level"], "beginner")
        self.assertEqual(body["effective_level_source"], "inferred")

    def test_delete_profile_resets_declared_fields(self):
        db = self.SessionLocal()
        try:
            db.add(
                LearningProfile(
                    user_id=self.user_id, preferred_level="advanced", learning_goal="Ôn thi"
                )
            )
            db.commit()
        finally:
            db.close()

        res = self.client.delete("/profile", params={"user_id": self.user_id})
        self.assertEqual(res.status_code, 200)

        res = self.client.get("/profile", params={"user_id": self.user_id})
        body = res.json()
        self.assertIsNone(body["preferred_level"])
        self.assertIsNone(body["learning_goal"])

    def test_delete_profile_without_existing_profile_is_a_noop(self):
        res = self.client.delete("/profile", params={"user_id": self.user_id})
        self.assertEqual(res.status_code, 200)

    def test_delete_profile_does_not_touch_mastery_score(self):
        db = self.SessionLocal()
        try:
            topic = Topic(user_id=self.user_id, name="Backpropagation")
            db.add(topic)
            db.commit()
            db.add(MasteryScore(user_id=self.user_id, topic_id=topic.id, score=0.8))
            db.add(LearningProfile(user_id=self.user_id, preferred_level="beginner"))
            db.commit()
        finally:
            db.close()

        self.client.delete("/profile", params={"user_id": self.user_id})

        db = self.SessionLocal()
        try:
            remaining = db.query(MasteryScore).filter(MasteryScore.user_id == self.user_id).all()
            self.assertEqual(len(remaining), 1)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
