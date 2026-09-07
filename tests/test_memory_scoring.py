import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.memory.scoring import (
    ScoredEvent,
    combine_score,
    importance_for,
    recency_weight,
    select_top_events,
)


def _event(event_id, relevance, created_at, event_type="question_asked", content="nội dung"):
    return ScoredEvent(
        event_id=event_id,
        event_type=event_type,
        content=content,
        importance=importance_for(event_type),
        created_at=created_at,
        relevance=relevance,
    )


class TestRecencyWeight(unittest.TestCase):
    def test_brand_new_event_has_weight_one(self):
        now = datetime.now(timezone.utc)
        self.assertAlmostEqual(recency_weight(now, now), 1.0, places=6)

    def test_weight_halves_after_one_half_life(self):
        now = datetime.now(timezone.utc)
        created = now - timedelta(hours=168)
        self.assertAlmostEqual(recency_weight(created, now), 0.5, places=6)

    def test_future_timestamp_is_clamped_to_weight_one(self):
        now = datetime.now(timezone.utc)
        created = now + timedelta(hours=5)
        self.assertAlmostEqual(recency_weight(created, now), 1.0, places=6)

    def test_naive_created_at_does_not_crash_against_aware_now(self):
        # created_at đọc từ SQLite luôn naive, now mặc định aware — trộn hai
        # kiểu này từng làm crash /quiz/submit (xem tests/test_mastery.py).
        aware_now = datetime.now(timezone.utc)
        naive_created = datetime.utcnow() - timedelta(hours=24)
        self.assertGreater(recency_weight(naive_created, aware_now), 0.0)


class TestImportanceFor(unittest.TestCase):
    def test_quiz_wrong_is_more_important_than_question_asked(self):
        self.assertGreater(importance_for("quiz_wrong"), importance_for("question_asked"))

    def test_unknown_event_type_falls_back_to_default(self):
        self.assertEqual(importance_for("khong_ton_tai"), 0.3)


class TestCombineScore(unittest.TestCase):
    def test_all_maximal_gives_one(self):
        self.assertAlmostEqual(combine_score(1.0, 1.0, 1.0), 1.0, places=6)

    def test_all_zero_gives_zero(self):
        self.assertAlmostEqual(combine_score(0.0, 0.0, 0.0), 0.0, places=6)

    def test_relevance_outweighs_recency(self):
        # relevance có trọng số 0.45 > recency 0.35
        only_relevance = combine_score(0.0, 1.0, 0.0)
        only_recency = combine_score(1.0, 0.0, 0.0)
        self.assertGreater(only_relevance, only_recency)


class TestSelectTopEvents(unittest.TestCase):
    def test_empty_input_returns_empty(self):
        self.assertEqual(select_top_events([]), [])

    def test_drops_events_below_min_score(self):
        now = datetime.now(timezone.utc)
        # relevance 0 + rất cũ + importance thấp -> dưới ngưỡng 0.25
        weak = _event("e1", relevance=0.0, created_at=now - timedelta(days=365))
        self.assertEqual(select_top_events([weak], now=now), [])

    def test_caps_at_max_events(self):
        now = datetime.now(timezone.utc)
        events = [_event(f"e{i}", relevance=1.0, created_at=now) for i in range(10)]
        self.assertEqual(len(select_top_events(events, now=now)), 5)

    def test_sorts_by_score_descending(self):
        now = datetime.now(timezone.utc)
        low = _event("low", relevance=0.3, created_at=now)
        high = _event("high", relevance=1.0, created_at=now)
        result = select_top_events([low, high], now=now)
        self.assertEqual([e.event_id for e in result], ["high", "low"])

    def test_populates_score_field(self):
        now = datetime.now(timezone.utc)
        result = select_top_events([_event("e1", relevance=1.0, created_at=now)], now=now)
        self.assertGreater(result[0].score, 0.0)


if __name__ == "__main__":
    unittest.main()
