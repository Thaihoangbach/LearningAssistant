import os
import sys
import unittest
from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.models import Base, FlashcardItem, FlashcardReview, FlashcardSet, MasteryScore, Topic

NOW = datetime(2026, 9, 10, 12, 0, 0)


class LearningStateTestCase(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        self.db = sessionmaker(bind=self.engine)()

        self.topic = Topic(user_id="u1", name="Chuẩn hoá CSDL", course_name="CSDL")
        self.other_topic = Topic(user_id="u1", name="Chỉ mục", course_name="CSDL")
        self.db.add_all([self.topic, self.other_topic])
        self.db.commit()

        self.fset = FlashcardSet(user_id="u1", document_id="d1")
        self.db.add(self.fset)
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def _flashcard_item(self, topic_id):
        item = FlashcardItem(flashcard_set_id=self.fset.id, topic_id=topic_id, front="f", back="b")
        self.db.add(item)
        self.db.commit()
        return item

    def _review(self, item, rating, reviewed_at, user_id="u1"):
        self.db.add(
            FlashcardReview(
                user_id=user_id,
                flashcard_item_id=item.id,
                rating=rating,
                reviewed_at=reviewed_at,
                interval_days=1,
                ease=2.5,
                next_due_at=reviewed_at + timedelta(days=1),
            )
        )
        self.db.commit()


class TestGetLearningState(LearningStateTestCase):
    def test_no_data_returns_none_for_both_signals(self):
        from app.services.learning_state import get_learning_state

        state = get_learning_state(self.db, "u1", self.topic.id)
        self.assertIsNone(state.comprehension)
        self.assertIsNone(state.retention)
        self.assertEqual(state.topic_id, self.topic.id)

    def test_comprehension_only(self):
        from app.services.learning_state import get_learning_state

        self.db.add(MasteryScore(user_id="u1", topic_id=self.topic.id, score=0.8, updated_at=NOW))
        self.db.commit()

        state = get_learning_state(self.db, "u1", self.topic.id, now=NOW)
        self.assertAlmostEqual(state.comprehension, 0.8, places=4)
        self.assertIsNone(state.retention)

    def test_retention_only(self):
        from app.services.learning_state import get_learning_state

        item = self._flashcard_item(self.topic.id)
        self._review(item, "easy", NOW)

        state = get_learning_state(self.db, "u1", self.topic.id, now=NOW)
        self.assertIsNone(state.comprehension)
        self.assertGreaterEqual(state.retention, 0.9)

    def test_both_signals_present(self):
        from app.services.learning_state import get_learning_state

        self.db.add(MasteryScore(user_id="u1", topic_id=self.topic.id, score=0.5, updated_at=NOW))
        self.db.commit()
        item = self._flashcard_item(self.topic.id)
        self._review(item, "again", NOW)

        state = get_learning_state(self.db, "u1", self.topic.id, now=NOW)
        self.assertAlmostEqual(state.comprehension, 0.5, places=4)
        self.assertEqual(state.retention, 0.0)

    def test_does_not_leak_across_topics(self):
        from app.services.learning_state import get_learning_state

        item = self._flashcard_item(self.other_topic.id)
        self._review(item, "easy", NOW)

        state = get_learning_state(self.db, "u1", self.topic.id, now=NOW)
        self.assertIsNone(state.retention)

    def test_does_not_leak_across_users(self):
        from app.services.learning_state import get_learning_state

        item = self._flashcard_item(self.topic.id)
        self._review(item, "easy", NOW, user_id="nguoi-khac")

        state = get_learning_state(self.db, "u1", self.topic.id, now=NOW)
        self.assertIsNone(state.retention)


if __name__ == "__main__":
    unittest.main()
