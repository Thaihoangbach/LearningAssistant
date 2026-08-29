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

    def test_naive_attempted_at_does_not_crash_against_aware_default_now(self):
        # attempted_at NAIVE mô phỏng đúng dữ liệu đọc từ DB thật (SQLAlchemy
        # DateTime + SQLite mất tzinfo khi round-trip), trong khi compute_mastery()
        # không truyền now= sẽ dùng default AWARE bên trong — trộn hai kiểu này
        # từng làm crash /quiz/submit thật (TypeError: naive vs aware).
        naive_now = datetime.utcnow()
        attempts = [Attempt(is_correct=True, attempted_at=naive_now - timedelta(days=1))]
        score = compute_mastery(attempts)
        self.assertIsNotNone(score)


class TestDecayWhenUnpractised(unittest.TestCase):
    """MasteryScore chỉ được tính lại khi có Attempt MỚI, nên một chủ đề đạt
    90% ba tháng trước mà không đụng tới vẫn hiện 90% mãi mãi — hệ thống không
    bao giờ nhắc ôn lại đúng lúc quên rơi vào."""

    def test_fresh_score_is_unchanged(self):
        from app.mastery import decay_unpractised

        now = datetime.now(timezone.utc)
        self.assertAlmostEqual(decay_unpractised(0.9, now, now=now), 0.9, places=4)

    def test_score_halves_after_one_half_life(self):
        from app.mastery import MASTERY_HALF_LIFE_DAYS, decay_unpractised

        now = datetime.now(timezone.utc)
        updated = now - timedelta(days=MASTERY_HALF_LIFE_DAYS)
        self.assertAlmostEqual(decay_unpractised(0.8, updated, now=now), 0.4, places=4)

    def test_long_unpractised_strong_topic_becomes_weak(self):
        from app.mastery import classify_mastery, decay_unpractised

        now = datetime.now(timezone.utc)
        updated = now - timedelta(days=90)
        decayed = decay_unpractised(0.9, updated, now=now)
        self.assertEqual(classify_mastery(decayed), "yếu")

    def test_decay_never_goes_below_zero(self):
        from app.mastery import decay_unpractised

        now = datetime.now(timezone.utc)
        updated = now - timedelta(days=3650)
        self.assertGreaterEqual(decay_unpractised(0.9, updated, now=now), 0.0)

    def test_naive_updated_at_does_not_crash(self):
        from app.mastery import decay_unpractised

        naive = datetime.utcnow() - timedelta(days=10)
        self.assertIsNotNone(decay_unpractised(0.7, naive))

    def test_future_timestamp_is_clamped(self):
        from app.mastery import decay_unpractised

        now = datetime.now(timezone.utc)
        self.assertAlmostEqual(
            decay_unpractised(0.6, now + timedelta(days=5), now=now), 0.6, places=4
        )

    def test_none_updated_at_returns_score_unchanged(self):
        from app.mastery import decay_unpractised

        self.assertAlmostEqual(decay_unpractised(0.5, None), 0.5, places=4)


class TestDifficultyWeighting(unittest.TestCase):
    def test_correct_on_hard_beats_correct_on_easy(self):
        from app.mastery import Attempt as A, compute_mastery

        now = datetime.now(timezone.utc)
        hard = compute_mastery(
            [A(is_correct=True, attempted_at=now, difficulty="advanced"),
             A(is_correct=False, attempted_at=now, difficulty="intermediate")]
        )
        easy = compute_mastery(
            [A(is_correct=True, attempted_at=now, difficulty="beginner"),
             A(is_correct=False, attempted_at=now, difficulty="intermediate")]
        )
        self.assertGreater(hard, easy)

    def test_wrong_on_easy_hurts_more_than_wrong_on_hard(self):
        from app.mastery import Attempt as A, compute_mastery

        now = datetime.now(timezone.utc)
        wrong_easy = compute_mastery(
            [A(is_correct=False, attempted_at=now, difficulty="beginner"),
             A(is_correct=True, attempted_at=now, difficulty="intermediate")]
        )
        wrong_hard = compute_mastery(
            [A(is_correct=False, attempted_at=now, difficulty="advanced"),
             A(is_correct=True, attempted_at=now, difficulty="intermediate")]
        )
        self.assertLess(wrong_easy, wrong_hard)

    def test_missing_difficulty_behaves_like_intermediate(self):
        from app.mastery import Attempt as A, compute_mastery

        now = datetime.now(timezone.utc)
        without = compute_mastery([A(is_correct=True, attempted_at=now)])
        with_mid = compute_mastery(
            [A(is_correct=True, attempted_at=now, difficulty="intermediate")]
        )
        self.assertAlmostEqual(without, with_mid, places=6)

    def test_unknown_difficulty_label_is_safe(self):
        from app.mastery import Attempt as A, compute_mastery

        now = datetime.now(timezone.utc)
        score = compute_mastery([A(is_correct=True, attempted_at=now, difficulty="siêu khó")])
        self.assertIsNotNone(score)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)


if __name__ == "__main__":
    unittest.main()
