"""Ghi và truy hồi ký ức episodic — vector embedding nằm THẲNG trên
MemoryEvent (app/models.py), không còn một FAISS index riêng theo user_id
(app/memory/store.py, đã gỡ bỏ khi chuyển sang Postgres+pgvector).

`embed_fn` inject được để test bằng fake, không cần gọi Cohere thật — cùng
khuôn Dependency Injection đã dùng cho `reranker` ở app/retrieval/pipeline.py
và `llm_client` ở app/llm/rag.py. Import nặng nằm LƯỜI bên trong hàm vì lý
do đó.
"""

from datetime import datetime, timezone
from typing import List, Optional

import numpy as np
from sqlalchemy import select

from app.memory.scoring import ScoredEvent, importance_for, select_top_events
from app.models import MemoryEvent

# Số ứng viên lấy trước khi chấm điểm recency/importance và cắt xuống
# MAX_RECALLED — lấy dư để hai yếu tố đó còn chỗ đảo thứ hạng so với
# relevance thuần (xem app/memory/scoring.py::select_top_events).
CANDIDATE_POOL = 20


def _default_embed(text: str):
    from app.ingestion.embedder import embed_query

    return embed_query(text)


def record_event(
    db,
    user_id: str,
    event_type: str,
    content: str,
    topic_id: Optional[str] = None,
    source_ref: Optional[str] = None,
    embed_fn=None,
) -> MemoryEvent:
    """Ghi một sự kiện học tập, kèm embedding của chính nó để truy hồi được
    về sau — MỘT bản ghi, MỘT transaction (khác bản FAISS cũ: ghi DB rồi ghi
    file index RIÊNG, hai bước có thể lệch pha nếu bước sau lỗi).

    `content` do phía gọi dựng bằng template cố định — KHÔNG gọi LLM để viết.

    Lỗi embedding (API Cohere lỗi/rớt mạng) KHÔNG được chặn đứng việc ghi lại
    sự kiện học tập — `embedding` nullable đúng vì lý do này; sự kiện vẫn có
    giá trị hiển thị ở trang Memory dù không truy hồi ngữ nghĩa được."""
    embed_fn = embed_fn or _default_embed

    embedding = None
    try:
        embedding = np.asarray(embed_fn(content), dtype="float32")
    except Exception:  # noqa: BLE001 — xem docstring: không chặn ghi sự kiện
        pass

    event = MemoryEvent(
        user_id=user_id,
        event_type=event_type,
        topic_id=topic_id,
        content=content,
        importance=importance_for(event_type),
        source_ref=source_ref,
        access_count=0,
        embedding=embedding,
    )
    db.add(event)
    db.commit()

    return event


def recall_events(
    db,
    user_id: str,
    query: str,
    now: Optional[datetime] = None,
    embed_fn=None,
) -> List[ScoredEvent]:
    """Trả về tối đa MAX_RECALLED ký ức liên quan nhất tới `query`.

    Chỉ xét sự kiện CỦA ĐÚNG user_id này VÀ có embedding (một sự kiện ghi lúc
    Cohere đang lỗi sẽ có `embedding IS NULL` — không có gì để so cosine,
    loại khỏi truy hồi ngữ nghĩa thay vì gây lỗi so sánh với NULL)."""
    embed_fn = embed_fn or _default_embed
    query_embedding = embed_fn(query)

    stmt = (
        select(MemoryEvent, MemoryEvent.embedding.cosine_distance(query_embedding).label("distance"))
        .where(MemoryEvent.user_id == user_id, MemoryEvent.embedding.is_not(None))
        .order_by("distance")
        .limit(CANDIDATE_POOL)
    )
    rows = db.execute(stmt).all()
    if not rows:
        return []

    candidates = [
        ScoredEvent(
            event_id=r.id,
            event_type=r.event_type,
            content=r.content,
            importance=r.importance,
            created_at=r.created_at,
            relevance=1.0 - float(distance),
        )
        for r, distance in rows
    ]

    selected = select_top_events(candidates, now=now)

    if selected:
        selected_ids = {e.event_id for e in selected}
        accessed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        for r, _ in rows:
            if r.id in selected_ids:
                r.last_accessed_at = accessed_at
                r.access_count = (r.access_count or 0) + 1
        db.commit()

    return selected
