"""API routes cho F3 (Quiz) + trigger cập nhật mastery cho F4."""

import json
import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.database import get_db
from app.ingestion.embedder import embed_query
from app.ingestion.outline import is_bibliography_like_chunk
from app.llm.client_factory import get_llm_client
from app.llm.quiz_generator import generate_quiz
from app.llm.rag import RetrievedChunk
from app.memory.service import record_event
from app.models import Attempt, Document, MasteryScore, Quiz, QuizItem, Topic
from app.services.generation_mode import VALID_GENERATION_MODES
from app.services.learner_context import build_learner_context
from app.services.mastery import Attempt as MasteryAttempt, compute_mastery
from app.vectorstore.pgvector_store import PgVectorStore

router = APIRouter(prefix="/quiz", tags=["quiz"])


def _prioritize_core_content(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    """Learning Loop Phase 0.5 — cùng vá với BUG-007 bên flashcard
    (app/routers/flashcard.py::_prioritize_core_content): đẩy các đoạn giống
    khu vực tham khảo/trích dẫn xuống CUỐI danh sách (KHÔNG xoá) trước khi đưa
    vào generator, để quiz ưu tiên hỏi nội dung cốt lõi thay vì bịa câu hỏi
    quanh một mục trích dẫn. Tách thành hàm thuần để test được không cần
    Postgres thật (xem tests/test_quiz_prioritization.py)."""
    return sorted(chunks, key=lambda c: is_bibliography_like_chunk(c.text))


class GenerateQuizRequest(BaseModel):
    user_id: str
    document_id: str | None = None
    document_ids: list[str] | None = None  # TC13 — sinh quiz tổng hợp từ nhiều tài liệu/chương
    topic_name: str | None = None
    num_questions: int = 5
    difficulty: str | None = None  # "beginner" | "advanced" | None — xem app/llm/quiz_generator.py
    # "learn" | "review" | "exam" | "weak_topics" | None — Learning Loop Phase 3,
    # xem app/services/generation_mode.py.
    generation_mode: str | None = None


@router.post("/generate")
def generate(req: GenerateQuizRequest, db: Session = Depends(get_db)):
    requested_ids = req.document_ids or ([req.document_id] if req.document_id else [])
    if not requested_ids:
        raise HTTPException(400, "Cần cung cấp document_id hoặc document_ids.")
    if req.generation_mode is not None and req.generation_mode not in VALID_GENERATION_MODES:
        raise HTTPException(400, f"Chế độ sinh không hợp lệ. Chỉ nhận: {', '.join(VALID_GENERATION_MODES)}.")

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
    store = PgVectorStore(db=db, user_id=req.user_id)
    retrieved_chunks: list[RetrievedChunk] = []
    for doc in docs:
        query_vector = embed_query(doc.file_name)
        results = store.search(query_vector, top_k=10, document_ids={doc.id})
        retrieved_chunks.extend(
            RetrievedChunk(
                text=c.text,
                document_name=c.document_name,
                position_ref=c.position_ref,
                score=score,
                chunk_id=c.chunk_id,
                document_id=c.document_id,
            )
            for c, score in results
        )
    if not retrieved_chunks:
        raise HTTPException(400, "Không tìm thấy nội dung để sinh quiz từ (các) tài liệu này.")

    # Hạ ưu tiên (KHÔNG xoá) các đoạn giống khu vực tham khảo/trích dẫn, cùng
    # vá với BUG-007 bên flashcard — quiz nên hỏi nội dung cốt lõi trước.
    # sort() ổn định nên thứ tự tương đối trong từng nhóm (theo điểm truy hồi)
    # được giữ nguyên.
    retrieved_chunks = _prioritize_core_content(retrieved_chunks)

    # KHÔNG truyền `query` — sinh quiz không cần truy hồi ký ức theo câu hỏi,
    # tránh tốn một lượt embed vô ích.
    learner = build_learner_context(db, req.user_id, requested_level=req.difficulty)
    effective_difficulty = learner.effective_level

    llm_client = get_llm_client()
    items = generate_quiz(
        chunks=retrieved_chunks,
        llm_client=llm_client,
        num_questions=req.num_questions,
        difficulty=effective_difficulty,
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

    topic = (
        db.query(Topic)
        .filter(
            Topic.user_id == req.user_id,
            Topic.course_name == docs[0].course_name,
            Topic.name == topic_name,
        )
        .first()
    )
    if not topic:
        topic = Topic(user_id=req.user_id, name=topic_name, course_name=docs[0].course_name)
        db.add(topic)
        db.commit()

    # Quiz.document_id giữ 1 FK (không đổi schema) — với quiz đa tài liệu, lưu tài liệu
    # đầu tiên làm tham chiếu chính; nguồn thật của TỪNG câu hỏi vẫn đúng qua
    # QuizItem.source_document/source_position (lấy từ chunk tương ứng).
    quiz = Quiz(user_id=req.user_id, document_id=docs[0].id, generation_mode=req.generation_mode)
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
                difficulty=effective_difficulty,
                content_type=item.content_type,
            )
        )
    db.commit()

    quiz_items = db.query(QuizItem).filter(QuizItem.quiz_id == quiz.id).all()
    # BUG-003: trước đây trả 200 kèm items ngắn hơn num_questions yêu cầu mà
    # không báo gì — người dùng tưởng đã tạo đủ. `generated`/`requested`/
    # `partial` cho frontend biết CHÍNH XÁC có thiếu hay không, thay vì suy
    # đoán từ độ dài mảng items (dễ quên kiểm tra).
    return {
        "quiz_id": quiz.id,
        "requested": req.num_questions,
        "generated": len(quiz_items),
        "partial": len(quiz_items) < req.num_questions,
        "items": [
            {
                "id": qi.id,
                "question": qi.question,
                "options": json.loads(qi.options),
                "content_type": qi.content_type,
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
    # Join sang Quiz để xác nhận quiz_item_id THUỘC VỀ req.user_id — trước đây
    # tra thẳng theo id, không lọc user_id nào (khác review() ở flashcard.py,
    # vốn lọc đúng theo FlashcardSet.user_id cho cùng một việc). Không có kiểm
    # tra này, một request nộp bài với quiz_item_id của người khác vẫn ghi
    # được Attempt gắn cho req.user_id — đầu độc mastery/ký ức của tài khoản
    # gửi request bằng câu hỏi không phải của họ.
    quiz_item = (
        db.query(QuizItem)
        .join(Quiz, QuizItem.quiz_id == Quiz.id)
        .filter(QuizItem.id == req.quiz_item_id, Quiz.user_id == req.user_id)
        .first()
    )
    if not quiz_item:
        raise HTTPException(404, "Không tìm thấy câu hỏi.")

    is_correct = req.selected_answer.strip() == quiz_item.correct_answer.strip()

    attempt = Attempt(
        user_id=req.user_id,
        quiz_item_id=quiz_item.id,
        topic_id=quiz_item.topic_id,
        is_correct=is_correct,
        selected_answer=req.selected_answer,
    )
    db.add(attempt)
    db.commit()

    # Cập nhật mastery ngay (F4) nếu câu hỏi này gắn với một Topic
    new_score = None
    if quiz_item.topic_id:
        # Join sang QuizItem để lấy độ khó — mastery cân trọng số theo độ khó
        # (app/services/mastery.py), nếu chỉ đọc Attempt thì mọi lượt bị coi
        # ngang nhau.
        history = (
            db.query(Attempt, QuizItem)
            .join(QuizItem, Attempt.quiz_item_id == QuizItem.id)
            .filter(Attempt.user_id == req.user_id, Attempt.topic_id == quiz_item.topic_id)
            .all()
        )
        mastery_attempts = [
            MasteryAttempt(
                is_correct=a.is_correct,
                attempted_at=a.attempted_at,
                difficulty=item.difficulty,
            )
            for a, item in history
        ]
        new_score = compute_mastery(mastery_attempts)

        if new_score is not None:
            # BUG-3 (đã vá) — 2 lượt nộp bài GẦN NHAU cho cùng (user_id,
            # topic_id) từng có thể cùng đọc "chưa có record" rồi cùng
            # INSERT, sinh 2 dòng MasteryScore trùng. Trước vá tạm bằng khoá
            # ứng dụng (app/concurrency.py); giờ sửa TẬN GỐC bằng
            # UniqueConstraint(user_id, topic_id) ở models.py + upsert
            # NGUYÊN TỬ của Postgres (INSERT ... ON CONFLICT DO UPDATE) — dù
            # 2 transaction thật sự chạy đồng thời, DB tự đảm bảo chỉ một
            # dòng tồn tại, không cần khoá ở tầng ứng dụng.
            upsert = insert(MasteryScore).values(
                user_id=req.user_id, topic_id=quiz_item.topic_id, score=new_score
            )
            upsert = upsert.on_conflict_do_update(
                constraint="uq_mastery_scores_user_topic",
                set_={"score": upsert.excluded.score},
            )
            db.execute(upsert)
            db.commit()

    # Ký ức episodic — làm sai một câu quiz là tín hiệu mạnh nhất về chỗ người
    # học đang hổng, nên importance của "quiz_wrong" cao nhất bảng
    # (app/memory/scoring.py). Nội dung dựng bằng template, không gọi LLM.
    question_preview = quiz_item.question.strip()
    if len(question_preview) > 120:
        question_preview = question_preview[:120].rstrip() + "…"

    record_event(
        db,
        user_id=req.user_id,
        event_type="quiz_right" if is_correct else "quiz_wrong",
        content=(
            f"Trả lời {'đúng' if is_correct else 'sai'} câu quiz: \"{question_preview}\""
            + (f" (đáp án đúng: {quiz_item.correct_answer})" if not is_correct else "")
        ),
        topic_id=quiz_item.topic_id,
        source_ref=quiz_item.source_position,
    )

    return {
        "is_correct": is_correct,
        "correct_answer": quiz_item.correct_answer,
        "explanation": quiz_item.explanation,
        "updated_mastery_score": new_score,
        # Learning Loop Phase 2a — màn tổng kết cần trích được nguồn của câu
        # sai khi đưa vào Flashcard ("Thêm vào Flashcard") hoặc mở hỏi AI kèm
        # ngữ cảnh ("Hỏi AI"), cùng 2 trường QuizItem đã lưu sẵn lúc sinh quiz.
        "source_document": quiz_item.source_document,
        "source_position": quiz_item.source_position,
    }
