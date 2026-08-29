"""API route cho phần dashboard của F4 — tổng quan mastery theo chủ đề.

Chỉ đọc dữ liệu đã có sẵn (MasteryScore được ghi khi nộp quiz ở app/routers/quiz.py),
không tính toán lại công thức mastery ở đây.
"""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.flashcard_service import count_due
from app.mastery import classify_mastery, decay_unpractised
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

    now = datetime.utcnow()
    topics = []
    for score, topic in scores:
        current = decay_unpractised(score.score, score.updated_at, now=now)
        topics.append(
            {
                "topic_id": topic.id,
                "topic_name": topic.name,
                "course_name": topic.course_name,
                # `score` là mức thành thạo ƯỚC LƯỢNG HIỆN TẠI (đã tính việc lâu
                # không luyện); `score_raw` là mức đo được ở lần làm bài cuối.
                # Trả cả hai để người dùng không bối rối khi thấy điểm tụt dù
                # không làm gì — họ nhìn được cả hai con số và biết vì sao.
                "score": current,
                "score_raw": score.score,
                "days_since_practice": (
                    (now - _to_naive(score.updated_at)).days if score.updated_at else None
                ),
                "level": classify_mastery(current),
                "updated_at": score.updated_at.isoformat(),
            }
        )
    topics.sort(key=lambda t: t["score"])

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
                # Đáp án người học đã chọn nói lên KIỂU hiểu sai, không chỉ
                # việc sai — đáp án nhiễu vốn được thiết kế là nhầm lẫn hợp lý.
                "selected_answer": attempt.selected_answer,
                "explanation": item.explanation,
                "difficulty": item.difficulty,
                "topic_name": topic_names.get(item.topic_id),
                "source_document": item.source_document,
                "source_position": item.source_position,
                "attempted_at": attempt.attempted_at.isoformat() if attempt.attempted_at else None,
            }
            for attempt, item in rows
        ]
    }
