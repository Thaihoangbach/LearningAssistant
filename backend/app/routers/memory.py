"""API routes cho ký ức episodic — xem và xoá.

Ký ức chi phối câu trả lời mà người dùng nhận được, nên phải xem được và xoá
được. Đây là lý do endpoint DELETE tồn tại ngay từ đầu chứ không phải tính năng
thêm cho đủ bộ CRUD.

Embedding nằm THẲNG trên cột MemoryEvent.embedding (app/memory/service.py), nên
xoá một hàng xoá luôn vector của nó trong cùng transaction — không còn nguy cơ
để lại vector mồ côi ở một index riêng như bản FAISS cũ.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import MemoryEvent, Topic

router = APIRouter(prefix="/memory", tags=["memory"])

DEFAULT_LIMIT = 50


@router.get("")
def list_memory(user_id: str, limit: int = DEFAULT_LIMIT, db: Session = Depends(get_db)):
    rows = (
        db.query(MemoryEvent)
        .filter(MemoryEvent.user_id == user_id)
        .order_by(MemoryEvent.created_at.desc())
        .limit(limit)
        .all()
    )

    topic_names = {
        t.id: t.name for t in db.query(Topic).filter(Topic.user_id == user_id).all()
    }

    return {
        "events": [
            {
                "id": r.id,
                "event_type": r.event_type,
                "content": r.content,
                "importance": r.importance,
                "topic_name": topic_names.get(r.topic_id),
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "access_count": r.access_count or 0,
            }
            for r in rows
        ]
    }


@router.delete("/{event_id}")
def delete_memory(event_id: str, user_id: str, db: Session = Depends(get_db)):
    event = (
        db.query(MemoryEvent)
        .filter(MemoryEvent.id == event_id, MemoryEvent.user_id == user_id)
        .first()
    )
    if not event:
        raise HTTPException(404, "Không tìm thấy ký ức này.")

    db.delete(event)
    db.commit()
    return {"status": "deleted", "event_id": event_id}
