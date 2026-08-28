import os
import sys
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.spaced_repetition import (
    DEFAULT_EASE,
    MAX_EASE,
    MIN_EASE,
    schedule_next_review,
)

NOW = datetime(2026, 8, 28, 12, 0, 0, tzinfo=timezone.utc)


class TestScheduleNextReview(unittest.TestCase):
    def test_new_card_rated_good_is_due_in_one_day(self):
        s = schedule_next_review("good", now=NOW)
        self.assertEqual(s.interval_days, 1)
        self.assertEqual((s.next_due_at - NOW.replace(tzinfo=None)).days, 1)

    def test_new_card_rated_easy_waits_longer_than_good(self):
        good = schedule_next_review("good", now=NOW)
        easy = schedule_next_review("easy", now=NOW)
        self.assertGreater(easy.interval_days, good.interval_days)

    def test_again_makes_card_due_immediately(self):
        s = schedule_next_review("again", interval_days=10, ease=2.5, now=NOW)
        self.assertEqual(s.interval_days, 0)
        self.assertEqual(s.next_due_at, NOW.replace(tzinfo=None))

    def test_again_lowers_ease(self):
        s = schedule_next_review("again", interval_days=10, ease=2.5, now=NOW)
        self.assertLess(s.ease, 2.5)

    def test_good_keeps_ease_unchanged(self):
        s = schedule_next_review("good", interval_days=4, ease=2.1, now=NOW)
        self.assertAlmostEqual(s.ease, 2.1)

    def test_interval_grows_by_ease_on_good(self):
        s = schedule_next_review("good", interval_days=4, ease=2.0, now=NOW)
        self.assertEqual(s.interval_days, 8)

    def test_ease_never_drops_below_floor(self):
        ease = DEFAULT_EASE
        for _ in range(20):
            ease = schedule_next_review("again", interval_days=1, ease=ease, now=NOW).ease
        self.assertGreaterEqual(ease, MIN_EASE)

    def test_ease_never_exceeds_ceiling(self):
        ease = DEFAULT_EASE
        for _ in range(20):
            ease = schedule_next_review("easy", interval_days=1, ease=ease, now=NOW).ease
        self.assertLessEqual(ease, MAX_EASE)

    def test_unknown_rating_is_rejected(self):
        with self.assertRaises(ValueError):
            schedule_next_review("khong_hop_le", now=NOW)

    def test_hard_grows_slower_than_good(self):
        hard = schedule_next_review("hard", interval_days=10, ease=2.5, now=NOW)
        good = schedule_next_review("good", interval_days=10, ease=2.5, now=NOW)
        self.assertLess(hard.interval_days, good.interval_days)


if __name__ == "__main__":
    unittest.main()
