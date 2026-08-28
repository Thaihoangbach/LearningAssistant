"""Ghi và truy hồi ký ức episodic — tầng nối giữa DB (app/models.py) và FAISS
index của memory (app/memory/store.py).

`embed_fn` và `store` inject được để test bằng fake, không cần cài faiss lẫn
sentence-transformers — cùng khuôn Dependency Injection đã dùng cho `reranker`
ở app/retrieval/pipeline.py và `llm_client` ở app/llm/rag.py. Import nặng nằm
LƯỜI bên trong hàm vì lý do đó.
"""

from datetime import datetime, timezone
from typing import List, Optional

import numpy as np

from app.memory.scoring import ScoredEvent, importance_for, select_top_events
from app.memory.store import MemoryRecord
from app.models import MemoryEvent

# Số ứng viên lấy từ FAISS trước khi chấm điểm và cắt xuống MAX_RECALLED —
# lấy dư để recency/importance còn có chỗ đảo thứ hạng so với relevance thuần.
CANDIDATE_POOL = 20


def _default_embed(text: str):
    from app.ingestion.embedder import embed_query

    return embed_query(text)


def _default_store(user_id: str):
    from app.memory.store import MemoryStore

    return MemoryStore(user_id=user_id)


def record_event(
    db,
    user_id: str,
    event_type: str,
    content: str,
    topic_id: Optional[str] = None,
    source_ref: Optional[str] = None,
    embed_fn=None,
    store=None,
) -> MemoryEvent:
    """Ghi một sự kiện học tập vào DB và index nó để truy hồi được về sau.

    `content` do phía gọi dựng bằng template cố định — KHÔNG gọi LLM để viết."""
    embed_fn = embed_fn or _default_embed
    store = store or _default_store(user_id)

    event = MemoryEvent(
        user_id=user_id,
        event_type=event_type,
        topic_id=topic_id,
        content=content,
        importance=importance_for(event_type),
        source_ref=source_ref,
        access_count=0,
    )
    db.add(event)
    db.commit()

    # embed_query() trả mảng 1 CHIỀU (dim,) — phải đưa về (1, dim) trước khi
    # đẩy vào FAISS, nếu không assert len(embeddings) == len(records) trong
    # MemoryStore.add() sẽ so 384 với 1 và vỡ.
    embedding = np.asarray(embed_fn(content), dtype="float32").reshape(1, -1)
    store.add(embedding, [MemoryRecord(event_id=event.id, text=content)])

    return event


def recall_events(
    db,
    user_id: str,
    query: str,
    now: Optional[datetime] = None,
    embed_fn=None,
    store=None,
) -> List[ScoredEvent]:
    """Trả về tối đa MAX_RECALLED ký ức liên quan nhất tới `query`.

    Lọc theo user_id NGAY SAU khi tra FAISS: index đã tách theo user nhưng vẫn
    kiểm tra lại ở tầng DB để không có đường nào rò ký ức sang người khác kể cả
    khi store bị truyền nhầm."""
    embed_fn = embed_fn or _default_embed
    store = store or _default_store(user_id)

    hits = store.search(embed_fn(query), top_k=CANDIDATE_POOL)
    if not hits:
        return []

    relevance_by_id = {record.event_id: score for record, score in hits}

    rows = (
        db.query(MemoryEvent)
        .filter(MemoryEvent.user_id == user_id, MemoryEvent.id.in_(list(relevance_by_id.keys())))
        .all()
    )
    if not rows:
        return []

    candidates = [
        ScoredEvent(
            event_id=r.id,
            event_type=r.event_type,
            content=r.content,
            importance=r.importance,
            created_at=r.created_at,
            relevance=relevance_by_id.get(r.id, 0.0),
        )
        for r in rows
    ]

    selected = select_top_events(candidates, now=now)

    if selected:
        selected_ids = {e.event_id for e in selected}
        accessed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        for r in rows:
            if r.id in selected_ids:
                r.last_accessed_at = accessed_at
                r.access_count = (r.access_count or 0) + 1
        db.commit()

    return selected
