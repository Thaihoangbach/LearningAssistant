"""API route cho kế hoạch học tập (TC15, TC16).

Tính lại toàn bộ mỗi lần gọi từ Topic/MasteryScore hiện có — xem
app/study_planner.py để biết lý do không cần bảng StudyPlan riêng.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import MasteryScore, Topic
from app.study_planner import TopicPriority, generate_plan

router = APIRouter(prefix="/study-plan", tags=["study-plan"])


@router.get("")
def get_study_plan(user_id: str, days: int, course_name: str | None = None, db: Session = Depends(get_db)):
    topics_query = db.query(Topic).filter(Topic.user_id == user_id)
    if course_name:
        topics_query = topics_query.filter(Topic.course_name == course_name)
    topics = topics_query.all()

    scores_by_topic_id = {
        s.topic_id: s.score
        for s in db.query(MasteryScore).filter(MasteryScore.user_id == user_id).all()
    }

    priorities = [
        TopicPriority(topic_name=t.name, score=scores_by_topic_id.get(t.id))
        for t in topics
    ]
    plan = generate_plan(priorities, days=days)

    return {"days": [{"day": d.day, "topics": d.topics} for d in plan]}
