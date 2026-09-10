import os
import sys
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.services.document_cleanup import cleanup_document_topics
from app.models import (
    Attempt,
    Base,
    Document,
    DocumentTopic,
    FlashcardItem,
    FlashcardSet,
    MasteryScore,
    Quiz,
    QuizItem,
    Topic,
)

USER = "u1"


class CleanupTestCase(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        self.db = sessionmaker(bind=self.engine)()

    def tearDown(self):
        self.db.close()

    def _outline(self, document_id, titles, course_name=None):
        if not self.db.query(Document).filter(Document.id == document_id).first():
            self.db.add(
                Document(
                    id=document_id,
                    user_id=USER,
                    file_name=f"{document_id}.pdf",
                    course_name=course_name,
                )
            )
        for i, title in enumerate(titles):
            self.db.add(
                DocumentTopic(
                    document_id=document_id, user_id=USER, title=title, order_index=i
                )
            )
            if not (
                self.db.query(Topic)
                .filter(Topic.user_id == USER, Topic.course_name == course_name, Topic.name == title)
                .first()
            ):
                self.db.add(Topic(user_id=USER, name=title, course_name=course_name))
        self.db.commit()

    def _topic(self, name, course_name=None):
        return (
            self.db.query(Topic)
            .filter(Topic.user_id == USER, Topic.course_name == course_name, Topic.name == name)
            .first()
        )


class TestCleanupDocumentTopics(CleanupTestCase):
    def test_removes_outline_rows_of_that_document(self):
        self._outline("doc-1", ["Chương 1", "Chương 2"])
        cleanup_document_topics(self.db, document_id="doc-1", user_id=USER)
        self.assertEqual(
            self.db.query(DocumentTopic).filter(DocumentTopic.document_id == "doc-1").count(), 0
        )

    def test_keeps_outline_rows_of_other_documents(self):
        self._outline("doc-1", ["Chương 1"])
        self._outline("doc-2", ["Chương khác"])
        cleanup_document_topics(self.db, document_id="doc-1", user_id=USER)
        self.assertEqual(
            self.db.query(DocumentTopic).filter(DocumentTopic.document_id == "doc-2").count(), 1
        )

    def test_removes_topic_never_used_by_learner(self):
        self._outline("doc-1", ["Chưa học bao giờ"])
        cleanup_document_topics(self.db, document_id="doc-1", user_id=USER)
        self.assertIsNone(self._topic("Chưa học bao giờ"))

    def test_keeps_topic_that_has_mastery_history(self):
        """Xoá tài liệu nguồn KHÔNG được xoá lịch sử học tập — người dùng đã bỏ
        công làm bài về chủ đề đó."""
        self._outline("doc-1", ["Đã học rồi"])
        topic = self._topic("Đã học rồi")
        self.db.add(MasteryScore(user_id=USER, topic_id=topic.id, score=0.7))
        self.db.commit()

        cleanup_document_topics(self.db, document_id="doc-1", user_id=USER)
        self.assertIsNotNone(self._topic("Đã học rồi"))

    def test_keeps_topic_that_has_attempts(self):
        self._outline("doc-1", ["Có lượt làm bài"])
        topic = self._topic("Có lượt làm bài")
        self.db.add(
            Attempt(user_id=USER, quiz_item_id="qi-1", topic_id=topic.id, is_correct=True)
        )
        self.db.commit()

        cleanup_document_topics(self.db, document_id="doc-1", user_id=USER)
        self.assertIsNotNone(self._topic("Có lượt làm bài"))

    def test_keeps_topic_that_has_quiz_items(self):
        self._outline("doc-1", ["Có quiz"])
        topic = self._topic("Có quiz")
        quiz = Quiz(user_id=USER, document_id="doc-1")
        self.db.add(quiz)
        self.db.commit()
        self.db.add(
            QuizItem(
                quiz_id=quiz.id, topic_id=topic.id, question="q", options="[]", correct_answer="a"
            )
        )
        self.db.commit()

        cleanup_document_topics(self.db, document_id="doc-1", user_id=USER)
        self.assertIsNotNone(self._topic("Có quiz"))

    def test_keeps_topic_that_has_flashcards(self):
        self._outline("doc-1", ["Có thẻ"])
        topic = self._topic("Có thẻ")
        fset = FlashcardSet(user_id=USER, document_id="doc-1")
        self.db.add(fset)
        self.db.commit()
        self.db.add(
            FlashcardItem(flashcard_set_id=fset.id, topic_id=topic.id, front="f", back="b")
        )
        self.db.commit()

        cleanup_document_topics(self.db, document_id="doc-1", user_id=USER)
        self.assertIsNotNone(self._topic("Có thẻ"))

    def test_keeps_topic_still_referenced_by_another_document(self):
        self._outline("doc-1", ["Chủ đề chung"])
        self._outline("doc-2", ["Chủ đề chung"])
        cleanup_document_topics(self.db, document_id="doc-1", user_id=USER)
        self.assertIsNotNone(self._topic("Chủ đề chung"))

    def test_does_not_touch_other_users(self):
        self._outline("doc-1", ["Của tôi"])
        self.db.add(DocumentTopic(document_id="doc-1", user_id="nguoi-khac", title="Của họ"))
        self.db.add(Topic(user_id="nguoi-khac", name="Của họ"))
        self.db.commit()

        cleanup_document_topics(self.db, document_id="doc-1", user_id=USER)
        remaining = self.db.query(Topic).filter(Topic.user_id == "nguoi-khac").count()
        self.assertEqual(remaining, 1)

    def test_is_idempotent(self):
        self._outline("doc-1", ["Chương 1"])
        cleanup_document_topics(self.db, document_id="doc-1", user_id=USER)
        cleanup_document_topics(self.db, document_id="doc-1", user_id=USER)
        self.assertEqual(self.db.query(DocumentTopic).count(), 0)

    def test_unknown_document_is_safe(self):
        cleanup_document_topics(self.db, document_id="khong-ton-tai", user_id=USER)
        self.assertEqual(self.db.query(DocumentTopic).count(), 0)


class TestCleanupDocumentTopicsCourseScoping(CleanupTestCase):
    """Topic được định danh theo (user_id, course_name, name) — cùng tên chủ đề
    có thể tồn tại hợp lệ ở hai môn khác nhau. cleanup_document_topics phải
    khoá CẢ việc tra Topic lẫn kiểm tra still_referenced theo course_name của
    tài liệu đang dọn, không chỉ theo tên."""

    def test_orphan_not_blocked_by_same_named_topic_in_other_course(self):
        """Doc B (môn khác) vẫn còn nhắc "Bài tập" — trước đây khiến
        still_referenced (không lọc theo môn) trả về sai, bỏ sót không xoá
        Topic mồ côi thật sự của môn CSDL."""
        self._outline("doc-a", ["Bài tập"], course_name="CSDL")
        self._outline("doc-b", ["Bài tập"], course_name="Mạng máy tính")

        cleanup_document_topics(self.db, document_id="doc-a", user_id=USER)

        self.assertIsNone(self._topic("Bài tập", course_name="CSDL"))
        self.assertIsNotNone(self._topic("Bài tập", course_name="Mạng máy tính"))
        self.assertEqual(
            self.db.query(DocumentTopic).filter(DocumentTopic.document_id == "doc-b").count(), 1
        )

    def test_same_named_orphan_topic_in_other_course_is_never_touched(self):
        """Một Topic "Bài tập" mồ côi sẵn ở môn Mạng máy tính (không tài liệu
        nào của môn đó nhắc tới) không được đụng tới khi dọn tài liệu của môn
        CSDL — trước đây tra Topic không lọc theo môn có thể xoá NHẦM Topic
        của môn khác."""
        self.db.add(Topic(user_id=USER, name="Bài tập", course_name="Mạng máy tính"))
        self.db.commit()
        self._outline("doc-a", ["Bài tập"], course_name="CSDL")

        cleanup_document_topics(self.db, document_id="doc-a", user_id=USER)

        self.assertIsNone(self._topic("Bài tập", course_name="CSDL"))
        self.assertIsNotNone(self._topic("Bài tập", course_name="Mạng máy tính"))

    def test_keeps_topic_referenced_by_another_document_in_same_course(self):
        self._outline("doc-a", ["Chủ đề chung"], course_name="CSDL")
        self._outline("doc-c", ["Chủ đề chung"], course_name="CSDL")

        cleanup_document_topics(self.db, document_id="doc-a", user_id=USER)

        self.assertIsNotNone(self._topic("Chủ đề chung", course_name="CSDL"))


if __name__ == "__main__":
    unittest.main()
