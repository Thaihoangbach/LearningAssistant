"""Tính tín hiệu Retention (mức nhớ) theo chủ đề, từ lịch sử FlashcardReview.

Retention TÁCH BIỆT khỏi Comprehension (app/services/mastery.py) — Quiz đo
hiểu, Flashcard đo nhớ, hai tín hiệu không gộp thành một công thức, chỉ
cùng xuất hiện trong Learning State (app/services/learning_state.py) để
Study Plan đọc.

Khác với compute_mastery(), điểm Retention KHÔNG cache lại (không có bảng
kiểu MasteryScore) — tính lại từ toàn bộ lịch sử FlashcardReview mỗi lần
đọc, nên trọng số suy giảm theo thời gian (recency weight) trong hàm này
đã tự phản ánh đúng "hiện tại". Không cần thêm một hàm decay-khi-không-
luyện riêng như app/services/mastery.py::decay_unpractised — hàm đó chỉ
cần thiết vì MasteryScore là giá trị CACHE, có thể cũ hơn thời điểm đọc.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

# Cùng số ngày bán rã với app/services/mastery.py (14 ngày) để hai tín hiệu
# "nhạy" như nhau với độ mới của dữ liệu — khai báo ĐỘC LẬP, không import từ
# mastery.py, vì đây là tín hiệu tách biệt.
HALF_LIFE_DAYS = 14.0

# Ánh xạ 4 mức đánh giá flashcard (app/services/spaced_repetition.py) sang
# thang điểm [0, 1] — CỐ Ý khớp ngưỡng phân loại của classify_mastery()
# (0.75 "tốt", 0.4 "trung bình"): "good" = 0.75, "hard" = 0.4, để Retention
# và Comprehension dùng chung một ngôn ngữ phân loại dù công thức khác nhau.
RATING_SCORE = {"again": 0.0, "hard": 0.4, "good": 0.75, "easy": 1.0}


@dataclass
class ReviewEvent:
    rating: str
    reviewed_at: datetime


def _to_naive_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=None) if value.tzinfo is not None else value


def _recency_weight(reviewed_at: datetime, now: datetime) -> float:
    age_days = max((_to_naive_utc(now) - _to_naive_utc(reviewed_at)).total_seconds() / 86400.0, 0.0)
    return 0.5 ** (age_days / HALF_LIFE_DAYS)


def compute_retention(reviews: List[ReviewEvent], now: Optional[datetime] = None) -> Optional[float]:
    """Trả về điểm retention trong khoảng [0, 1], hoặc None nếu chưa có lượt ôn nào."""
    if not reviews:
        return None

    now = now or datetime.now(timezone.utc)
    total_weight = 0.0
    weighted_score = 0.0

    for r in reviews:
        w = _recency_weight(r.reviewed_at, now)
        total_weight += w
        weighted_score += w * RATING_SCORE[r.rating]

    if total_weight == 0:
        return None

    return max(0.0, min(1.0, weighted_score / total_weight))
