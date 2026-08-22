"""API routes cho Learning Profile — cá nhân hóa dài hạn (Giai đoạn 1 trong
hướng phát triển, xem docs/thesis Chương 8).

Gộp lại hai loại dữ liệu cá nhân hóa vốn tách riêng theo thiết kế
(architecture-diagrams.md): `preferred_level`/`learning_goal` do người dùng
tự khai báo (tĩnh, lưu trong bảng LEARNING_PROFILE), và `weak_topics` suy ra
từ MasteryScore (động, không lưu trùng ở đây — luôn đọc lại mới nhất).

CHƯA CHẠY ĐƯỢC TRONG SANDBOX NÀY: cần `pip install fastapi sqlalchemy`.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.llm.guardrail import BLOCKED_MESSAGE, contains_hard_block_pattern
from app.models import LearningProfile, MasteryScore, Topic

router = APIRouter(prefix="/profile", tags=["profile"])

# Cùng ngưỡng với app/llm/recommendation.py::_WEAK_THRESHOLD và
# app/mastery.py::classify_mastery — giữ độc lập thay vì import tên private
# xuyên module, chấp nhận trùng hằng số nhỏ để không ràng buộc router này vào
# nội bộ các module khác.
WEAK_MASTERY_THRESHOLD = 0.4
GOOD_MASTERY_THRESHOLD = 0.75
MAX_TOPICS_SHOWN = 3


@router.get("")
def get_profile(user_id: str, db: Session = Depends(get_db)):
    profile = db.query(LearningProfile).filter(LearningProfile.user_id == user_id).first()

    scores = (
        db.query(MasteryScore, Topic)
        .join(Topic, MasteryScore.topic_id == Topic.id)
        .filter(MasteryScore.user_id == user_id)
        .order_by(MasteryScore.score.asc())
        .all()
    )
    weak_topics = [topic.name for score, topic in scores if score.score < WEAK_MASTERY_THRESHOLD]
    mastered_topics = [topic.name for score, topic in scores if score.score >= GOOD_MASTERY_THRESHOLD]

    return {
        "preferred_level": profile.preferred_level if profile else None,
        "learning_goal": profile.learning_goal if profile else None,
        # weak_topics/mastered_topics suy ra từ MasteryScore NGAY tại thời điểm
        # gọi, KHÔNG lưu trong LEARNING_PROFILE — tránh hai nguồn dữ liệu lệch
        # nhau theo thời gian. Đây là "tóm tắt chủ đề đã học/chưa học" nêu ở
        # docs/thesis Chương 8, Giai đoạn 1.
        "weak_topics": weak_topics[:MAX_TOPICS_SHOWN],
        "mastered_topics": mastered_topics[:MAX_TOPICS_SHOWN],
        "updated_at": profile.updated_at.isoformat() if profile else None,
    }


class UpdateProfileRequest(BaseModel):
    user_id: str
    preferred_level: str | None = None  # "beginner" | "advanced" | None
    learning_goal: str | None = None


@router.put("")
def update_profile(req: UpdateProfileRequest, db: Session = Depends(get_db)):
    """Cập nhật thủ công qua màn hình hồ sơ (nếu có). Cùng bảng này cũng được
    /chat/ask và /quiz/generate tự động cập nhật `preferred_level` khi người
    dùng truyền level/difficulty tường minh — xem app/learning_profile.py.

    `learning_goal` được đọc lại và đưa vào prompt sinh câu trả lời ở NHIỀU
    lượt hỏi đáp sau này (app/llm/rag.py::_build_goal_block), khác với một
    câu hỏi chỉ dùng một lần rồi thôi — nên phải chặn injection ngay tại đây
    bằng rule-based check (contains_hard_block_pattern, cùng pattern với
    guardrail của câu hỏi), không đợi tới lúc dùng mới lọc."""
    if req.learning_goal and contains_hard_block_pattern(req.learning_goal):
        raise HTTPException(400, BLOCKED_MESSAGE)

    profile = db.query(LearningProfile).filter(LearningProfile.user_id == req.user_id).first()
    if profile:
        if req.preferred_level is not None:
            profile.preferred_level = req.preferred_level
        if req.learning_goal is not None:
            profile.learning_goal = req.learning_goal
        profile.updated_at = datetime.utcnow()
    else:
        profile = LearningProfile(
            user_id=req.user_id,
            preferred_level=req.preferred_level,
            learning_goal=req.learning_goal,
        )
        db.add(profile)
    db.commit()

    return {
        "preferred_level": profile.preferred_level,
        "learning_goal": profile.learning_goal,
        "updated_at": profile.updated_at.isoformat(),
    }
