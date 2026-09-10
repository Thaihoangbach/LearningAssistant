"""Integration test cho POST /flashcard/generate qua FastAPI TestClient +
Postgres THẬT — mirror của tests/test_quiz_route.py::QuizTopicCourseScopingTest.

Task 3 (fix root cause: khoá tra cứu Topic theo course_name) ban đầu chỉ sửa
app/routers/documents.py::_save_outline và app/routers/quiz.py::generate —
kế hoạch gốc chỉ xét app/routers/flashcard.py:162 (save_from_answer, KHÔNG có
document/course để khoá theo, nên cố tình để nguyên). Review sau đó phát hiện
app/routers/flashcard.py:83 (bên trong generate(), khác dòng 162) mắc CHÍNH
XÁC lỗi tương tự — có sẵn `doc.course_name` ngay trong hàm nhưng tra cứu
Topic không lọc theo course_name — đây là lỗ hổng của kế hoạch, không phải
lỗi khi làm Task 3."""
import os
import sys
import unittest
import uuid
from datetime import datetime, timedelta
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models import Document, FlashcardItem, FlashcardReview, FlashcardSet, Topic, User
from pg_test_helpers import fresh_test_session_factory


def _fake_embed_query(text):
    return np.zeros(1024, dtype="float32")


class FlashcardTopicCourseScopingTest(unittest.TestCase):
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
            db.add(User(id=self.user_id, email=f"{self.user_id}@test.local", display_name="Heidi"))
            db.flush()
            self.doc_csdl = Document(user_id=self.user_id, file_name="a.pdf", course_name="CSDL", status="sẵn sàng")
            self.doc_mmt = Document(user_id=self.user_id, file_name="b.pdf", course_name="Mạng máy tính", status="sẵn sàng")
            db.add_all([self.doc_csdl, self.doc_mmt])
            db.flush()
            # Chụp id dạng chuỗi thuần TRƯỚC khi đóng session — sau
            # db.commit() (expire_on_commit=True mặc định), truy cập lại
            # self.doc_mmt.id trong test method (session đã đóng) sẽ ném
            # DetachedInstanceError vì SQLAlchemy cần refresh từ DB.
            self.doc_mmt_id = self.doc_mmt.id
            self.doc_csdl_id = self.doc_csdl.id
            # Topic CÙNG TÊN đã tồn tại sẵn cho môn CSDL, TRƯỚC khi flashcard
            # sinh cho môn Mạng máy tính chạy — mô phỏng đúng kịch bản bug:
            # nếu lookup không lọc theo course_name, flashcard Mạng máy tính
            # sẽ tái sử dụng nhầm Topic của CSDL.
            db.add(Topic(user_id=self.user_id, name="Bài tập", course_name="CSDL"))
            db.commit()
        finally:
            db.close()

    def test_same_topic_name_in_different_course_does_not_reuse_other_courses_topic(self):
        # generate() (app/routers/flashcard.py) gọi TRỰC TIẾP các tên đã
        # import vào namespace app.routers.flashcard (`from ... import
        # embed_query/generate_flashcards/PgVectorStore/get_llm_client`) —
        # patch phải nhắm vào namespace app.routers.flashcard, KHÔNG PHẢI
        # module gốc định nghĩa chúng (cùng lý do đã xác nhận với
        # app/routers/quiz.py ở Task 3: patch tại nguồn không chặn được lệnh
        # gọi thật vì tên đã được bind vào namespace module lúc import).
        fake_item = type(
            "FakeItem",
            (),
            {
                "front": "Q?", "back": "A.",
                "source_document": "b.pdf", "source_position": "Trang 1",
            },
        )()

        with patch("app.routers.flashcard.get_llm_client", return_value=object()), \
             patch("app.routers.flashcard.embed_query", side_effect=_fake_embed_query), \
             patch("app.routers.flashcard.generate_flashcards", return_value=[fake_item]), \
             patch("app.routers.flashcard.PgVectorStore") as store_cls:
            store_cls.return_value.search.return_value = [
                (
                    type("C", (), {
                        "text": "nội dung", "document_name": "b.pdf", "position_ref": "Trang 1",
                        "chunk_id": "c1", "document_id": self.doc_mmt_id,
                    })(),
                    0.9,
                )
            ]
            res = self.client.post(
                "/flashcard/generate",
                json={
                    "user_id": self.user_id,
                    "document_id": self.doc_mmt_id,
                    "topic_name": "Bài tập",
                    "num_cards": 1,
                },
            )

        self.assertEqual(res.status_code, 200)

        db = self.SessionLocal()
        try:
            topics = db.query(Topic).filter(Topic.user_id == self.user_id, Topic.name == "Bài tập").all()
        finally:
            db.close()

        self.assertEqual(len(topics), 2)
        self.assertEqual(sorted(t.course_name for t in topics), ["CSDL", "Mạng máy tính"])

    def test_response_reports_partial_when_fewer_cards_generated_than_requested(self):
        """Mirror BUG-003 bên quiz — POST /flashcard/generate giờ báo rõ khi
        tạo được ít thẻ hơn yêu cầu thay vì trả 200 im lặng với items ngắn hơn."""
        fake_item = type(
            "FakeItem",
            (),
            {"front": "Q?", "back": "A.", "source_document": "b.pdf", "source_position": "Trang 1"},
        )()

        with patch("app.routers.flashcard.get_llm_client", return_value=object()), \
             patch("app.routers.flashcard.embed_query", side_effect=_fake_embed_query), \
             patch("app.routers.flashcard.generate_flashcards", return_value=[fake_item]), \
             patch("app.routers.flashcard.PgVectorStore") as store_cls:
            store_cls.return_value.search.return_value = [
                (
                    type("C", (), {
                        "text": "nội dung", "document_name": "b.pdf", "position_ref": "Trang 1",
                        "chunk_id": "c1", "document_id": self.doc_mmt_id,
                    })(),
                    0.9,
                )
            ]
            res = self.client.post(
                "/flashcard/generate",
                json={"user_id": self.user_id, "document_id": self.doc_mmt_id, "num_cards": 3},
            )

        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["requested"], 3)
        self.assertEqual(body["generated"], 1)
        self.assertTrue(body["partial"])

    def test_generation_mode_is_persisted_on_the_flashcard_set(self):
        """Learning Loop Phase 3 — mirror test cùng tên ở test_quiz_route.py."""
        from app.models import FlashcardSet

        fake_item = type(
            "FakeItem",
            (),
            {"front": "Q?", "back": "A.", "source_document": "b.pdf", "source_position": "Trang 1"},
        )()

        with patch("app.routers.flashcard.get_llm_client", return_value=object()), \
             patch("app.routers.flashcard.embed_query", side_effect=_fake_embed_query), \
             patch("app.routers.flashcard.generate_flashcards", return_value=[fake_item]), \
             patch("app.routers.flashcard.PgVectorStore") as store_cls:
            store_cls.return_value.search.return_value = [
                (
                    type("C", (), {
                        "text": "nội dung", "document_name": "b.pdf", "position_ref": "Trang 1",
                        "chunk_id": "c1", "document_id": self.doc_mmt_id,
                    })(),
                    0.9,
                )
            ]
            res = self.client.post(
                "/flashcard/generate",
                json={
                    "user_id": self.user_id,
                    "document_id": self.doc_mmt_id,
                    "num_cards": 1,
                    "generation_mode": "exam",
                },
            )

        self.assertEqual(res.status_code, 200)
        fset_id = res.json()["flashcard_set_id"]

        db = self.SessionLocal()
        try:
            fset = db.query(FlashcardSet).filter(FlashcardSet.id == fset_id).first()
        finally:
            db.close()

        self.assertEqual(fset.generation_mode, "exam")

    def test_invalid_generation_mode_is_rejected(self):
        fake_item = type(
            "FakeItem",
            (),
            {"front": "Q?", "back": "A.", "source_document": "b.pdf", "source_position": "Trang 1"},
        )()

        with patch("app.routers.flashcard.get_llm_client", return_value=object()), \
             patch("app.routers.flashcard.embed_query", side_effect=_fake_embed_query), \
             patch("app.routers.flashcard.generate_flashcards", return_value=[fake_item]), \
             patch("app.routers.flashcard.PgVectorStore") as store_cls:
            store_cls.return_value.search.return_value = [
                (
                    type("C", (), {
                        "text": "nội dung", "document_name": "b.pdf", "position_ref": "Trang 1",
                        "chunk_id": "c1", "document_id": self.doc_mmt_id,
                    })(),
                    0.9,
                )
            ]
            res = self.client.post(
                "/flashcard/generate",
                json={
                    "user_id": self.user_id,
                    "document_id": self.doc_mmt_id,
                    "num_cards": 1,
                    "generation_mode": "not-a-real-mode",
                },
            )

        self.assertEqual(res.status_code, 400)


class SaveFromAnswerRouteTest(unittest.TestCase):
    """POST /flashcard/save (lưu thẻ từ câu trả lời hỏi đáp/quiz sai — không
    gắn với tài liệu nào cụ thể) — chưa từng có test nào chạy trên Postgres
    THẬT trước đây. FlashcardSet.document_id có FK NOT NULL tới documents.id
    (app/models.py); route lại dùng sentinel string "saved-from-answers" làm
    document_id, không phải id thật của bảng documents -> vi phạm FK ngay khi
    Postgres ép ràng buộc (SQLite mặc định không ép FK nên lỗi này không lộ ra
    nếu test bằng SQLite)."""

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
            db.add(User(id=self.user_id, email=f"{self.user_id}@test.local", display_name="Ivan"))
            db.commit()
        finally:
            db.close()

    def test_save_from_answer_does_not_violate_document_fk(self):
        res = self.client.post(
            "/flashcard/save",
            json={"user_id": self.user_id, "front": "Câu hỏi?", "back": "Câu trả lời."},
        )

        self.assertEqual(res.status_code, 200)

    def test_second_save_reuses_the_same_flashcard_set(self):
        """save_from_answer() tra cứu bộ "saved-from-answers" đã có trước khi
        tạo mới — 2 lượt lưu của CÙNG user phải rơi vào CÙNG một FlashcardSet,
        không tạo set mới mỗi lần."""
        from app.models import FlashcardSet

        self.client.post(
            "/flashcard/save",
            json={"user_id": self.user_id, "front": "Q1?", "back": "A1."},
        )
        self.client.post(
            "/flashcard/save",
            json={"user_id": self.user_id, "front": "Q2?", "back": "A2."},
        )

        db = self.SessionLocal()
        try:
            sets = db.query(FlashcardSet).filter(FlashcardSet.user_id == self.user_id).all()
        finally:
            db.close()

        self.assertEqual(len(sets), 1)


class FlashcardBoardMistakesHistoryTest(unittest.TestCase):
    """GET /flashcard/board, /flashcard/mistakes, /flashcard/{id}/history."""

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
        self.other_user_id = str(uuid.uuid4())
        self.now = datetime(2026, 9, 10, 12, 0, 0)

        db = self.SessionLocal()
        try:
            db.add(User(id=self.user_id, email=f"{self.user_id}@test.local", display_name="Judy"))
            db.add(User(id=self.other_user_id, email=f"{self.other_user_id}@test.local", display_name="Kevin"))
            db.flush()
            topic_id = str(uuid.uuid4())
            db.add(Topic(id=topic_id, user_id=self.user_id, name="Chủ đề A"))
            db.flush()

            fset_id = str(uuid.uuid4())
            fset = FlashcardSet(id=fset_id, user_id=self.user_id, document_id=None)
            db.add(fset)
            db.flush()

            self.new_item_id = str(uuid.uuid4())
            self.due_item_id = str(uuid.uuid4())
            self.learning_item_id = str(uuid.uuid4())
            self.mastered_item_id = str(uuid.uuid4())
            db.add_all([
                FlashcardItem(id=self.new_item_id, flashcard_set_id=fset_id, front="Mới", back="B"),
                FlashcardItem(id=self.due_item_id, flashcard_set_id=fset_id, topic_id=topic_id, front="Đến hạn", back="B"),
                FlashcardItem(id=self.learning_item_id, flashcard_set_id=fset_id, front="Đang học", back="B"),
                FlashcardItem(id=self.mastered_item_id, flashcard_set_id=fset_id, front="Đã thuộc", back="B"),
            ])
            db.flush()

            db.add(FlashcardReview(
                user_id=self.user_id, flashcard_item_id=self.due_item_id, rating="again",
                reviewed_at=self.now - timedelta(days=2), interval_days=0, ease=2.5,
                next_due_at=self.now - timedelta(days=1),
            ))
            db.add(FlashcardReview(
                user_id=self.user_id, flashcard_item_id=self.learning_item_id, rating="good",
                reviewed_at=self.now, interval_days=3, ease=2.5,
                next_due_at=self.now + timedelta(days=3),
            ))
            db.add(FlashcardReview(
                user_id=self.user_id, flashcard_item_id=self.mastered_item_id, rating="easy",
                reviewed_at=self.now, interval_days=25, ease=2.5,
                next_due_at=self.now + timedelta(days=25),
            ))
            db.commit()
        finally:
            db.close()

    def test_board_partitions_cards_into_three_buckets(self):
        res = self.client.get(f"/flashcard/board?user_id={self.user_id}")

        self.assertEqual(res.status_code, 200)
        body = res.json()
        due_ids = {i["id"] for i in body["due"]["items"]}
        self.assertEqual(due_ids, {self.new_item_id, self.due_item_id})
        self.assertEqual([i["id"] for i in body["learning"]["items"]], [self.learning_item_id])
        self.assertEqual([i["id"] for i in body["mastered"]["items"]], [self.mastered_item_id])
        self.assertEqual(body["due"]["count"], 2)

    def test_mistakes_returns_only_cards_last_rated_again(self):
        res = self.client.get(f"/flashcard/mistakes?user_id={self.user_id}")

        self.assertEqual(res.status_code, 200)
        mistakes = res.json()["mistakes"]
        self.assertEqual([m["id"] for m in mistakes], [self.due_item_id])
        self.assertEqual(mistakes[0]["topic_name"], "Chủ đề A")

    def test_history_returns_reviews_newest_first(self):
        db = self.SessionLocal()
        try:
            db.add(FlashcardReview(
                user_id=self.user_id, flashcard_item_id=self.due_item_id, rating="hard",
                reviewed_at=self.now, interval_days=1, ease=2.3,
                next_due_at=self.now + timedelta(days=1),
            ))
            db.commit()
        finally:
            db.close()

        res = self.client.get(f"/flashcard/{self.due_item_id}/history?user_id={self.user_id}")

        self.assertEqual(res.status_code, 200)
        ratings = [h["rating"] for h in res.json()["history"]]
        self.assertEqual(ratings, ["hard", "again"])

    def test_history_of_someone_elses_card_is_rejected(self):
        res = self.client.get(f"/flashcard/{self.due_item_id}/history?user_id={self.other_user_id}")

        self.assertEqual(res.status_code, 404)


if __name__ == "__main__":
    unittest.main()
