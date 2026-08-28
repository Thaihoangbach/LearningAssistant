"""API routes cho F2 — hỏi đáp có căn cứ dựa trên tài liệu (RAG).

CHƯA CHẠY ĐƯỢC TRONG SANDBOX NÀY: cần `pip install fastapi`, cộng toàn bộ
dependency của embedder.py, faiss_store.py, gemini_client.py.
"""

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.capability_router import detect_capability
from app.citation import _content_words, supporting_sentences
from app.database import get_db
from app.flashcard_service import count_due
from app.learner_context import build_learner_context
from app.llm.gemini_client import GeminiClient
from app.llm.guardrail import check_question
from app.llm.rag import _SIMPLIFY_REQUEST_RE, AnswerResult, ConversationTurn
from app.llm.recommendation import TopicMastery, build_recommendation
from app.study_planner import TopicPriority, generate_plan
from app.memory.service import record_event
from app.models import (
    Conversation,
    Document,
    DocumentTopic,
    MasteryScore,
    MemoryEvent,
    Message,
    Topic,
)
from app.qa_pipeline import answer_with_fallback
from app.retrieval.pipeline import retrieve_chunks
from app.retrieval.query_context import build_retrieval_query

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

# Số chủ đề gợi ý kèm theo khi hệ thống từ chối trả lời.
MAX_SUGGESTED_TOPICS = 4


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


# Loại ký ức dùng làm LÝ DO một chủ đề bị coi là yếu — chỉ lấy các sự kiện
# phản ánh việc không nhớ/không làm được, không lấy sự kiện hỏi đáp thường.
_WEAKNESS_EVENT_TYPES = ("quiz_wrong", "flashcard_again")
MAX_EVIDENCE_PER_TOPIC = 3


def _build_recommendation_result(db: Session, user_id: str, course_name: str | None) -> AnswerResult:
    """TC10/TC24 — gợi ý chủ đề nên học tiếp theo, đọc lại MasteryScore đã có
    sẵn (F4) cộng ký ức episodic (giai đoạn A) để nói được VÌ SAO chủ đề đó
    yếu. Vẫn KHÔNG gọi LLM: toàn bộ là đọc lại dữ liệu đã tính."""
    query = (
        db.query(MasteryScore, Topic)
        .join(Topic, MasteryScore.topic_id == Topic.id)
        .filter(MasteryScore.user_id == user_id)
    )
    if course_name:
        query = query.filter(Topic.course_name == course_name)

    rows = query.all()
    topics = [TopicMastery(topic_name=topic.name, score=score.score) for score, topic in rows]

    topic_name_by_id = {topic.id: topic.name for _, topic in rows}
    evidence_by_topic: dict[str, list[str]] = {}
    if topic_name_by_id:
        events = (
            db.query(MemoryEvent)
            .filter(
                MemoryEvent.user_id == user_id,
                MemoryEvent.topic_id.in_(list(topic_name_by_id.keys())),
                MemoryEvent.event_type.in_(_WEAKNESS_EVENT_TYPES),
            )
            .order_by(MemoryEvent.created_at.desc())
            .all()
        )
        for event in events:
            name = topic_name_by_id.get(event.topic_id)
            if not name:
                continue
            bucket = evidence_by_topic.setdefault(name, [])
            if len(bucket) < MAX_EVIDENCE_PER_TOPIC:
                bucket.append(event.content)

    answer = build_recommendation(
        topics,
        evidence_by_topic=evidence_by_topic,
        due_flashcards=count_due(db, user_id),
    )
    return AnswerResult(answer=answer, is_grounded=True, sources=[])


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


def _build_study_plan_result(db: Session, user_id: str, course_name: str | None, days: int) -> AnswerResult:
    """Lập kế hoạch ôn tập ngay trong hội thoại. Trước đây năng lực này chỉ gọi
    được qua endpoint riêng, nên hỏi "còn 5 ngày nữa thi, ôn thế nào?" trong
    chat rơi vào nhánh hỏi đáp tài liệu và không bao giờ trả lời được."""
    topics_query = db.query(Topic).filter(Topic.user_id == user_id)
    if course_name:
        topics_query = topics_query.filter(Topic.course_name == course_name)
    topics = topics_query.all()

    if not topics:
        return AnswerResult(
            answer=(
                "Chưa có chủ đề nào để chia lịch. Hãy tải tài liệu lên — hệ thống sẽ tự rút "
                "dàn ý chủ đề và lập kế hoạch được ngay."
            ),
            is_grounded=True,
            sources=[],
        )

    scores_by_topic_id = {
        s.topic_id: s.score
        for s in db.query(MasteryScore).filter(MasteryScore.user_id == user_id).all()
    }
    plan = generate_plan(
        [TopicPriority(topic_name=t.name, score=scores_by_topic_id.get(t.id)) for t in topics],
        days=days,
    )

    lines = [f"Kế hoạch ôn tập trong {days} ngày, ưu tiên chủ đề yếu và chưa học:"]
    for day in plan:
        lines.append(f"Ngày {day.day}: {', '.join(day.topics) if day.topics else 'ôn tự do'}")
    return AnswerResult(answer="\n".join(lines), is_grounded=True, sources=[])


def _build_flashcard_due_result(db: Session, user_id: str) -> AnswerResult:
    due = count_due(db, user_id)
    if due == 0:
        answer = "Hiện không có thẻ flashcard nào đến hạn ôn. Bạn đang theo kịp lịch."
    else:
        answer = (
            f"Bạn đang có {due} thẻ flashcard đến hạn ôn. Vào mục Flashcard để ôn ngay — "
            "ôn đúng lúc đến hạn là cách nhớ lâu nhất."
        )
    return AnswerResult(answer=answer, is_grounded=True, sources=[])


@router.post("/ask")
def ask(req: AskRequest, db: Session = Depends(get_db)):
    # Điều phối bằng bảng đăng ký năng lực (app/capability_router.py) thay vì
    # chuỗi if/else. Không khớp năng lực nào thì rơi về hỏi đáp có căn cứ —
    # đường DUY NHẤT bắt buộc qua generator + verifier.
    capability = detect_capability(req.question)
    guardrail_result = None
    qa_result = None

    if capability is None:
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

    if capability is not None:
        # Các năng lực này chỉ đọc lại dữ liệu đã tính sẵn (mastery, kế hoạch,
        # lịch ôn) nên không có gì để bịa và không cần qua verifier.
        if capability.name == "study_plan":
            result = _build_study_plan_result(
                db, req.user_id, req.course_name, capability.params["days"]
            )
        elif capability.name == "flashcard_due":
            result = _build_flashcard_due_result(db, req.user_id)
        else:
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

            def _retrieve(query: str, top_k: int, mode: str):
                return retrieve_chunks(
                    user_id=req.user_id,
                    query=query,
                    top_k=top_k,
                    document_ids=document_ids,
                    mode=mode,
                )

            # Câu hỏi tiếp nối ("tại sao nó tốt hơn?") không có đủ từ nội dung
            # để truy hồi; bổ sung từ khoá của các lượt trước vào truy vấn.
            retrieval_query = build_retrieval_query(req.question, history)

            def _suggest_topics(question: str) -> list[str]:
                """Chủ đề tài liệu THỰC SỰ có, gần câu hỏi nhất — để lời từ chối
                không phải ngõ cụt. Xếp hạng bằng độ trùng từ nội dung nên
                không tốn lượt gọi mô hình nào."""
                rows = (
                    db.query(DocumentTopic)
                    .filter(
                        DocumentTopic.user_id == req.user_id,
                        DocumentTopic.document_id.in_(document_ids),
                    )
                    .all()
                )
                if not rows:
                    return []

                question_words = _content_words(question)
                scored = sorted(
                    rows,
                    key=lambda r: len(_content_words(r.title) & question_words),
                    reverse=True,
                )
                return [r.title for r in scored[:MAX_SUGGESTED_TOPICS]]

            qa_result = answer_with_fallback(
                question=req.question,
                retrieval_query=retrieval_query,
                llm_client=llm_client,
                retrieve_fn=_retrieve,
                suggest_topics_fn=_suggest_topics,
                searched_documents=[{"id": d.id, "file_name": d.file_name} for d in ready_docs],
                top_k=effective_top_k,
                min_score=req.min_score,
                conversation_history=history,
                level=learner.effective_level,
                learning_goal=learner.learning_goal,
                recalled_events=learner.recalled_events,
            )
            result = AnswerResult(
                answer=qa_result.answer,
                is_grounded=qa_result.is_grounded,
                sources=qa_result.sources,
            )

    db.add(Message(conversation_id=conversation_id, role="user", content=req.question))
    db.add(
        Message(
            conversation_id=conversation_id,
            role="assistant",
            content=result.answer,
            is_grounded=result.is_grounded,
            # Lưu ĐỦ trường để mở lại hội thoại cũ vẫn bấm được vào citation và
            # thấy nguyên văn đoạn trích — nếu chỉ lưu tên tài liệu và vị trí
            # thì panel đoạn trích sẽ rỗng khi xem lại lịch sử.
            cited_sources=json.dumps(
                [
                    {
                        "document_name": s.document_name,
                        "position_ref": s.position_ref,
                        "chunk_id": s.chunk_id,
                        "document_id": s.document_id,
                        "text": s.text,
                        "supporting_sentences": supporting_sentences(result.answer, s.text),
                    }
                    for s in result.sources
                ],
                ensure_ascii=False,
            ),
        )
    )

    # Chỉ ghi ký ức cho câu hỏi thật — không ghi cho nhánh gợi ý học tiếp (đọc
    # lại dữ liệu có sẵn, không phải một sự kiện học tập mới) và không ghi cho
    # câu bị guardrail chặn (không phản ánh điều gì về trình độ người học).
    if capability is None and guardrail_result is not None and not guardrail_result.blocked:
        event_type, content = _classify_question_event(req.question, result)
        record_event(db, user_id=req.user_id, event_type=event_type, content=content)

    db.commit()

    return {
        "conversation_id": conversation_id,
        "answer": result.answer,
        "is_grounded": result.is_grounded,
        "abstained": qa_result.abstained if qa_result else False,
        "sources": [
            {
                "document_name": s.document_name,
                "position_ref": s.position_ref,
                "chunk_id": s.chunk_id,
                "document_id": s.document_id,
                "text": s.text,
                # Câu nào trong đoạn trích thực sự chống đỡ câu trả lời — dùng
                # để tô sáng trong panel, tính bằng trùng lặp từ vựng, không
                # tốn lượt gọi LLM (app/citation.py).
                "supporting_sentences": supporting_sentences(result.answer, s.text),
            }
            for s in result.sources
        ],
        "search_report": (
            {
                "passes_run": qa_result.search_report.passes_run,
                "searched_documents": qa_result.search_report.searched_documents,
                "near_misses": [
                    {
                        "chunk_id": n.chunk_id,
                        "document_id": n.document_id,
                        "document_name": n.document_name,
                        "position_ref": n.position_ref,
                        "text": n.text,
                        "score": n.score,
                    }
                    for n in qa_result.search_report.near_misses
                ],
                "suggested_topics": qa_result.search_report.suggested_topics,
            }
            if qa_result and qa_result.search_report
            else None
        ),
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
