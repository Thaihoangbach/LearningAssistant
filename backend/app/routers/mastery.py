"""API route cho phần dashboard của F4 — tổng quan mastery theo chủ đề.

Chỉ đọc dữ liệu đã có sẵn (MasteryScore được ghi khi nộp quiz ở app/routers/quiz.py),
không tính toán lại công thức mastery ở đây.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.mastery import classify_mastery
from app.models import Attempt, Document, MasteryScore, Quiz, Topic

router = APIRouter(prefix="/mastery", tags=["mastery"])


@router.get("")
def get_mastery(user_id: str, db: Session = Depends(get_db)):
    scores = (
        db.query(MasteryScore, Topic)
        .join(Topic, MasteryScore.topic_id == Topic.id)
        .filter(MasteryScore.user_id == user_id)
        .order_by(MasteryScore.score.asc())
        .all()
    )

    topics = [
        {
            "topic_id": topic.id,
            "topic_name": topic.name,
            "course_name": topic.course_name,
            "score": score.score,
            "level": classify_mastery(score.score),
            "updated_at": score.updated_at.isoformat(),
        }
        for score, topic in scores
    ]

    documents_ready = (
        db.query(Document).filter(Document.user_id == user_id, Document.status == "sẵn sàng").count()
    )
    documents_processing = (
        db.query(Document).filter(Document.user_id == user_id, Document.status == "đang xử lý").count()
    )
    quizzes_taken = db.query(Quiz).filter(Quiz.user_id == user_id).count()
    attempts = db.query(Attempt).filter(Attempt.user_id == user_id).all()
    attempts_total = len(attempts)
    attempts_correct = sum(1 for a in attempts if a.is_correct)

    avg_mastery = sum(t["score"] for t in topics) / len(topics) if topics else None

    return {
        "topics": topics,
        "summary": {
            "documents_ready": documents_ready,
            "documents_processing": documents_processing,
            "quizzes_taken": quizzes_taken,
            "attempts_total": attempts_total,
            "attempts_correct": attempts_correct,
            "avg_mastery": avg_mastery,
        },
    }
