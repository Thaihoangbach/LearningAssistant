"""API routes cho F2 — hỏi đáp có căn cứ dựa trên tài liệu (RAG).

CHƯA CHẠY ĐƯỢC TRONG SANDBOX NÀY: cần `pip install fastapi`, cộng toàn bộ
dependency của embedder.py, faiss_store.py, gemini_client.py.
"""

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.learner_context import build_learner_context
from app.llm.gemini_client import GeminiClient
from app.llm.guardrail import check_question
from app.llm.rag import _SIMPLIFY_REQUEST_RE, AnswerResult, ConversationTurn, answer_question
from app.llm.recommendation import TopicMastery, build_recommendation, is_recommendation_request
from app.memory.service import record_event
from app.models import Conversation, Document, MasteryScore, Message, Topic
from app.retrieval.pipeline import retrieve_chunks

router = APIRouter(prefix="/chat", tags=["chat"])

MAX_HISTORY_TURNS = 3

# Golden Set (eval/report.md, mục 14) đo được Config A (dense-only, lọc lỏng
# hơn) đạt Personalization 0.67 trong khi Config B (hybrid+reranker, lọc gắt
# hơn) chỉ đạt 0.13 — nguyên nhân chỉ ra là retrieval lọc quá gắt khiến
# generator có ÍT nguyên liệu hơn để viết một câu trả lời "advanced" đủ sâu.
# Khác với Config A, ở đây KHÔNG nới lỏng bộ lọc bằng cách bỏ rerank (sẽ mất
# luôn phần cải thiện Citation Accuracy +0.45 mà hybrid+reranker mang lại) —
# thay vào đó chỉ tăng top_k khi có level, để rerank vẫn lọc chất lượng như
# cũ nhưng giữ lại nhiều đoạn liên quan hơn cho generator có đủ chất liệu
# phân biệt độ sâu beginner/advanced.
LEVEL_TOP_K_BOOST = 3


def _load_conversation_history(db: Session, conversation_id: str) -> list[ConversationTurn]:
    """Lấy N lượt hỏi-đáp gần nhất của hội thoại, dùng để giải ngữ cảnh câu hỏi
    tiếp nối (vd: "nó" ám chỉ chủ đề đã hỏi trước đó) — xem app/llm/rag.py."""
    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .all()
    )
    turns: list[ConversationTurn] = []
    pending_question: str | None = None
    for m in messages:
        if m.role == "user":
            pending_question = m.content
        elif m.role == "assistant" and pending_question is not None:
            turns.append(ConversationTurn(question=pending_question, answer=m.content))
            pending_question = None
    return turns[-MAX_HISTORY_TURNS:]


def _build_recommendation_result(db: Session, user_id: str, course_name: str | None) -> AnswerResult:
    """TC10/TC24 — gợi ý chủ đề nên học tiếp theo, đọc lại MasteryScore đã có
    sẵn (F4). Không cần tài liệu "sẵn sàng" nào, không gọi LLM."""
    query = (
        db.query(MasteryScore, Topic)
        .join(Topic, MasteryScore.topic_id == Topic.id)
        .filter(MasteryScore.user_id == user_id)
    )
    if course_name:
        query = query.filter(Topic.course_name == course_name)

    topics = [TopicMastery(topic_name=topic.name, score=score.score) for score, topic in query.all()]
    return AnswerResult(answer=build_recommendation(topics), is_grounded=True, sources=[])


class AskRequest(BaseModel):
    user_id: str
    question: str
    course_name: str | None = None
    conversation_id: str | None = None
    top_k: int = 5
    # Xem giải thích ngưỡng thấp này ở app/llm/rag.py::answer_question
    min_score: float = 0.02
    level: str | None = None  # "beginner" | "advanced" | None — xem app/llm/rag.py


# Nội dung ký ức dựng bằng template cố định — KHÔNG gọi LLM để viết, đúng
# nguyên tắc chi phí ở PRD §6.
QUESTION_PREVIEW_MAX = 120


def _classify_question_event(question: str, result: AnswerResult) -> tuple[str, str]:
    """Quyết định loại sự kiện và câu mô tả sẽ lưu vào ký ức episodic."""
    preview = question.strip()
    if len(preview) > QUESTION_PREVIEW_MAX:
        preview = preview[:QUESTION_PREVIEW_MAX].rstrip() + "…"

    if not result.is_grounded:
        return "abstention", f"Đã hỏi \"{preview}\" nhưng hệ thống không tìm được căn cứ trong tài liệu"
    if _SIMPLIFY_REQUEST_RE.search(question):
        return "concept_confused", f"Từng nói chưa hiểu và xin giải thích đơn giản hơn khi hỏi \"{preview}\""
    return "question_asked", f"Đã hỏi \"{preview}\""


@router.post("/ask")
def ask(req: AskRequest, db: Session = Depends(get_db)):
    is_recommendation = is_recommendation_request(req.question)
    guardrail_result = None

    if not is_recommendation:
        # Chỉ tìm trong tài liệu "sẵn sàng", phiên bản mới nhất, thuộc quyền
        # user_id — thực thi AC F2/F5 + ưu tiên bản mới khi tài liệu có version.
        ready_docs = (
            db.query(Document)
            .filter(Document.user_id == req.user_id, Document.status == "sẵn sàng", Document.is_latest == True)
            .all()
        )
        if req.course_name:
            ready_docs = [d for d in ready_docs if d.course_name == req.course_name]

        if not ready_docs:
            raise HTTPException(400, "Chưa có tài liệu nào sẵn sàng để hỏi đáp.")

        document_ids = {d.id for d in ready_docs}

    conversation_id = req.conversation_id
    if not conversation_id:
        convo = Conversation(user_id=req.user_id, course_name=req.course_name)
        db.add(convo)
        db.commit()
        conversation_id = convo.id

    history = _load_conversation_history(db, conversation_id)

    if is_recommendation:
        result = _build_recommendation_result(db, req.user_id, req.course_name)
    else:
        llm_client = GeminiClient()

        # Guardrail (F2 an toàn đầu vào) — chặn prompt injection/jailbreak, yêu cầu
        # làm bài hộ, và câu hỏi ngoài phạm vi học tập TRƯỚC khi tốn lượt gọi
        # generator+verifier.
        guardrail_result = check_question(req.question, llm_client=llm_client)
        if guardrail_result.blocked:
            result = AnswerResult(answer=guardrail_result.message, is_grounded=False, sources=[])
        else:
            learner = build_learner_context(
                db, req.user_id, requested_level=req.level, query=req.question
            )

            effective_top_k = req.top_k + LEVEL_TOP_K_BOOST if learner.effective_level else req.top_k
            retrieved_chunks = retrieve_chunks(
                user_id=req.user_id,
                query=req.question,
                top_k=effective_top_k,
                document_ids=document_ids,
            )

            result = answer_question(
                question=req.question,
                retrieved_chunks=retrieved_chunks,
                llm_client=llm_client,
                min_score=req.min_score,
                conversation_history=history,
                level=learner.effective_level,
                learning_goal=learner.learning_goal,
                recalled_events=learner.recalled_events,
            )

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

    # Chỉ ghi ký ức cho câu hỏi thật — không ghi cho nhánh gợi ý học tiếp (đọc
    # lại dữ liệu có sẵn, không phải một sự kiện học tập mới) và không ghi cho
    # câu bị guardrail chặn (không phản ánh điều gì về trình độ người học).
    if not is_recommendation and guardrail_result is not None and not guardrail_result.blocked:
        event_type, content = _classify_question_event(req.question, result)
        record_event(db, user_id=req.user_id, event_type=event_type, content=content)

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
