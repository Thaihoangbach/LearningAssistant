"""Hợp nhất ba tầng ký ức/cá nhân hoá sau MỘT điểm gọi duy nhất.

Trước khi có module này, logic quyết định trình độ bị chép làm hai bản gần
giống nhau ở app/routers/chat.py::_apply_learning_profile và
app/routers/quiz.py::_resolve_quiz_difficulty — sửa một bên quên bên kia là
chuyện sớm muộn. Cả hai router giờ gọi vào đây.

Ba tầng gộp lại:
- long-term semantic TĨNH: LearningProfile (người dùng tự khai)
- long-term semantic ĐỘNG: MasteryScore (suy ra từ hành vi làm bài)
- episodic: app/memory/service.py::recall_events (từng sự kiện học tập cụ thể)

Tầng short-term (N lượt hỏi gần nhất trong cùng hội thoại) KHÔNG nằm ở đây —
nó thuộc về một hội thoại cụ thể, do app/routers/chat.py tự nạp từ bảng
Message. Gộp nó vào đây sẽ buộc mọi phía gọi phải biết về conversation_id kể
cả khi không có hội thoại nào (ví dụ lúc sinh quiz).
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from app.models import LearningProfile, MasteryScore, Topic
from app.services.learning_profile import (
    infer_level_from_mastery,
    resolve_effective_level,
    should_update_preference,
)
from app.services.mastery import decay_unpractised

# Cùng ngưỡng "yếu" với app/services/mastery.py::classify_mastery để không có
# hai bộ ngưỡng lệch nhau trong cùng hệ thống.
WEAK_TOPIC_THRESHOLD = 0.4


@dataclass
class LearnerContext:
    effective_level: Optional[str] = None
    learning_goal: Optional[str] = None
    recalled_events: List[str] = field(default_factory=list)
    weak_topics: List[str] = field(default_factory=list)


def _default_recall(db, user_id, query):
    from app.memory.service import recall_events

    return recall_events(db, user_id, query)


def _avg_mastery(db, user_id: str) -> Optional[float]:
    rows = db.query(MasteryScore).filter(MasteryScore.user_id == user_id).all()
    # Dùng điểm ĐÃ SUY GIẢM, nếu không thì trình độ suy ra ở đây sẽ lệch với
    # con số dashboard hiển thị (app/routers/mastery.py).
    scores = [decay_unpractised(s.score, s.updated_at) for s in rows]
    return sum(scores) / len(scores) if scores else None


def _weak_topics(db, user_id: str) -> List[str]:
    rows = (
        db.query(MasteryScore, Topic)
        .join(Topic, MasteryScore.topic_id == Topic.id)
        .filter(MasteryScore.user_id == user_id)
        .all()
    )
    # Lọc theo điểm đã suy giảm, không lọc trong SQL: chủ đề từng giỏi nhưng
    # lâu không ôn phải được coi là yếu trở lại.
    weak = [
        (decay_unpractised(s.score, s.updated_at), t.name)
        for s, t in rows
        if decay_unpractised(s.score, s.updated_at) < WEAK_TOPIC_THRESHOLD
    ]
    weak.sort(key=lambda pair: pair[0])
    return [name for _, name in weak]


def build_learner_context(
    db,
    user_id: str,
    requested_level: Optional[str] = None,
    query: Optional[str] = None,
    recall_fn=None,
) -> LearnerContext:
    """Trả về toàn bộ bối cảnh cá nhân hoá cho một request.

    `query` là câu hỏi hiện tại, dùng để truy hồi ký ức liên quan. Không truyền
    `query` thì BỎ QUA hẳn bước truy hồi — tránh tốn một lượt embed cho những
    phía gọi không dùng tới ký ức."""
    recall_fn = recall_fn or _default_recall

    profile = db.query(LearningProfile).filter(LearningProfile.user_id == user_id).first()
    stored_level = profile.preferred_level if profile else None
    learning_goal = profile.learning_goal if profile else None

    # Chỉ ghi đè preference khi request TỰ khai báo level tường minh — request
    # dùng lại preference cũ hoặc dùng giá trị suy ra không được phép âm thầm
    # ghi đè (xem app/services/learning_profile.py::should_update_preference).
    if should_update_preference(requested_level):
        if profile:
            profile.preferred_level = requested_level
            profile.updated_at = datetime.utcnow()
        else:
            profile = LearningProfile(user_id=user_id, preferred_level=requested_level)
            db.add(profile)
        db.commit()

    inferred_level = None
    if not requested_level and not stored_level:
        inferred_level = infer_level_from_mastery(_avg_mastery(db, user_id))

    recalled_events: List[str] = []
    if query:
        recalled_events = [e.content for e in recall_fn(db, user_id, query)]

    return LearnerContext(
        effective_level=resolve_effective_level(requested_level, stored_level, inferred_level),
        learning_goal=learning_goal,
        recalled_events=recalled_events,
        weak_topics=_weak_topics(db, user_id),
    )
