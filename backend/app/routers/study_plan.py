"""API route cho kế hoạch học tập (TC15, TC16).

Tính lại toàn bộ mỗi lần gọi từ Topic/MasteryScore hiện có — xem
app/services/study_planner.py để biết lý do không cần bảng StudyPlan riêng.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.ingestion.outline import is_plausible_topic
from app.models import DocumentTopic, MasteryScore, Topic
from app.services.mastery import decay_unpractised
from app.services.study_planner import TopicPriority, generate_plan

router = APIRouter(prefix="/study-plan", tags=["study-plan"])


@router.get("")
def get_study_plan(user_id: str, days: int, course_name: str | None = None, db: Session = Depends(get_db)):
    topics_query = db.query(Topic).filter(Topic.user_id == user_id)
    if course_name:
        topics_query = topics_query.filter(Topic.course_name == course_name)
    topics = topics_query.all()

    # Cùng lớp lọc chất lượng với chat capability (app/routers/chat.py::
    # _build_study_plan_result, BUG-001) — cả hai lối vào phải xử lý nhất
    # quán để không lộ ra "kế hoạch" ghép từ Topic nhiễu ở nơi này trong khi
    # nơi kia đã chặn.
    topics = [t for t in topics if is_plausible_topic(t.name)]

    scores_by_topic_id = {
        s.topic_id: decay_unpractised(s.score, s.updated_at)
        for s in db.query(MasteryScore).filter(MasteryScore.user_id == user_id).all()
    }

    # Thứ tự chủ đề trong tài liệu gốc — dùng làm ràng buộc mềm khi hai chủ đề
    # cùng mức ưu tiên (app/services/study_planner.py).
    order_by_name = {
        dt.title: dt.order_index
        for dt in db.query(DocumentTopic).filter(DocumentTopic.user_id == user_id).all()
    }

    priorities = [
        TopicPriority(
            topic_name=t.name,
            score=scores_by_topic_id.get(t.id),
            order_index=order_by_name.get(t.name),
        )
        for t in topics
    ]
    plan = generate_plan(priorities, days=days)

    return {"days": [{"day": d.day, "topics": d.topics} for d in plan]}
