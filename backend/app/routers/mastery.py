"""API route cho phần dashboard của F4 — tổng quan mastery theo chủ đề.

Chỉ đọc dữ liệu đã có sẵn (MasteryScore được ghi khi nộp quiz ở app/routers/quiz.py),
không tính toán lại công thức mastery ở đây.
"""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.flashcard_service import count_due
from app.mastery import classify_mastery
from app.models import Attempt, Document, MasteryScore, Quiz, QuizItem, Topic

router = APIRouter(prefix="/mastery", tags=["mastery"])

# Cửa sổ so sánh để trả lời câu hỏi người học thực sự quan tâm — "tuần này tôi
# khá hơn tuần trước chưa" — thay vì chỉ đưa ra một điểm số hiện tại.
TREND_WINDOW_DAYS = 7
MAX_MISTAKES_RETURNED = 20


def _accuracy(attempts) -> float | None:
    if not attempts:
        return None
    return sum(1 for a in attempts if a.is_correct) / len(attempts)


def _to_naive(value: datetime) -> datetime:
    return value.replace(tzinfo=None) if value.tzinfo is not None else value


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

    # Xu hướng: so tỉ lệ đúng của tuần này với tuần trước. Dữ liệu đã nằm sẵn
    # trong bảng Attempt từ lâu, chỉ là chưa ai hiển thị nó — mà "tôi có khá
    # lên không" mới là câu người học thực sự muốn biết, chứ không phải một
    # điểm số tĩnh.
    now = datetime.utcnow()
    recent_cutoff = now - timedelta(days=TREND_WINDOW_DAYS)
    previous_cutoff = now - timedelta(days=TREND_WINDOW_DAYS * 2)

    recent = [a for a in attempts if _to_naive(a.attempted_at) >= recent_cutoff]
    previous = [
        a for a in attempts if previous_cutoff <= _to_naive(a.attempted_at) < recent_cutoff
    ]

    return {
        "topics": topics,
        "summary": {
            "documents_ready": documents_ready,
            "documents_processing": documents_processing,
            "quizzes_taken": quizzes_taken,
            "attempts_total": attempts_total,
            "attempts_correct": attempts_correct,
            "avg_mastery": avg_mastery,
            "flashcards_due": count_due(db, user_id),
            "accuracy_recent": _accuracy(recent),
            "accuracy_previous": _accuracy(previous),
            "trend_window_days": TREND_WINDOW_DAYS,
            "mistakes_total": attempts_total - attempts_correct,
        },
    }


@router.get("/mistakes")
def get_mistakes(user_id: str, limit: int = MAX_MISTAKES_RETURNED, db: Session = Depends(get_db)):
    """Kho câu đã trả lời sai.

    Với người tự học, đây là dữ liệu giá trị nhất mà hệ thống đang vứt đi sau
    mỗi lần làm quiz: câu hỏi, đáp án đúng, giải thích và nguồn đều đã lưu
    trong QuizItem, chỉ chưa bao giờ được đưa trở lại cho người dùng."""
    rows = (
        db.query(Attempt, QuizItem)
        .join(QuizItem, Attempt.quiz_item_id == QuizItem.id)
        .filter(Attempt.user_id == user_id, Attempt.is_correct == False)  # noqa: E712
        .order_by(Attempt.attempted_at.desc())
        .limit(limit)
        .all()
    )

    topic_names = {t.id: t.name for t in db.query(Topic).filter(Topic.user_id == user_id).all()}

    return {
        "mistakes": [
            {
                "quiz_item_id": item.id,
                "question": item.question,
                "correct_answer": item.correct_answer,
                "explanation": item.explanation,
                "topic_name": topic_names.get(item.topic_id),
                "source_document": item.source_document,
                "source_position": item.source_position,
                "attempted_at": attempt.attempted_at.isoformat() if attempt.attempted_at else None,
            }
            for attempt, item in rows
        ]
    }
