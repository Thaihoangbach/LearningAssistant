"""API routes cho F3 (Quiz) + trigger cập nhật mastery cho F4.

CHƯA CHẠY ĐƯỢC TRONG SANDBOX NÀY: cần `pip install fastapi sqlalchemy`.
"""

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.ingestion.embedder import embed_query
from app.llm.gemini_client import GeminiClient
from app.llm.quiz_generator import generate_quiz
from app.llm.rag import RetrievedChunk
from app.mastery import Attempt as MasteryAttempt, compute_mastery
from app.models import Attempt, Document, MasteryScore, Quiz, QuizItem, Topic
from app.vectorstore.faiss_store import UserVectorStore

router = APIRouter(prefix="/quiz", tags=["quiz"])


class GenerateQuizRequest(BaseModel):
    user_id: str
    document_id: str
    topic_name: str | None = None
    num_questions: int = 5


@router.post("/generate")
def generate(req: GenerateQuizRequest, db: Session = Depends(get_db)):
    doc = (
        db.query(Document)
        .filter(Document.id == req.document_id, Document.user_id == req.user_id, Document.status == "sẵn sàng")
        .first()
    )
    if not doc:
        raise HTTPException(400, "Tài liệu không tồn tại hoặc chưa sẵn sàng.")

    # Lấy toàn bộ chunk thuộc tài liệu này bằng một câu hỏi tổng quát làm query truy hồi.
    # Đơn giản hoá cho MVP: retrieval theo tên tài liệu, chưa tối ưu lấy "đại diện" nội dung.
    query_vector = embed_query(doc.file_name)
    store = UserVectorStore(user_id=req.user_id)
    results = store.search(query_vector, top_k=10, document_ids={doc.id})

    retrieved_chunks = [
        RetrievedChunk(text=c.text, document_name=c.document_name, position_ref=c.position_ref, score=score)
        for c, score in results
    ]
    if not retrieved_chunks:
        raise HTTPException(400, "Không tìm thấy nội dung để sinh quiz từ tài liệu này.")

    llm_client = GeminiClient()
    items = generate_quiz(chunks=retrieved_chunks, llm_client=llm_client, num_questions=req.num_questions)
    if not items:
        raise HTTPException(500, "Không sinh được câu hỏi nào xác minh được từ tài liệu.")

    topic = None
    if req.topic_name:
        topic = db.query(Topic).filter(Topic.user_id == req.user_id, Topic.name == req.topic_name).first()
        if not topic:
            topic = Topic(user_id=req.user_id, name=req.topic_name, course_name=doc.course_name)
            db.add(topic)
            db.commit()

    quiz = Quiz(user_id=req.user_id, document_id=doc.id)
    db.add(quiz)
    db.commit()

    for item in items:
        db.add(
            QuizItem(
                quiz_id=quiz.id,
                topic_id=topic.id if topic else None,
                question=item.question,
                options=json.dumps(item.options, ensure_ascii=False),
                correct_answer=item.correct_answer,
                explanation=item.explanation,
                source_document=item.source_document,
                source_position=item.source_position,
            )
        )
    db.commit()

    quiz_items = db.query(QuizItem).filter(QuizItem.quiz_id == quiz.id).all()
    return {
        "quiz_id": quiz.id,
        "items": [
            {
                "id": qi.id,
                "question": qi.question,
                "options": json.loads(qi.options),
                # KHÔNG trả correct_answer/explanation ở bước sinh quiz - chỉ trả sau khi nộp bài (/submit)
            }
            for qi in quiz_items
        ],
    }


class SubmitAttemptRequest(BaseModel):
    user_id: str
    quiz_item_id: str
    selected_answer: str


@router.post("/submit")
def submit_attempt(req: SubmitAttemptRequest, db: Session = Depends(get_db)):
    quiz_item = db.query(QuizItem).filter(QuizItem.id == req.quiz_item_id).first()
    if not quiz_item:
        raise HTTPException(404, "Không tìm thấy câu hỏi.")

    is_correct = req.selected_answer.strip() == quiz_item.correct_answer.strip()

    attempt = Attempt(
        user_id=req.user_id,
        quiz_item_id=quiz_item.id,
        topic_id=quiz_item.topic_id,
        is_correct=is_correct,
    )
    db.add(attempt)
    db.commit()

    # Cập nhật mastery ngay (F4) nếu câu hỏi này gắn với một Topic
    new_score = None
    if quiz_item.topic_id:
        history = (
            db.query(Attempt)
            .filter(Attempt.user_id == req.user_id, Attempt.topic_id == quiz_item.topic_id)
            .all()
        )
        mastery_attempts = [MasteryAttempt(is_correct=a.is_correct, attempted_at=a.attempted_at) for a in history]
        new_score = compute_mastery(mastery_attempts)

        if new_score is not None:
            record = (
                db.query(MasteryScore)
                .filter(MasteryScore.user_id == req.user_id, MasteryScore.topic_id == quiz_item.topic_id)
                .first()
            )
            if record:
                record.score = new_score
            else:
                db.add(MasteryScore(user_id=req.user_id, topic_id=quiz_item.topic_id, score=new_score))
            db.commit()

    return {
        "is_correct": is_correct,
        "correct_answer": quiz_item.correct_answer,
        "explanation": quiz_item.explanation,
        "updated_mastery_score": new_score,
    }
