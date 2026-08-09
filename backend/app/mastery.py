"""Tính mức độ thành thạo theo chủ đề (F4) — công thức rule-based đơn giản.

Đây là quyết định đã chốt trong kịch bản hạ cấp của PRD: KHÔNG dùng mô hình
Knowledge Tracing học sâu (kiểu MLFBK trong TutorLLM) ở MVP, mà dùng trọng
số suy giảm theo thời gian (recency-weighted average) — dễ hiểu, dễ giải
thích cho người dùng, và đủ để phục vụ F4/F5/F7.

Công thức: mỗi lượt làm bài đúng góp +1, sai góp 0, nhưng lượt càng gần đây
càng có trọng số cao hơn (nửa chu kỳ suy giảm 14 ngày) để phản ánh đúng
trạng thái "hiện tại" thay vì coi mọi lượt làm bài quan trọng như nhau.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

HALF_LIFE_DAYS = 14.0


@dataclass
class Attempt:
    is_correct: bool
    attempted_at: datetime


def _recency_weight(attempted_at: datetime, now: datetime) -> float:
    age_days = max((now - attempted_at).total_seconds() / 86400.0, 0.0)
    return 0.5 ** (age_days / HALF_LIFE_DAYS)


def compute_mastery(attempts: List[Attempt], now: Optional[datetime] = None) -> Optional[float]:
    """Trả về điểm mastery trong khoảng [0, 1], hoặc None nếu chưa có dữ liệu."""
    if not attempts:
        return None

    now = now or datetime.now(timezone.utc)
    total_weight = 0.0
    weighted_correct = 0.0

    for a in attempts:
        w = _recency_weight(a.attempted_at, now)
        total_weight += w
        if a.is_correct:
            weighted_correct += w

    if total_weight == 0:
        return None

    score = weighted_correct / total_weight
    return max(0.0, min(1.0, score))


def classify_mastery(score: float) -> str:
    if score >= 0.75:
        return "tốt"
    if score >= 0.4:
        return "trung bình"
    return "yếu"
