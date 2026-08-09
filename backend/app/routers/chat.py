"""API routes cho F2 — hỏi đáp có căn cứ dựa trên tài liệu (RAG).

CHƯA CHẠY ĐƯỢC TRONG SANDBOX NÀY: cần `pip install fastapi`, cộng toàn bộ
dependency của embedder.py, faiss_store.py, gemini_client.py.
"""

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.ingestion.embedder import embed_query
from app.llm.gemini_client import GeminiClient
from app.llm.rag import RetrievedChunk, answer_question
from app.models import Conversation, Document, Message
from app.vectorstore.faiss_store import UserVectorStore

router = APIRouter(prefix="/chat", tags=["chat"])


class AskRequest(BaseModel):
    user_id: str
    question: str
    course_name: str | None = None
    conversation_id: str | None = None
    top_k: int = 5
    min_score: float = 0.3


@router.post("/ask")
def ask(req: AskRequest, db: Session = Depends(get_db)):
    # Chỉ tìm trong tài liệu "sẵn sàng" thuộc quyền của user_id — thực thi AC F2/F5
    ready_docs = (
        db.query(Document)
        .filter(Document.user_id == req.user_id, Document.status == "sẵn sàng")
        .all()
    )
    if req.course_name:
        ready_docs = [d for d in ready_docs if d.course_name == req.course_name]

    if not ready_docs:
        raise HTTPException(400, "Chưa có tài liệu nào sẵn sàng để hỏi đáp.")

    document_ids = {d.id for d in ready_docs}

    query_vector = embed_query(req.question)
    store = UserVectorStore(user_id=req.user_id)
    results = store.search(query_vector, top_k=req.top_k, document_ids=document_ids)

    retrieved_chunks = [
        RetrievedChunk(
            text=chunk.text,
            document_name=chunk.document_name,
            position_ref=chunk.position_ref,
            score=score,
        )
        for chunk, score in results
    ]

    llm_client = GeminiClient()
    result = answer_question(
        question=req.question,
        retrieved_chunks=retrieved_chunks,
        llm_client=llm_client,
        min_score=req.min_score,
    )

    conversation_id = req.conversation_id
    if not conversation_id:
        convo = Conversation(user_id=req.user_id, course_name=req.course_name)
        db.add(convo)
        db.commit()
        conversation_id = convo.id

    db.add(Message(conversation_id=conversation_id, role="user", content=req.question))
    db.add(
        Message(
            conversation_id=conversation_id,
            role="assistant",
            content=result.answer,
            is_grounded=result.is_grounded,
            cited_sources=json.dumps(
                [{"document_name": s.document_name, "position_ref": s.position_ref} for s in result.sources],
                ensure_ascii=False,
            ),
        )
    )
    db.commit()

    return {
        "conversation_id": conversation_id,
        "answer": result.answer,
        "is_grounded": result.is_grounded,
        "sources": [
            {"document_name": s.document_name, "position_ref": s.position_ref}
            for s in result.sources
        ],
    }


PREVIEW_MAX_LENGTH = 80


@router.get("/conversations")
def list_conversations(user_id: str, db: Session = Depends(get_db)):
    conversations = (
        db.query(Conversation)
        .filter(Conversation.user_id == user_id)
        .order_by(Conversation.created_at.desc())
        .all()
    )

    result = []
    for convo in conversations:
        first_message = (
            db.query(Message)
            .filter(Message.conversation_id == convo.id, Message.role == "user")
            .order_by(Message.created_at.asc())
            .first()
        )
        preview = first_message.content if first_message else ""
        if len(preview) > PREVIEW_MAX_LENGTH:
            preview = preview[:PREVIEW_MAX_LENGTH].rstrip() + "…"

        result.append(
            {
                "id": convo.id,
                "course_name": convo.course_name,
                "created_at": convo.created_at.isoformat(),
                "preview": preview,
            }
        )
    return result


@router.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: str, user_id: str, db: Session = Depends(get_db)):
    convo = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id, Conversation.user_id == user_id)
        .first()
    )
    if not convo:
        raise HTTPException(404, "Không tìm thấy cuộc hội thoại.")

    messages = (
        db.query(Message)
        .filter(Message.conversation_id == convo.id)
        .order_by(Message.created_at.asc())
        .all()
    )

    return {
        "id": convo.id,
        "course_name": convo.course_name,
        "created_at": convo.created_at.isoformat(),
        "messages": [
            {
                "role": m.role,
                "content": m.content,
                "is_grounded": m.is_grounded,
                "sources": json.loads(m.cited_sources) if m.cited_sources else [],
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ],
    }
