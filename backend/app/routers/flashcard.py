"""API routes cho Flashcard (TC14) — tái sử dụng pattern app/routers/quiz.py."""

import os
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.ingestion.embedder import embed_query
from app.ingestion.outline import is_bibliography_like_chunk
from app.llm.client_factory import get_llm_client
from app.llm.flashcard_generator import generate_flashcards
from app.llm.rag import RetrievedChunk
from app.memory.service import record_event
from app.models import Document, FlashcardItem, FlashcardReview, FlashcardSet, Topic
from app.services.flashcard import due_items
from app.services.spaced_repetition import DEFAULT_EASE, VALID_RATINGS, schedule_next_review
from app.vectorstore.pgvector_store import PgVectorStore

router = APIRouter(prefix="/flashcard", tags=["flashcard"])


def _prioritize_core_content(chunks: List[RetrievedChunk]) -> List[RetrievedChunk]:
    """BUG-007 — đẩy các đoạn giống khu vực tham khảo/trích dẫn xuống CUỐI
    danh sách (KHÔNG xoá) trước khi đưa vào generator, để flashcard ưu tiên
    dạy nội dung cốt lõi. Tách thành hàm thuần để test được không cần Postgres
    thật (xem tests/test_flashcard.py)."""
    return sorted(chunks, key=lambda c: is_bibliography_like_chunk(c.text))


class GenerateFlashcardRequest(BaseModel):
    user_id: str
    document_id: str
    topic_name: str | None = None
    num_cards: int = 10


@router.post("/generate")
def generate(req: GenerateFlashcardRequest, db: Session = Depends(get_db)):
    doc = (
        db.query(Document)
        .filter(Document.id == req.document_id, Document.user_id == req.user_id, Document.status == "sẵn sàng")
        .first()
    )
    if not doc:
        raise HTTPException(400, "Tài liệu không tồn tại hoặc chưa sẵn sàng.")

    query_vector = embed_query(doc.file_name)
    store = PgVectorStore(db=db, user_id=req.user_id)
    # BUG-007: top_k nới rộng hơn app/routers/quiz.py (10 -> 15) để sau khi đẩy
    # các đoạn giống mục tham khảo xuống cuối, vẫn còn đủ đoạn nội dung cốt
    # lõi cho generator chọn — quiz không đổi vì QA không quan sát thấy vấn đề
    # tương tự ở đó.
    results = store.search(query_vector, top_k=15, document_ids={doc.id})

    retrieved_chunks = [
        RetrievedChunk(
            text=c.text,
            document_name=c.document_name,
            position_ref=c.position_ref,
            score=score,
            chunk_id=c.chunk_id,
            document_id=c.document_id,
        )
        for c, score in results
    ]
    if not retrieved_chunks:
        raise HTTPException(400, "Không tìm thấy nội dung để sinh flashcard từ tài liệu này.")

    # Hạ ưu tiên (KHÔNG xoá) các đoạn giống khu vực tham khảo/trích dẫn —
    # flashcard nên dạy nội dung cốt lõi trước (BUG-007). sort() ổn định nên
    # thứ tự tương đối trong từng nhóm (theo điểm truy hồi) được giữ nguyên.
    retrieved_chunks = _prioritize_core_content(retrieved_chunks)

    llm_client = get_llm_client()
    items = generate_flashcards(chunks=retrieved_chunks, llm_client=llm_client, num_cards=req.num_cards)
    if not items:
        raise HTTPException(500, "Không sinh được flashcard nào xác minh được từ tài liệu.")

    topic_name = req.topic_name.strip() if req.topic_name and req.topic_name.strip() else os.path.splitext(doc.file_name)[0]
    topic = (
        db.query(Topic)
        .filter(
            Topic.user_id == req.user_id,
            Topic.course_name == doc.course_name,
            Topic.name == topic_name,
        )
        .first()
    )
    if not topic:
        topic = Topic(user_id=req.user_id, name=topic_name, course_name=doc.course_name)
        db.add(topic)
        db.commit()

    fset = FlashcardSet(user_id=req.user_id, document_id=doc.id)
    db.add(fset)
    db.commit()

    for item in items:
        db.add(
            FlashcardItem(
                flashcard_set_id=fset.id,
                topic_id=topic.id,
                front=item.front,
                back=item.back,
                source_document=item.source_document,
                source_position=item.source_position,
            )
        )
    db.commit()

    saved = db.query(FlashcardItem).filter(FlashcardItem.flashcard_set_id == fset.id).all()
    return {
        "flashcard_set_id": fset.id,
        "items": [
            {
                "id": i.id,
                "front": i.front,
                "back": i.back,
                "source_document": i.source_document,
                "source_position": i.source_position,
            }
            for i in saved
        ],
    }


class SaveFlashcardRequest(BaseModel):
    user_id: str
    front: str
    back: str
    source_document: str | None = None
    source_position: str | None = None
    topic_name: str | None = None


@router.post("/save")
def save_from_answer(req: SaveFlashcardRequest, db: Session = Depends(get_db)):
    """Biến một câu trả lời hỏi đáp thành thẻ ôn tập.

    Đây là mắt nối giữa hỏi đáp và vòng ôn tập: trước đây một câu trả lời hay
    chỉ trôi vào lịch sử chat rồi mất, dù nó chính là thứ người học muốn nhớ.
    Thẻ lưu theo đường này vào thẳng hàng đợi ôn tập vì chưa có lượt ôn nào."""
    if not req.front.strip() or not req.back.strip():
        raise HTTPException(400, "Thẻ phải có cả mặt trước và mặt sau.")

    # document_id = NULL đánh dấu bộ "lưu từ câu trả lời" (không gắn tài liệu
    # nào cụ thể) — xem docstring FlashcardSet.document_id (app/models.py).
    fset = (
        db.query(FlashcardSet)
        .filter(
            FlashcardSet.user_id == req.user_id,
            FlashcardSet.document_id.is_(None),
        )
        .first()
    )
    if not fset:
        fset = FlashcardSet(user_id=req.user_id, document_id=None)
        db.add(fset)
        db.commit()

    topic_id = None
    if req.topic_name and req.topic_name.strip():
        name = req.topic_name.strip()
        topic = db.query(Topic).filter(Topic.user_id == req.user_id, Topic.name == name).first()
        if not topic:
            topic = Topic(user_id=req.user_id, name=name)
            db.add(topic)
            db.commit()
        topic_id = topic.id

    item = FlashcardItem(
        flashcard_set_id=fset.id,
        topic_id=topic_id,
        front=req.front.strip(),
        back=req.back.strip(),
        source_document=req.source_document,
        source_position=req.source_position,
    )
    db.add(item)
    db.commit()

    return {
        "id": item.id,
        "front": item.front,
        "back": item.back,
        "source_document": item.source_document,
        "source_position": item.source_position,
    }


@router.get("/due")
def list_due(user_id: str, limit: int = 20, db: Session = Depends(get_db)):
    """Thẻ cần ôn hôm nay — chưa từng ôn hoặc đã tới hạn."""
    items = due_items(db, user_id, limit=limit)
    return {
        "items": [
            {
                "id": item.id,
                "front": item.front,
                "back": item.back,
                "source_document": item.source_document,
                "source_position": item.source_position,
                "interval_days": review.interval_days if review else 0,
                "ease": review.ease if review else DEFAULT_EASE,
            }
            for item, review in items
        ]
    }


class ReviewFlashcardRequest(BaseModel):
    user_id: str
    flashcard_item_id: str
    rating: str  # again | hard | good | easy


# Chỉ ghi ký ức cho hai đầu mút của thang đánh giá: "quên hẳn" và "quá dễ" nói
# lên điều gì đó về người học, còn "hard"/"good" là trạng thái bình thường của
# việc ôn tập và ghi lại chỉ làm nhiễu ký ức.
_MEMORY_EVENT_BY_RATING = {"again": "flashcard_again", "easy": "flashcard_easy"}


@router.post("/review")
def review(req: ReviewFlashcardRequest, db: Session = Depends(get_db)):
    if req.rating not in VALID_RATINGS:
        raise HTTPException(400, f"Mức đánh giá không hợp lệ. Chỉ nhận: {', '.join(VALID_RATINGS)}.")

    item = (
        db.query(FlashcardItem)
        .join(FlashcardSet, FlashcardItem.flashcard_set_id == FlashcardSet.id)
        .filter(FlashcardItem.id == req.flashcard_item_id, FlashcardSet.user_id == req.user_id)
        .first()
    )
    if not item:
        raise HTTPException(404, "Không tìm thấy thẻ này.")

    previous = (
        db.query(FlashcardReview)
        .filter(
            FlashcardReview.user_id == req.user_id,
            FlashcardReview.flashcard_item_id == item.id,
        )
        .order_by(FlashcardReview.reviewed_at.desc())
        .first()
    )

    schedule = schedule_next_review(
        rating=req.rating,
        interval_days=previous.interval_days if previous else 0.0,
        ease=previous.ease if previous else DEFAULT_EASE,
    )

    db.add(
        FlashcardReview(
            user_id=req.user_id,
            flashcard_item_id=item.id,
            rating=req.rating,
            interval_days=schedule.interval_days,
            ease=schedule.ease,
            next_due_at=schedule.next_due_at,
        )
    )
    db.commit()

    event_type = _MEMORY_EVENT_BY_RATING.get(req.rating)
    if event_type:
        verb = "quên" if req.rating == "again" else "thấy quá dễ"
        record_event(
            db,
            user_id=req.user_id,
            event_type=event_type,
            content=f"Khi ôn flashcard đã {verb} thẻ: \"{item.front}\"",
            topic_id=item.topic_id,
            source_ref=item.source_position,
        )

    return {
        "rating": req.rating,
        "interval_days": schedule.interval_days,
        "ease": schedule.ease,
        "next_due_at": schedule.next_due_at.isoformat(),
        "back": item.back,
    }
