"""Learning State — trạng thái học tập hiện tại của MỘT chủ đề, gộp hai tín
hiệu tách biệt: Comprehension (từ Quiz/MasteryScore, app/services/mastery.py)
và Retention (từ Flashcard/FlashcardReview, app/services/retention.py).

Đọc trực tiếp, TÍNH LẠI mỗi lần gọi — không có bảng lưu riêng. Comprehension
vẫn đọc từ MasteryScore (bảng cache đã có, ghi bởi app/routers/quiz.py) rồi
áp decay_unpractised() như app/routers/study_plan.py đang làm; Retention
không có bảng cache tương đương nên tính thẳng từ toàn bộ lịch sử
FlashcardReview mỗi lần gọi (xem lý do trong app/services/retention.py).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models import FlashcardItem, FlashcardReview, MasteryScore
from app.services.mastery import decay_unpractised
from app.services.retention import ReviewEvent, compute_retention


@dataclass
class LearningState:
    topic_id: str
    comprehension: Optional[float]
    retention: Optional[float]


def get_learning_state(
    db: Session, user_id: str, topic_id: str, now: Optional[datetime] = None
) -> LearningState:
    return get_learning_states(db, user_id, [topic_id], now=now)[topic_id]


def get_learning_states(
    db: Session, user_id: str, topic_ids: list, now: Optional[datetime] = None
) -> dict:
    """Bản BULK của get_learning_state() — đúng 2 truy vấn CỐ ĐỊNH bất kể
    số lượng topic_ids, thay vì 2 truy vấn cho MỖI topic (N+1). Dùng ở nơi
    cần Learning State cho NHIỀU chủ đề cùng lúc trong một request (vd
    app/routers/study_plan.py dựng lịch nhiều môn, hàng chục chủ đề) — gọi
    get_learning_state() theo vòng lặp ở đó từng mất 17s/môn khi đo qua
    Postgres cloud (round-trip mạng nhân với số topic), N+1 kinh điển."""
    if not topic_ids:
        return {}

    mastery_rows = (
        db.query(MasteryScore)
        .filter(MasteryScore.user_id == user_id, MasteryScore.topic_id.in_(topic_ids))
        .all()
    )
    comprehension_by_topic = {
        row.topic_id: decay_unpractised(row.score, row.updated_at, now=now) for row in mastery_rows
    }

    review_rows = (
        db.query(FlashcardItem.topic_id, FlashcardReview.rating, FlashcardReview.reviewed_at)
        .join(FlashcardItem, FlashcardReview.flashcard_item_id == FlashcardItem.id)
        .filter(FlashcardReview.user_id == user_id, FlashcardItem.topic_id.in_(topic_ids))
        .all()
    )
    reviews_by_topic = {}
    for topic_id, rating, reviewed_at in review_rows:
        reviews_by_topic.setdefault(topic_id, []).append(ReviewEvent(rating=rating, reviewed_at=reviewed_at))

    return {
        topic_id: LearningState(
            topic_id=topic_id,
            comprehension=comprehension_by_topic.get(topic_id),
            retention=compute_retention(reviews_by_topic.get(topic_id, []), now=now),
        )
        for topic_id in topic_ids
    }
