import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.services.retention import ReviewEvent, compute_retention


class TestComputeRetention(unittest.TestCase):
    def test_no_reviews_returns_none(self):
        self.assertIsNone(compute_retention([]))

    def test_all_easy_gives_high_score(self):
        now = datetime.now(timezone.utc)
        reviews = [ReviewEvent(rating="easy", reviewed_at=now) for _ in range(5)]
        score = compute_retention(reviews)
        self.assertGreaterEqual(score, 0.9)

    def test_all_again_gives_zero_score(self):
        now = datetime.now(timezone.utc)
        reviews = [ReviewEvent(rating="again", reviewed_at=now) for _ in range(5)]
        self.assertEqual(compute_retention(reviews), 0.0)

    def test_score_always_between_0_and_1(self):
        now = datetime.now(timezone.utc)
        reviews = [
            ReviewEvent(rating="easy", reviewed_at=now),
            ReviewEvent(rating="again", reviewed_at=now - timedelta(days=1)),
            ReviewEvent(rating="hard", reviewed_at=now - timedelta(days=10)),
        ]
        score = compute_retention(reviews)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_recent_reviews_weigh_more_than_old_ones(self):
        now = datetime.now(timezone.utc)
        recent_easy = [
            ReviewEvent(rating="again", reviewed_at=now - timedelta(days=30)),
            ReviewEvent(rating="easy", reviewed_at=now),
        ]
        recent_again = [
            ReviewEvent(rating="easy", reviewed_at=now - timedelta(days=30)),
            ReviewEvent(rating="again", reviewed_at=now),
        ]
        self.assertGreater(compute_retention(recent_easy), compute_retention(recent_again))

    def test_good_rating_aligns_with_tot_threshold(self):
        from app.services.mastery import classify_mastery

        now = datetime.now(timezone.utc)
        score = compute_retention([ReviewEvent(rating="good", reviewed_at=now)])
        self.assertEqual(classify_mastery(score), "tốt")

    def test_hard_rating_aligns_with_trung_binh_threshold(self):
        from app.services.mastery import classify_mastery

        now = datetime.now(timezone.utc)
        score = compute_retention([ReviewEvent(rating="hard", reviewed_at=now)])
        self.assertEqual(classify_mastery(score), "trung bình")

    def test_naive_reviewed_at_does_not_crash_against_aware_default_now(self):
        naive_now = datetime.utcnow()
        reviews = [ReviewEvent(rating="good", reviewed_at=naive_now - timedelta(days=1))]
        self.assertIsNotNone(compute_retention(reviews))


if __name__ == "__main__":
    unittest.main()
