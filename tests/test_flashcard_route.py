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
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models import Document, Topic, User
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


if __name__ == "__main__":
    unittest.main()
