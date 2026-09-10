import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, FlashcardSet, Quiz


class TestGenerationModeColumn(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        self.db = sessionmaker(bind=self.engine)()

    def tearDown(self):
        self.db.close()

    def test_quiz_generation_mode_defaults_to_none(self):
        quiz = Quiz(user_id="u1", document_id="d1")
        self.db.add(quiz)
        self.db.commit()
        self.assertIsNone(quiz.generation_mode)

    def test_quiz_generation_mode_can_be_set(self):
        quiz = Quiz(user_id="u1", document_id="d1", generation_mode="weak_topics")
        self.db.add(quiz)
        self.db.commit()
        self.assertEqual(quiz.generation_mode, "weak_topics")

    def test_flashcard_set_generation_mode_can_be_set(self):
        fset = FlashcardSet(user_id="u1", document_id="d1", generation_mode="review")
        self.db.add(fset)
        self.db.commit()
        self.assertEqual(fset.generation_mode, "review")


if __name__ == "__main__":
    unittest.main()
