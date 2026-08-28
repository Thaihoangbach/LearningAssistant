"""Xếp lịch ôn lại flashcard theo lặp lại ngắt quãng — bản rút gọn của SM-2.

Module THUẦN: không chạm DB, không chạm mạng, nhận trạng thái hiện tại và trả
về trạng thái tiếp theo. Cùng khuôn với app/mastery.py để test được độc lập.

Vì sao rút gọn thay vì SM-2 đầy đủ: SM-2 gốc dùng thang chất lượng 0-5 và một
công thức ease phức tạp hơn, nhưng người học phải tự chấm mình theo 6 mức —
quá tinh vi cho một giao diện chỉ có bốn nút. Bốn mức "again/hard/good/easy"
là cách Anki đã đơn giản hoá và đủ để phân biệt trạng thái nhớ.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

VALID_RATINGS = ("again", "hard", "good", "easy")

DEFAULT_EASE = 2.5
MIN_EASE = 1.3
MAX_EASE = 2.5

_EASE_DELTA = {"again": -0.20, "hard": -0.15, "good": 0.0, "easy": 0.15}


@dataclass
class ReviewSchedule:
    interval_days: float
    ease: float
    next_due_at: datetime


def _to_naive_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=None) if value.tzinfo is not None else value


def _next_interval(rating: str, interval_days: float, ease: float) -> float:
    if rating == "again":
        # Quên hẳn thì phải gặp lại NGAY trong cùng phiên, không đẩy sang ngày
        # khác — đó là điểm mấu chốt của lặp lại ngắt quãng.
        return 0
    if rating == "hard":
        return max(1, interval_days * 1.2)
    if rating == "good":
        return max(1, interval_days * ease)
    return max(2, interval_days * ease * 1.3)


def schedule_next_review(
    rating: str,
    interval_days: float = 0.0,
    ease: float = DEFAULT_EASE,
    now: Optional[datetime] = None,
) -> ReviewSchedule:
    if rating not in VALID_RATINGS:
        raise ValueError(f"Mức đánh giá không hợp lệ: {rating!r}. Chỉ nhận {VALID_RATINGS}.")

    now = _to_naive_utc(now or datetime.now(timezone.utc))
    new_interval = _next_interval(rating, interval_days, ease)
    new_ease = max(MIN_EASE, min(MAX_EASE, ease + _EASE_DELTA[rating]))

    return ReviewSchedule(
        interval_days=new_interval,
        ease=new_ease,
        next_due_at=now + timedelta(days=new_interval),
    )
