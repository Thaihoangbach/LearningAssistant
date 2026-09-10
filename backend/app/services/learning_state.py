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
    mastery_row = (
        db.query(MasteryScore)
        .filter(MasteryScore.user_id == user_id, MasteryScore.topic_id == topic_id)
        .first()
    )
    comprehension = (
        decay_unpractised(mastery_row.score, mastery_row.updated_at, now=now)
        if mastery_row
        else None
    )

    review_rows = (
        db.query(FlashcardReview.rating, FlashcardReview.reviewed_at)
        .join(FlashcardItem, FlashcardReview.flashcard_item_id == FlashcardItem.id)
        .filter(FlashcardReview.user_id == user_id, FlashcardItem.topic_id == topic_id)
        .all()
    )
    reviews = [ReviewEvent(rating=rating, reviewed_at=reviewed_at) for rating, reviewed_at in review_rows]
    retention = compute_retention(reviews, now=now)

    return LearningState(topic_id=topic_id, comprehension=comprehension, retention=retention)
