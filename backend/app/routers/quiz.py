"""API routes cho F3 (Quiz) + trigger cập nhật mastery cho F4.

CHƯA CHẠY ĐƯỢC TRONG SANDBOX NÀY: cần `pip install fastapi sqlalchemy`.
"""

import json
import os

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
    document_id: str | None = None
    document_ids: list[str] | None = None  # TC13 — sinh quiz tổng hợp từ nhiều tài liệu/chương
    topic_name: str | None = None
    num_questions: int = 5
    difficulty: str | None = None  # "beginner" | "advanced" | None — xem app/llm/quiz_generator.py


@router.post("/generate")
def generate(req: GenerateQuizRequest, db: Session = Depends(get_db)):
    requested_ids = req.document_ids or ([req.document_id] if req.document_id else [])
    if not requested_ids:
        raise HTTPException(400, "Cần cung cấp document_id hoặc document_ids.")

    docs = (
        db.query(Document)
        .filter(Document.id.in_(requested_ids), Document.user_id == req.user_id, Document.status == "sẵn sàng")
        .all()
    )
    if not docs:
        raise HTTPException(400, "Tài liệu không tồn tại hoặc chưa sẵn sàng.")

    # Lấy chunk từ TỪNG tài liệu bằng một câu hỏi tổng quát làm query truy hồi, để quiz
    # tổng hợp (TC13) không bị dồn hết câu hỏi vào một tài liệu/chương duy nhất.
    # Đơn giản hoá cho MVP: retrieval theo tên tài liệu, chưa tối ưu lấy "đại diện" nội dung.
    store = UserVectorStore(user_id=req.user_id)
    retrieved_chunks: list[RetrievedChunk] = []
    for doc in docs:
        query_vector = embed_query(doc.file_name)
        results = store.search(query_vector, top_k=10, document_ids={doc.id})
        retrieved_chunks.extend(
            RetrievedChunk(text=c.text, document_name=c.document_name, position_ref=c.position_ref, score=score)
            for c, score in results
        )
    if not retrieved_chunks:
        raise HTTPException(400, "Không tìm thấy nội dung để sinh quiz từ (các) tài liệu này.")

    llm_client = GeminiClient()
    items = generate_quiz(
        chunks=retrieved_chunks,
        llm_client=llm_client,
        num_questions=req.num_questions,
        difficulty=req.difficulty,
    )
    if not items:
        raise HTTPException(500, "Không sinh được câu hỏi nào xác minh được từ tài liệu.")

    # Chủ đề luôn được gán (fallback về tên tài liệu/môn học nếu người dùng bỏ trống) để
    # mọi quiz đều tính được vào mastery (F4) — trước đây bỏ trống thì mastery không cập
    # nhật mà không hề báo cho người dùng biết.
    if req.topic_name and req.topic_name.strip():
        topic_name = req.topic_name.strip()
    elif len(docs) == 1:
        topic_name = os.path.splitext(docs[0].file_name)[0]
    else:
        topic_name = docs[0].course_name or "Ôn tập tổng hợp"

    topic = db.query(Topic).filter(Topic.user_id == req.user_id, Topic.name == topic_name).first()
    if not topic:
        topic = Topic(user_id=req.user_id, name=topic_name, course_name=docs[0].course_name)
        db.add(topic)
        db.commit()

    # Quiz.document_id giữ 1 FK (không đổi schema) — với quiz đa tài liệu, lưu tài liệu
    # đầu tiên làm tham chiếu chính; nguồn thật của TỪNG câu hỏi vẫn đúng qua
    # QuizItem.source_document/source_position (lấy từ chunk tương ứng).
    quiz = Quiz(user_id=req.user_id, document_id=docs[0].id)
    db.add(quiz)
    db.commit()

    for item in items:
        db.add(
            QuizItem(
                quiz_id=quiz.id,
                topic_id=topic.id,
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
