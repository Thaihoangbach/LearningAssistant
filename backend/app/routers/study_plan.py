"""API route cho kế hoạch học tập (TC15, TC16).

Tính lại toàn bộ mỗi lần gọi từ Topic/MasteryScore hiện có — xem
app/services/study_planner.py để biết lý do không cần bảng StudyPlan riêng.
"""

from datetime import date, datetime, time

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.ingestion.outline import filter_topic_titles
from app.memory.service import record_event
from app.models import CourseDeadline, Document, DocumentTopic, MasteryScore, MemoryEvent, Topic
from app.services.learning_policy import recommend_action
from app.services.learning_state import get_learning_states
from app.services.mastery import decay_unpractised
from app.services.study_planner import CoursePlanInput, TopicPriority, generate_multi_course_plan

router = APIRouter(prefix="/study-plan", tags=["study-plan"])

# Trần trên cho số ngày còn lại tới hạn thi của MỘT môn. Không có trần này,
# một ngày thi ở rất xa tương lai khiến generate_multi_course_plan() sinh ra
# hàng trăm ngày (phần lớn trống — xem docstring của hàm đó) trong JSON trả
# về. Cùng giá trị 60 với MAX_PLAN_DAYS (app/services/capability_detector.py)
# và _MAX_PLAN_TOPICS (app/services/study_planner.py) — cả hai đã dùng 60 làm
# trần hợp lý cho input bất thường kiểu này; định nghĩa lại hằng số cục bộ ở
# đây thay vì import từ capability_detector.py vì module đó là để phân tích
# câu hỏi chat, không liên quan.
MAX_DAYS_LEFT = 60


@router.get("")
def get_study_plan(
    user_id: str,
    course_names: list[str] = Query(...),
    db: Session = Depends(get_db),
):
    # Bỏ trùng, giữ thứ tự — tránh đếm gấp đôi chủ đề của một môn nếu query
    # param bị lặp (?course_names=CSDL&course_names=CSDL).
    course_names = list(dict.fromkeys(course_names))

    deadlines = {
        d.course_name: d.exam_date
        for d in db.query(CourseDeadline)
        .filter(CourseDeadline.user_id == user_id, CourseDeadline.course_name.in_(course_names))
        .all()
    }
    missing = [c for c in course_names if c not in deadlines]
    if missing:
        raise HTTPException(400, f"Chưa đặt ngày thi cho môn: {', '.join(missing)}.")

    today = date.today()
    reviewed_today_ids = _topics_reviewed_today(db, user_id)

    scores_by_topic_id = {
        s.topic_id: decay_unpractised(s.score, s.updated_at)
        for s in db.query(MasteryScore).filter(MasteryScore.user_id == user_id).all()
    }
    order_by_name = {
        dt.title: dt.order_index
        for dt in db.query(DocumentTopic).filter(DocumentTopic.user_id == user_id).all()
    }

    # (course_name, topic_name) -> topic_id / document_id, dùng để đính kèm
    # thêm thông tin vào MỗI chủ đề khi trả JSON (MergedTopic thuần chỉ có
    # tên + môn — xem app/services/study_planner.py). Trong phạm vi một môn,
    # tên chủ đề là duy nhất (Topic khoá theo (user_id, course_name, name))
    # nên các khoá này không mập mờ.
    topic_id_by_key: dict[tuple[str, str], str] = {}
    doc_id_by_key: dict[tuple[str, str], str] = {}

    course_inputs: list[CoursePlanInput] = []
    for course_name in course_names:
        exam_date = deadlines[course_name]
        if exam_date < today:
            continue  # đã qua ngày thi -> không còn góp mặt trong kế hoạch (spec §6)
        # Trần MAX_DAYS_LEFT chặn input bất thường (hạn thi rất xa) sinh ra kế
        # hoạch hàng trăm ngày phần lớn trống.
        days_left = max(min((exam_date - today).days, MAX_DAYS_LEFT), 1)

        topics = db.query(Topic).filter(Topic.user_id == user_id, Topic.course_name == course_name).all()
        # Cùng lớp lọc chất lượng với chat capability (app/routers/chat.py::
        # _build_study_plan_result, BUG-001).
        plausible_names = set(filter_topic_titles([t.name for t in topics]))
        topics = [t for t in topics if t.name in plausible_names]

        for t in topics:
            topic_id_by_key[(course_name, t.name)] = t.id

        # Chủ đề trùng tên có thể tồn tại ở nhiều tài liệu của CÙNG một môn —
        # lấy tài liệu ĐẦU TIÊN tìm thấy làm đại diện (đủ dùng để tự điền sẵn
        # tài liệu lúc bấm "Làm quiz"/"Ôn flashcard" từ lịch, người dùng vẫn
        # đổi tay được nếu không đúng ý). Lọc theo course_name của CHÍNH môn
        # này (khác `order_by_name` phía trên, vốn không lọc theo môn) để
        # không lỡ trỏ sang tài liệu của môn khác khi hai môn trùng tên
        # chủ đề.
        for title, document_id in (
            db.query(DocumentTopic.title, DocumentTopic.document_id)
            .join(Document, Document.id == DocumentTopic.document_id)
            .filter(Document.user_id == user_id, Document.course_name == course_name)
            .all()
        ):
            doc_id_by_key.setdefault((course_name, title), document_id)

        course_inputs.append(
            CoursePlanInput(
                course_name=course_name,
                topics=[
                    TopicPriority(
                        topic_name=t.name,
                        score=scores_by_topic_id.get(t.id),
                        order_index=order_by_name.get(t.name),
                    )
                    for t in topics
                ],
                days_left=days_left,
            )
        )

    plan = generate_multi_course_plan(course_inputs)

    # Learning Loop Phase 1: gợi ý hành động tiếp theo (Quiz/Flashcard/Learn)
    # + lý do, để "Làm quiz"/"Ôn flashcard" trên lịch mang theo ngữ cảnh giải
    # thích (nguyên tắc AI đề xuất, học sinh kiểm soát). Tính MỘT LẦN mỗi
    # topic_id (không phải mỗi lần chủ đề đó xuất hiện lặp lại qua các ngày
    # trong kế hoạch) — Comprehension/Retention của một topic không đổi theo
    # ngày được xếp lịch.
    learning_states = get_learning_states(db, user_id, list(set(topic_id_by_key.values())))
    recommendation_by_topic_id = {
        topic_id: recommend_action(state) for topic_id, state in learning_states.items()
    }

    return {
        "days": [
            {
                "day": d.day,
                "topics": [
                    {
                        "name": t.name,
                        "course_name": t.course_name,
                        "document_id": doc_id_by_key.get((t.course_name, t.name)),
                        # Chỉ ngày 1 (hôm nay) mang ý nghĩa "đã ôn hôm nay" —
                        # nó vẫn xuất hiện ở TOÀN BỘ kế hoạch (không bị xoá
                        # khỏi ngày sau nếu mastery vẫn cho là còn yếu, spec
                        # §9), chỉ khác nhau ở cờ này để UI tự quyết định
                        # cách hiển thị (vd: đẩy xuống cuối danh sách, khoá
                        # nút) thay vì biến mất hẳn.
                        "reviewed_today": (
                            d.day == 1
                            and topic_id_by_key.get((t.course_name, t.name)) in reviewed_today_ids
                        ),
                        **_recommendation_fields(
                            recommendation_by_topic_id.get(topic_id_by_key.get((t.course_name, t.name)))
                        ),
                    }
                    for t in d.topics
                ],
            }
            for d in plan
        ]
    }


def _recommendation_fields(rec) -> dict:
    """`rec` là None khi chủ đề không tra được topic_id (không nên xảy ra
    trong luồng bình thường, nhưng an toàn hơn là để None thay vì KeyError)."""
    if rec is None:
        return {"recommended_action": None, "reason": None}
    return {"recommended_action": rec.action, "reason": rec.reason}


TOPIC_REVIEWED_EVENT_TYPE = "topic_reviewed_manual"


def _topics_reviewed_today(db: Session, user_id: str) -> set[str]:
    """ID các chủ đề người dùng đã tự bấm "Đã ôn xong" HÔM NAY — dùng để ẩn
    khỏi NGÀY 1 của lịch hôm nay (spec §9), KHÔNG ẩn khỏi cả kế hoạch. KHÔNG
    đụng tới mastery: tự nhận đã ôn là tín hiệu chưa kiểm chứng, khác Attempt
    từ quiz (có đúng/sai khách quan).

    Trả về ID thay vì TÊN: cùng một tên chủ đề có thể tồn tại hợp lệ ở nhiều
    môn khác nhau (Topic khoá theo (user_id, course_name, name)), nên lọc
    theo tên sẽ ẩn nhầm chủ đề trùng tên ở môn khác — ID thì không mập mờ.

    "Hôm nay" tính theo UTC (datetime.utcnow().date()), không phải giờ máy
    chủ (date.today()) — MemoryEvent.created_at cũng được ghi bằng
    datetime.utcnow() (app/models.py), nếu so lệch múi giờ thì ranh giới
    "hôm nay" sẽ sai lệch vài giờ trên máy chủ không chạy UTC."""
    start_of_day = datetime.combine(datetime.utcnow().date(), time.min)
    rows = (
        db.query(Topic.id)
        .join(MemoryEvent, MemoryEvent.topic_id == Topic.id)
        .filter(
            MemoryEvent.user_id == user_id,
            MemoryEvent.event_type == TOPIC_REVIEWED_EVENT_TYPE,
            MemoryEvent.created_at >= start_of_day,
        )
        .all()
    )
    return {topic_id for (topic_id,) in rows}


class MarkReviewedRequest(BaseModel):
    user_id: str
    topic_name: str
    course_name: str | None = None


@router.post("/review")
def mark_topic_reviewed(req: MarkReviewedRequest, db: Session = Depends(get_db)):
    topic = (
        db.query(Topic)
        .filter(
            Topic.user_id == req.user_id,
            Topic.course_name == req.course_name,
            Topic.name == req.topic_name,
        )
        .first()
    )
    if not topic:
        raise HTTPException(404, "Không tìm thấy chủ đề này.")

    record_event(
        db,
        user_id=req.user_id,
        event_type=TOPIC_REVIEWED_EVENT_TYPE,
        content=f"Đã tự đánh dấu ôn xong chủ đề \"{topic.name}\"",
        topic_id=topic.id,
    )
    return {"status": "recorded", "topic_name": topic.name}
