import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.mastery import Attempt, compute_mastery


class TestComputeMastery(unittest.TestCase):
    def test_no_attempts_returns_none(self):
        self.assertIsNone(compute_mastery([]))

    def test_all_correct_gives_high_score(self):
        now = datetime.now(timezone.utc)
        attempts = [Attempt(is_correct=True, attempted_at=now) for _ in range(5)]
        score = compute_mastery(attempts)
        self.assertGreaterEqual(score, 0.9)

    def test_all_incorrect_gives_low_score(self):
        now = datetime.now(timezone.utc)
        attempts = [Attempt(is_correct=False, attempted_at=now) for _ in range(5)]
        score = compute_mastery(attempts)
        self.assertLessEqual(score, 0.1)

    def test_score_always_between_0_and_1(self):
        now = datetime.now(timezone.utc)
        attempts = [
            Attempt(is_correct=True, attempted_at=now),
            Attempt(is_correct=False, attempted_at=now - timedelta(days=1)),
            Attempt(is_correct=True, attempted_at=now - timedelta(days=10)),
        ]
        score = compute_mastery(attempts)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_recent_attempts_weigh_more_than_old_ones(self):
        now = datetime.now(timezone.utc)
        # kịch bản A: đúng gần đây, sai lâu rồi -> mastery phải cao hơn kịch bản B
        attempts_recent_correct = [
            Attempt(is_correct=False, attempted_at=now - timedelta(days=30)),
            Attempt(is_correct=True, attempted_at=now),
        ]
        # kịch bản B: sai gần đây, đúng lâu rồi
        attempts_recent_wrong = [
            Attempt(is_correct=True, attempted_at=now - timedelta(days=30)),
            Attempt(is_correct=False, attempted_at=now),
        ]
        score_a = compute_mastery(attempts_recent_correct)
        score_b = compute_mastery(attempts_recent_wrong)
        self.assertGreater(score_a, score_b)

    def test_topics_below_threshold_are_flagged_weak(self):
        from app.mastery import classify_mastery

        self.assertEqual(classify_mastery(0.9), "tốt")
        self.assertEqual(classify_mastery(0.5), "trung bình")
        self.assertEqual(classify_mastery(0.2), "yếu")


if __name__ == "__main__":
    unittest.main()
