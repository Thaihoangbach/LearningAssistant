import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, FlashcardItem, FlashcardSet, Quiz, QuizItem


class TestContentTypeColumn(unittest.TestCase):
    """Learning Loop Phase 5 — mirror tests/test_generation_mode_column.py.
    content_type là kết quả phân loại của LLM-judge (khái niệm/định nghĩa/
    công thức/sự kiện/quy trình), xem app/llm/quiz_generator.py::
    _build_item_judge_prompt và bản mirror ở app/llm/flashcard_generator.py."""

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        self.db = sessionmaker(bind=self.engine)()

    def tearDown(self):
        self.db.close()

    def test_quiz_item_content_type_defaults_to_none(self):
        quiz = Quiz(user_id="u1", document_id="d1")
        self.db.add(quiz)
        self.db.commit()
        item = QuizItem(quiz_id=quiz.id, question="Q?", options="[]", correct_answer="A")
        self.db.add(item)
        self.db.commit()
        self.assertIsNone(item.content_type)

    def test_quiz_item_content_type_can_be_set(self):
        quiz = Quiz(user_id="u1", document_id="d1")
        self.db.add(quiz)
        self.db.commit()
        item = QuizItem(quiz_id=quiz.id, question="Q?", options="[]", correct_answer="A", content_type="formula")
        self.db.add(item)
        self.db.commit()
        self.assertEqual(item.content_type, "formula")

    def test_flashcard_item_content_type_can_be_set(self):
        fset = FlashcardSet(user_id="u1", document_id="d1")
        self.db.add(fset)
        self.db.commit()
        item = FlashcardItem(flashcard_set_id=fset.id, front="F", back="B", content_type="definition")
        self.db.add(item)
        self.db.commit()
        self.assertEqual(item.content_type, "definition")


if __name__ == "__main__":
    unittest.main()
