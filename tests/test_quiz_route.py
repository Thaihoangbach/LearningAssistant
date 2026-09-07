"""Integration test cho POST /quiz/submit qua FastAPI TestClient + Postgres
THẬT — router này (như mọi router khác, xem báo cáo rà soát) trước đây không
có test nào. Hai việc khoá lại ở đây:

1. MED-5 — quiz_item_id KHÔNG thuộc về user_id gửi request phải bị từ chối
   (404), không được âm thầm ghi Attempt gắn cho user đó bằng câu hỏi của
   người khác.
2. BUG-3 (đã sửa tận gốc) — 2 lượt nộp bài GẦN NHAU cho cùng (user_id,
   topic_id) không được tạo ra 2 dòng MasteryScore trùng nhau. Router dùng
   `sqlalchemy.dialects.postgresql.insert(...).on_conflict_do_update(...)`
   (Postgres-SPECIFIC) nên bắt buộc phải test trên Postgres thật, không còn
   chạy được trên SQLite như bản trước.

Mỗi test tự tạo user_id/document_id/... RIÊNG (uuid4) trong setUp — tránh
đụng UNIQUE/FK giữa các test chạy trong cùng schema (setUpClass chỉ
drop/create MỘT LẦN cho cả file, xem tests/pg_test_helpers.py).
"""
import os
import sys
import unittest
import uuid
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models import Document, QuizItem, Quiz, Topic, User
from pg_test_helpers import fresh_test_session_factory


def _fake_embed_query(text):
    # submit_attempt() ghi ký ức episodic qua record_event(), vốn KHÔNG nhận
    # embed_fn override từ router (xem app/routers/quiz.py) — router test này
    # chạy qua HTTP thật nên không có chỗ nào để tiêm fake vào giữa đường.
    # Patch thẳng app.ingestion.embedder.embed_query để tránh gọi Cohere API
    # thật — router chỉ cần MỘT vector cố định chiều (khớp EMBEDDING_DIM ở
    # models.py để giống dữ liệu thật).
    return np.zeros(1024, dtype="float32")


class QuizSubmitRouteTest(unittest.TestCase):
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

        embed_patcher = patch("app.ingestion.embedder.embed_query", side_effect=_fake_embed_query)
        embed_patcher.start()
        self.addCleanup(embed_patcher.stop)

        # Hai user, mỗi user 1 document + 1 topic + 1 quiz + 1 quiz_item — đủ
        # để kiểm tra ranh giới sở hữu (MED-5) và race mastery (BUG-3). uuid4
        # cho mọi id để không đụng dữ liệu của test khác trong cùng class.
        self.alice_id = str(uuid.uuid4())
        self.bob_id = str(uuid.uuid4())
        self.alice_topic_id = str(uuid.uuid4())
        self.alice_item_id = str(uuid.uuid4())

        db = self.SessionLocal()
        try:
            db.add(User(id=self.alice_id, email=f"{self.alice_id}@test.local", display_name="Alice"))
            db.add(User(id=self.bob_id, email=f"{self.bob_id}@test.local", display_name="Bob"))
            # flush() TRUNG GIAN — SQLAlchemy không tự sắp thứ tự INSERT đúng
            # khi một dòng phụ thuộc HAI FK khác nhau (Quiz -> users VÀ
            # documents) trong CÙNG một flush với cả hai bảng cha; đo được
            # thật: không flush() ở đây thì INSERT quizzes chạy TRƯỚC users,
            # vỡ FK, dù đã db.add(User(...)) trước đó trong cùng hàm. Tách
            # flush theo từng "tầng" phụ thuộc (users -> documents/topics ->
            # quizzes -> quiz_items) là cách chắc chắn né lỗi sắp xếp này.
            db.flush()

            document_id = str(uuid.uuid4())
            db.add(Document(id=document_id, user_id=self.alice_id, file_name="a.pdf", status="sẵn sàng"))
            db.add(Topic(id=self.alice_topic_id, user_id=self.alice_id, name="Chủ đề A"))
            db.flush()

            quiz_id = str(uuid.uuid4())
            db.add(Quiz(id=quiz_id, user_id=self.alice_id, document_id=document_id))
            db.flush()

            db.add(
                QuizItem(
                    id=self.alice_item_id, quiz_id=quiz_id, topic_id=self.alice_topic_id,
                    question="1+1=?", options="[\"1\",\"2\"]", correct_answer="2",
                )
            )
            db.commit()
        finally:
            db.close()

    def test_submitting_someone_elses_quiz_item_is_rejected(self):
        res = self.client.post(
            "/quiz/submit",
            json={"user_id": self.bob_id, "quiz_item_id": self.alice_item_id, "selected_answer": "2"},
        )

        self.assertEqual(res.status_code, 404)

    def test_owner_can_submit_their_own_quiz_item(self):
        res = self.client.post(
            "/quiz/submit",
            json={"user_id": self.alice_id, "quiz_item_id": self.alice_item_id, "selected_answer": "2"},
        )

        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["is_correct"])

    def test_repeated_submits_keep_exactly_one_mastery_row(self):
        """Xác nhận upsert (`INSERT ... ON CONFLICT DO UPDATE` trên
        UniqueConstraint(user_id, topic_id), xem app/routers/quiz.py) hội tụ
        đúng về MỘT dòng MasteryScore dù gọi lặp lại nhiều lần — bằng chứng
        gián tiếp cho race BUG-3: ràng buộc UNIQUE ở tầng DB khiến 2 INSERT
        cùng (user_id, topic_id), dù có chạy đồng thời thật, cũng không thể
        nào tạo ra 2 dòng (một trong hai sẽ tự động rơi vào nhánh UPDATE của
        CHÍNH CÂU LỆNH đó, không phải race ở tầng ứng dụng để kiểm bằng
        thread nữa) — khác cơ chế khoá ứng dụng trước đây, đúng đắn của
        UNIQUE constraint không phụ thuộc timing nên không cần dựng lại kịch
        bản đa luồng để chứng minh."""
        for _ in range(5):
            res = self.client.post(
                "/quiz/submit",
                json={"user_id": self.alice_id, "quiz_item_id": self.alice_item_id, "selected_answer": "2"},
            )
            self.assertEqual(res.status_code, 200)

        db = self.SessionLocal()
        try:
            from app.models import MasteryScore

            rows = (
                db.query(MasteryScore)
                .filter(MasteryScore.user_id == self.alice_id, MasteryScore.topic_id == self.alice_topic_id)
                .all()
            )
        finally:
            db.close()

        self.assertEqual(len(rows), 1)


if __name__ == "__main__":
    unittest.main()
