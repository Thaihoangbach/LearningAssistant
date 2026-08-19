"""API routes cho Flashcard (TC14) — tái sử dụng pattern app/routers/quiz.py."""

import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.ingestion.embedder import embed_query
from app.llm.flashcard_generator import generate_flashcards
from app.llm.gemini_client import GeminiClient
from app.llm.rag import RetrievedChunk
from app.models import Document, FlashcardItem, FlashcardSet, Topic
from app.vectorstore.faiss_store import UserVectorStore

router = APIRouter(prefix="/flashcard", tags=["flashcard"])


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
    store = UserVectorStore(user_id=req.user_id)
    results = store.search(query_vector, top_k=10, document_ids={doc.id})

    retrieved_chunks = [
        RetrievedChunk(text=c.text, document_name=c.document_name, position_ref=c.position_ref, score=score)
        for c, score in results
    ]
    if not retrieved_chunks:
        raise HTTPException(400, "Không tìm thấy nội dung để sinh flashcard từ tài liệu này.")

    llm_client = GeminiClient()
    items = generate_flashcards(chunks=retrieved_chunks, llm_client=llm_client, num_cards=req.num_cards)
    if not items:
        raise HTTPException(500, "Không sinh được flashcard nào xác minh được từ tài liệu.")

    topic_name = req.topic_name.strip() if req.topic_name and req.topic_name.strip() else os.path.splitext(doc.file_name)[0]
    topic = db.query(Topic).filter(Topic.user_id == req.user_id, Topic.name == topic_name).first()
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
