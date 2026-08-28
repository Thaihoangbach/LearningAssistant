"""Chấm điểm truy hồi ký ức episodic — hàm thuần, KHÔNG chạm DB hay FAISS.

Tách riêng khỏi store.py/service.py theo đúng khuôn đã dùng ở app/mastery.py và
app/study_planner.py: phần quyết định LOGIC phải test được mà không cần cài
faiss hay sentence-transformers.

Công thức truy hồi lấy ý tưởng từ ba tín hiệu độc lập nhau: sự kiện càng gần
đây càng đáng nhắc lại (recency), càng liên quan tới câu hỏi hiện tại càng đáng
nhắc lại (relevance), và có loại sự kiện tự nó đã quan trọng hơn loại khác —
làm sai một câu quiz nói lên nhiều điều về người học hơn là hỏi một câu bình
thường (importance).
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

HALF_LIFE_HOURS = 168.0  # 7 ngày

WEIGHT_RECENCY = 0.35
WEIGHT_RELEVANCE = 0.45
WEIGHT_IMPORTANCE = 0.20

MIN_SCORE = 0.25
MAX_RECALLED = 5

# Gán lúc GHI sự kiện bằng bảng tra cứu tĩnh — không gọi LLM để chấm mức quan
# trọng, đúng nguyên tắc chi phí ở PRD §6 (chỉ gọi LLM ở bước thật sự cần khả
# năng ngôn ngữ).
IMPORTANCE_BY_EVENT_TYPE = {
    "quiz_wrong": 0.9,
    "flashcard_again": 0.8,
    "concept_confused": 0.7,
    "abstention": 0.6,
    "quiz_right": 0.4,
    "question_asked": 0.3,
    "flashcard_easy": 0.2,
}
DEFAULT_IMPORTANCE = 0.3


@dataclass
class ScoredEvent:
    """Một ứng viên ký ức kèm độ liên quan đã tính sẵn bởi tầng gọi (service.py
    tính relevance bằng FAISS rồi truyền vào đây). `score` do select_top_events()
    điền, khởi tạo 0.0."""

    event_id: str
    event_type: str
    content: str
    importance: float
    created_at: datetime
    relevance: float
    score: float = 0.0


def importance_for(event_type: str) -> float:
    return IMPORTANCE_BY_EVENT_TYPE.get(event_type, DEFAULT_IMPORTANCE)


def _to_naive_utc(value: datetime) -> datetime:
    # Cùng lý do với app/mastery.py:26-27 — created_at đọc từ SQLite là naive,
    # còn `now` mặc định là aware; trừ trực tiếp hai kiểu này sẽ TypeError.
    return value.replace(tzinfo=None) if value.tzinfo is not None else value


def recency_weight(created_at: datetime, now: datetime) -> float:
    age_hours = max(
        (_to_naive_utc(now) - _to_naive_utc(created_at)).total_seconds() / 3600.0,
        0.0,
    )
    return 0.5 ** (age_hours / HALF_LIFE_HOURS)


def combine_score(recency: float, relevance: float, importance: float) -> float:
    score = (
        WEIGHT_RECENCY * recency
        + WEIGHT_RELEVANCE * relevance
        + WEIGHT_IMPORTANCE * importance
    )
    return max(0.0, min(1.0, score))


def select_top_events(
    events: List[ScoredEvent],
    now: Optional[datetime] = None,
    max_events: int = MAX_RECALLED,
    min_score: float = MIN_SCORE,
) -> List[ScoredEvent]:
    """Chấm điểm từng ứng viên, loại những cái dưới ngưỡng, trả về tối đa
    max_events cái điểm cao nhất. Ngưỡng tồn tại để một câu hỏi không liên quan
    gì tới quá khứ của người học thì KHÔNG bị nhét ký ức lạc đề vào prompt."""
    if not events:
        return []

    now = now or datetime.now(timezone.utc)

    scored: List[ScoredEvent] = []
    for e in events:
        e.score = combine_score(
            recency_weight(e.created_at, now),
            max(0.0, e.relevance),
            e.importance,
        )
        if e.score >= min_score:
            scored.append(e)

    scored.sort(key=lambda e: e.score, reverse=True)
    return scored[:max_events]
