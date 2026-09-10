import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.services.learning_policy import recommend_action
from app.services.learning_state import LearningState


class TestRecommendAction(unittest.TestCase):
    def test_no_data_recommends_learn(self):
        state = LearningState(topic_id="t1", comprehension=None, retention=None)
        rec = recommend_action(state)
        self.assertEqual(rec.action, "learn")

    def test_weak_comprehension_ok_retention_recommends_quiz(self):
        state = LearningState(topic_id="t1", comprehension=0.2, retention=0.8)
        rec = recommend_action(state)
        self.assertEqual(rec.action, "quiz")
        self.assertIn("hiểu", rec.reason)

    def test_weak_retention_ok_comprehension_recommends_flashcard(self):
        state = LearningState(topic_id="t1", comprehension=0.8, retention=0.2)
        rec = recommend_action(state)
        self.assertEqual(rec.action, "flashcard")
        self.assertIn("nhớ", rec.reason)

    def test_both_weak_recommends_learn(self):
        state = LearningState(topic_id="t1", comprehension=0.1, retention=0.1)
        rec = recommend_action(state)
        self.assertEqual(rec.action, "learn")

    def test_both_ok_recommends_no_priority_action(self):
        state = LearningState(topic_id="t1", comprehension=0.9, retention=0.9)
        rec = recommend_action(state)
        self.assertIsNone(rec.action)

    def test_weak_comprehension_missing_retention_still_recommends_quiz(self):
        # Chưa có flashcard nào cho topic này (retention=None) không được
        # coi là "yếu" — tránh gợi ý "learn" oan cho người chỉ mới làm quiz.
        state = LearningState(topic_id="t1", comprehension=0.1, retention=None)
        rec = recommend_action(state)
        self.assertEqual(rec.action, "quiz")

    def test_reason_is_always_non_empty_string(self):
        for state in (
            LearningState(topic_id="t1", comprehension=None, retention=None),
            LearningState(topic_id="t1", comprehension=0.9, retention=0.9),
        ):
            rec = recommend_action(state)
            self.assertIsInstance(rec.reason, str)
            self.assertTrue(rec.reason)


if __name__ == "__main__":
    unittest.main()
