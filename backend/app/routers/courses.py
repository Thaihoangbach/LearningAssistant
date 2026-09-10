"""API routes cho môn học — danh sách tên môn đã có + ngày thi riêng từng môn.

Không phải một bảng Course độc lập có khoá ngoại: course_name vẫn là chuỗi
tự do trên Document/Topic (xem app/models.py::CourseDeadline docstring) —
router này chỉ tổng hợp danh sách tên môn ĐÃ CÓ (từ Document.course_name,
dùng cho autocomplete lúc upload — frontend/src/pages/UploadPage.jsx) và lưu
ngày thi riêng từng môn (dùng cho lập kế hoạch đa môn —
app/routers/study_plan.py).
"""

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.database import ensure_user, get_db
from app.models import CourseDeadline, Document

router = APIRouter(prefix="/courses", tags=["courses"])


@router.get("")
def list_courses(user_id: str, db: Session = Depends(get_db)):
    course_names = {
        c
        for (c,) in db.query(Document.course_name)
        .filter(Document.user_id == user_id, Document.course_name.isnot(None))
        .distinct()
        .all()
    }
    deadlines = {
        d.course_name: d.exam_date
        for d in db.query(CourseDeadline).filter(CourseDeadline.user_id == user_id).all()
    }
    return {
        "courses": [
            {
                "course_name": name,
                "exam_date": deadlines[name].isoformat() if name in deadlines else None,
            }
            for name in sorted(course_names)
        ]
    }


class SetExamDateRequest(BaseModel):
    user_id: str
    exam_date: date


@router.put("/{course_name}/exam-date")
def set_exam_date(course_name: str, req: SetExamDateRequest, db: Session = Depends(get_db)):
    ensure_user(db, req.user_id)
    stmt = insert(CourseDeadline).values(
        user_id=req.user_id, course_name=course_name, exam_date=req.exam_date
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_course_deadlines_user_course",
        set_={"exam_date": stmt.excluded.exam_date, "updated_at": datetime.utcnow()},
    )
    db.execute(stmt)
    db.commit()
    return {"course_name": course_name, "exam_date": req.exam_date.isoformat()}


@router.delete("/{course_name}/exam-date")
def delete_exam_date(course_name: str, user_id: str, db: Session = Depends(get_db)):
    deleted = (
        db.query(CourseDeadline)
        .filter(CourseDeadline.user_id == user_id, CourseDeadline.course_name == course_name)
        .delete()
    )
    db.commit()
    if not deleted:
        raise HTTPException(404, "Môn học này chưa có ngày thi để xoá.")
    return {"status": "deleted", "course_name": course_name}
