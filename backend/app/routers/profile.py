"""API routes cho Learning Profile — cá nhân hóa dài hạn.

Chỉ chứa phần TĨNH do người dùng tự khai (`preferred_level`, `learning_goal`)
và trạng thái HIỆU LỰC đang áp dụng ngay bây giờ (`effective_level` +
`effective_level_source`) — trả lời đúng câu "hệ thống đang coi tôi trình độ
gì, và vì sao" mà trước đây Profile không hiển thị dù đã tính sẵn ở
app/services/learning_profile.py.

`weak_topics`/`mastered_topics` đã BỎ khỏi router này — đó là Learning State
(suy ra từ MasteryScore), đã có màn hình riêng ở app/routers/mastery.py; giữ
cả ở đây là lặp dữ liệu, tạo cảm giác Profile là "Dashboard thứ hai".
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import ensure_user, get_db
from app.llm.guardrail import BLOCKED_MESSAGE, contains_hard_block_pattern
from app.models import LearningProfile, MasteryScore
from app.services.learning_profile import infer_level_from_mastery, resolve_effective_level
from app.services.mastery import decay_unpractised

router = APIRouter(prefix="/profile", tags=["profile"])


def _avg_mastery(db: Session, user_id: str) -> float | None:
    """Trùng logic với app/services/learner_context.py::_avg_mastery — chấp
    nhận lặp lại một truy vấn nhỏ thay vì import hàm private xuyên module,
    cùng lý do đã áp dụng cho các ngưỡng mastery ở router khác trong hệ thống
    (mỗi router tự đứng độc lập, không ràng buộc vào nội bộ module kia)."""
    rows = db.query(MasteryScore).filter(MasteryScore.user_id == user_id).all()
    scores = [decay_unpractised(s.score, s.updated_at) for s in rows]
    return sum(scores) / len(scores) if scores else None


@router.get("")
def get_profile(user_id: str, db: Session = Depends(get_db)):
    profile = db.query(LearningProfile).filter(LearningProfile.user_id == user_id).first()
    stored_level = profile.preferred_level if profile else None

    inferred_level = None
    if not stored_level:
        inferred_level = infer_level_from_mastery(_avg_mastery(db, user_id))

    effective_level = resolve_effective_level(None, stored_level, inferred_level)
    if stored_level:
        effective_level_source = "declared"
    elif inferred_level:
        effective_level_source = "inferred"
    else:
        effective_level_source = None

    return {
        "preferred_level": stored_level,
        "learning_goal": profile.learning_goal if profile else None,
        "effective_level": effective_level,
        "effective_level_source": effective_level_source,
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
    dùng truyền level/difficulty tường minh — xem app/services/learning_profile.py.

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
        ensure_user(db, req.user_id)
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


@router.delete("")
def reset_profile(user_id: str, db: Session = Depends(get_db)):
    """Đặt lại phần TỰ KHAI (preferred_level, learning_goal) về rỗng.

    Chỉ xoá hàng LearningProfile — KHÔNG đụng MasteryScore/Attempt/MemoryEvent.
    Ranh giới Profile (tự khai) vs Learning State (hệ thống quan sát/suy ra)
    phải giữ đúng kể cả ở hành vi reset này; xoá lịch sử học tập không phải
    việc của nút này."""
    profile = db.query(LearningProfile).filter(LearningProfile.user_id == user_id).first()
    if profile:
        db.delete(profile)
        db.commit()
    return {"status": "reset"}
