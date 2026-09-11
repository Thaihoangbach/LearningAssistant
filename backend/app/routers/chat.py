"""API routes cho F2 — hỏi đáp có căn cứ dựa trên tài liệu (RAG)."""

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.llm.client_factory import get_llm_client
from app.llm.guardrail import check_question
from app.llm.rag import _SIMPLIFY_REQUEST_RE, AnswerResult, ConversationTurn
from app.llm.recommendation import TopicMastery, build_recommendation
from app.memory.service import record_event
from app.models import (
    Attempt,
    Conversation,
    Document,
    DocumentTopic,
    MasteryScore,
    MemoryEvent,
    Message,
    QuizItem,
    Topic,
)
from app.retrieval.pipeline import retrieve_chunks
from app.retrieval.query_context import build_retrieval_query
from app.ingestion.outline import filter_topic_titles
from app.services.capability_detector import detect_capability
from app.services.citation import _content_words, supporting_sentences
from app.services.context_assembly import assemble_context
from app.services.flashcard import count_due
from app.services.learner_context import build_learner_context
from app.services.mastery import decay_unpractised
from app.services.misconception import WrongChoice, find_repeated_misconceptions
from app.services.qa_pipeline import answer_with_fallback
from app.services.structural_retrieval import StructuralRetrievalUnavailable
from app.services.study_planner import TopicPriority, generate_plan
from app.services.summarize import (
    NEEDS_TOPIC_MESSAGE,
    UNAVAILABLE_MESSAGE,
    TopicCandidate,
    build_summary,
    is_summarize_request,
    resolve_topic,
)

router = APIRouter(prefix="/chat", tags=["chat"])

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
    topics = [
        TopicMastery(
            topic_name=topic.name,
            score=decay_unpractised(score.score, score.updated_at),
        )
        for score, topic in rows
    ]

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

    # Quan niệm sai LẶP LẠI là lý do cụ thể hơn hẳn "chủ đề này điểm thấp", nên
    # chèn lên ĐẦU danh sách bằng chứng của chủ đề tương ứng.
    wrong_rows = (
        db.query(Attempt, QuizItem)
        .join(QuizItem, Attempt.quiz_item_id == QuizItem.id)
        .filter(Attempt.user_id == user_id, Attempt.is_correct == False)  # noqa: E712
        .all()
    )
    for text in find_repeated_misconceptions(
        [
            WrongChoice(
                quiz_item_id=item.id,
                question=item.question,
                selected_answer=attempt.selected_answer or "",
                correct_answer=item.correct_answer,
                topic_name=topic_name_by_id.get(item.topic_id, ""),
            )
            for attempt, item in wrong_rows
        ]
    ):
        for name in topic_name_by_id.values():
            if name and f'"{name}"' in text:
                evidence_by_topic.setdefault(name, []).insert(0, text)
                break

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


_REDIRECT_TO_CALENDAR_MESSAGE = (
    "Có vẻ bạn cần lên kế hoạch cho nhiều môn cùng lúc — vào trang Kế hoạch ôn để "
    "chọn từng môn kèm ngày thi riêng, kế hoạch sẽ chính xác hơn một câu hỏi chat."
)


def _mentions_multiple_known_courses(question: str, known_course_names: list[str]) -> bool:
    lowered = question.lower()
    return sum(1 for name in known_course_names if name and name.lower() in lowered) > 1


def _build_study_plan_result(
    db: Session,
    user_id: str,
    course_name: str | None,
    days: int,
    question: str,
    multiple_days_mentioned: bool,
) -> AnswerResult:
    """Lập kế hoạch ôn tập ngay trong hội thoại — CHỈ cho ca đơn-môn-đơn-hạn.
    Câu hỏi nhắc nhiều hơn 1 hạn ("N ngày") hoặc nhiều hơn 1 môn đã có của
    người dùng được nhường sang trang Kế hoạch ôn (spec §10) — chat
    capability này cố tình KHÔNG dùng LLM để tách nhiều thực thể tự do, giữ
    đúng nguyên tắc điều phối rẻ-trước-đắt-sau của module này."""
    known_course_names = [
        c
        for (c,) in db.query(Document.course_name)
        .filter(Document.user_id == user_id, Document.course_name.isnot(None))
        .distinct()
        .all()
    ]
    if multiple_days_mentioned or _mentions_multiple_known_courses(question, known_course_names):
        return AnswerResult(answer=_REDIRECT_TO_CALENDAR_MESSAGE, is_grounded=True, sources=[])

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

    # Lọc chất lượng TẠI ĐIỂM TIÊU THỤ (app/ingestion/outline.py::
    # filter_topic_titles) — không tin thẳng Topic.name, vì bảng này có thể
    # còn chứa dữ liệu rút từ TRƯỚC khi heuristic trích xuất outline được siết
    # chặt (BUG-001). Dùng filter_topic_titles (không chỉ is_plausible_topic
    # từng dòng) vì loại nhiễu chính trong dữ liệu thật là HEADER/FOOTER LẶP
    # LẠI theo từng trang scan — mỗi biến thể lỗi OCR khác nhau đủ để không
    # dòng nào tự nó trông bất thường, chỉ lộ ra khi so cả danh sách với nhau.
    plausible_names = set(filter_topic_titles([t.name for t in topics]))
    topics = [t for t in topics if t.name in plausible_names]
    if not topics:
        return AnswerResult(
            answer="Không đủ dữ liệu để tạo kế hoạch học tập đáng tin cậy từ tài liệu hiện tại.",
            is_grounded=True,
            sources=[],
        )

    scores_by_topic_id = {
        s.topic_id: decay_unpractised(s.score, s.updated_at)
        for s in db.query(MasteryScore).filter(MasteryScore.user_id == user_id).all()
    }
    order_by_name = {
        dt.title: dt.order_index
        for dt in db.query(DocumentTopic).filter(DocumentTopic.user_id == user_id).all()
    }
    plan = generate_plan(
        [
            TopicPriority(
                topic_name=t.name,
                score=scores_by_topic_id.get(t.id),
                order_index=order_by_name.get(t.name),
            )
            for t in topics
        ],
        days=days,
    )

    # Mỗi chủ đề một dòng (không nối bằng dấu phẩy) — một ngày có thể có rất
    # nhiều chủ đề, gộp chung một dòng sẽ thành một khối văn bản dài khó đọc.
    # AnswerWithCitations.jsx đã có sẵn `whitespace-pre-wrap` nên chỉ cần
    # xuống dòng thật ở đây là frontend hiển thị đúng, không cần sửa gì thêm.
    lines = [f"Kế hoạch ôn tập trong {days} ngày, ưu tiên chủ đề yếu và chưa học:"]
    for day in plan:
        lines.append(f"\nNgày {day.day}:")
        if day.topics:
            lines.extend(f"- {topic}" for topic in day.topics)
        else:
            lines.append("- ôn tự do")
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


def _build_summarize_result(
    db: Session, user_id: str, question: str, ready_docs: list[Document], llm_client
) -> AnswerResult:
    """Tóm tắt một DocumentTopic — xem app/services/summarize.py cho thiết kế
    đầy đủ (structural retrieval thay semantic, output dạng bullet). Ở đây chỉ
    lo phần đặc thù router: lấy danh sách chủ đề ứng viên trong phạm vi tài
    liệu đã chọn, lọc chất lượng (cùng bộ lọc với gợi ý chủ đề khi từ chối trả
    lời — BUG-001/BUG-006), rồi giao việc còn lại cho summarize.py."""
    document_ids = {d.id for d in ready_docs}
    rows = (
        db.query(DocumentTopic)
        .filter(DocumentTopic.user_id == user_id, DocumentTopic.document_id.in_(document_ids))
        .all()
    )
    plausible_titles = set(filter_topic_titles([r.title for r in rows]))
    candidates = [
        TopicCandidate(topic_id=r.id, document_id=r.document_id, title=r.title)
        for r in rows
        if r.title in plausible_titles
    ]

    topic = resolve_topic(question, candidates)
    if topic is None:
        return AnswerResult(answer=NEEDS_TOPIC_MESSAGE, is_grounded=False, sources=[], needs_clarification=True)

    try:
        return build_summary(db, user_id, topic, llm_client)
    except StructuralRetrievalUnavailable:
        return AnswerResult(answer=UNAVAILABLE_MESSAGE, is_grounded=False, sources=[])


@router.post("/ask")
def ask(req: AskRequest, db: Session = Depends(get_db)):
    # Câu hỏi rỗng/toàn khoảng trắng vẫn qua được validation kiểu `str` của
    # Pydantic, nhưng Cohere embed API từ chối text rỗng (BadRequestError,
    # không bắt được ở embedder.py) — chặn ở đây thay vì để crash 500 lúc
    # embed_query().
    if not req.question.strip():
        raise HTTPException(400, "Câu hỏi không được để trống.")

    # Điều phối bằng bảng đăng ký năng lực (app/services/capability_detector.py)
    # thay vì chuỗi if/else. Không khớp năng lực nào thì rơi về hỏi đáp có căn
    # cứ — đường DUY NHẤT bắt buộc qua generator + verifier.
    capability = detect_capability(req.question)
    guardrail_result = None
    qa_result = None

    context = assemble_context(db, req, needs_document_scope=capability is None)
    ready_docs = context.ready_docs
    document_ids = context.document_ids
    conversation_id = context.conversation_id
    history = context.history

    if capability is not None:
        # Các năng lực này chỉ đọc lại dữ liệu đã tính sẵn (mastery, kế hoạch,
        # lịch ôn) nên không có gì để bịa và không cần qua verifier.
        if capability.name == "study_plan":
            result = _build_study_plan_result(
                db,
                req.user_id,
                req.course_name,
                capability.params["days"],
                req.question,
                capability.params["multiple_days_mentioned"],
            )
        elif capability.name == "flashcard_due":
            result = _build_flashcard_due_result(db, req.user_id)
        else:
            result = _build_recommendation_result(db, req.user_id, req.course_name)
    else:
        llm_client = get_llm_client()

        # Guardrail (F2 an toàn đầu vào) — chặn prompt injection/jailbreak, yêu cầu
        # làm bài hộ, và câu hỏi ngoài phạm vi học tập TRƯỚC khi tốn lượt gọi
        # generator+verifier.
        guardrail_result = check_question(req.question, llm_client=llm_client)
        if guardrail_result.blocked:
            result = AnswerResult(answer=guardrail_result.message, is_grounded=False, sources=[])
        elif is_summarize_request(req.question):
            # Intent riêng có output contract khác (bullet, structural
            # retrieval) — xem app/services/summarize.py. Vẫn qua guardrail ở
            # trên trước, cùng lý do an toàn với đường hỏi đáp chung bên dưới.
            result = _build_summarize_result(db, req.user_id, req.question, ready_docs, llm_client)
        else:
            learner = build_learner_context(
                db, req.user_id, requested_level=req.level, query=req.question
            )

            effective_top_k = req.top_k + LEVEL_TOP_K_BOOST if learner.effective_level else req.top_k

            def _retrieve(query: str, top_k: int, mode: str):
                return retrieve_chunks(
                    db=db,
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
                # Cùng lớp lọc chất lượng với kế hoạch ôn tập
                # (_build_study_plan_result ở trên, BUG-006) — DocumentTopic
                # cũng có thể còn dòng nhiễu rút từ trước khi heuristic outline
                # được siết chặt (vd OCR vỡ "BY A. M. TUBING", hoặc header/
                # footer scan lặp lại theo trang).
                plausible_titles = set(filter_topic_titles([r.title for r in rows]))
                rows = [r for r in rows if r.title in plausible_titles]
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
        # Hợp cả hai nguồn: qa_result (đường RAG chung, answer_with_fallback
        # không copy needs_clarification sang `result` khi tái dựng
        # AnswerResult ở trên) VÀ result.needs_clarification (đường Summarize,
        # app/services/summarize.py không đi qua qa_result) — thiếu vế nào
        # cũng làm sai tín hiệu clarification của MỘT trong hai đường, phát
        # hiện được khi test /chat/ask thật với yêu cầu tóm tắt mơ hồ.
        "needs_clarification": (qa_result.needs_clarification if qa_result else False)
        or result.needs_clarification,
        # Hậu quét injection trên câu trả lời cuối (app/services/qa_pipeline.py)
        # — phát hiện, không tự chặn. `False` mặc định cho các nhánh không sinh
        # bằng LLM (capability rule-based, guardrail chặn từ đầu vào).
        "injection_flag": qa_result.injection_flag if qa_result else False,
        "sources": [
            {
                "document_name": s.document_name,
                "position_ref": s.position_ref,
                "chunk_id": s.chunk_id,
                "document_id": s.document_id,
                "text": s.text,
                # Câu nào trong đoạn trích thực sự chống đỡ câu trả lời — dùng
                # để tô sáng trong panel, tính bằng trùng lặp từ vựng, không
                # tốn lượt gọi LLM (app/services/citation.py).
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
