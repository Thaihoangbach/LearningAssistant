"""Lắp ráp context dùng chung cho một lượt hỏi đáp — tách khỏi
app/routers/chat.py::ask() (đã hơn 200 dòng, tự làm mọi việc: chọn tài liệu
trong phạm vi, tạo/nạp hội thoại, nạp lịch sử...) để hàm đó chỉ còn điều phối,
và để các năng lực sinh câu trả lời mới (Summarize, Compare, Apply — chưa xây,
xem thảo luận thiết kế) có một điểm vào context chung thay vì mỗi capability
tự lắp lại logic chọn tài liệu/hội thoại của riêng nó.

Đây là refactor THUẦN — hành vi giữ nguyên y hệt phần code cũ trong
app/routers/chat.py::ask(), chỉ đổi chỗ code sống. `_load_conversation_history`
cũng chuyển hẳn về đây vì nó là một phần của việc lắp context, không phải logic
điều phối câu hỏi."""

from dataclasses import dataclass
from typing import List, Optional, Set

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.database import ensure_user
from app.llm.rag import ConversationTurn
from app.models import Conversation, Document, Message

# Số lượt hỏi-đáp gần nhất đưa vào ngữ cảnh câu hỏi tiếp nối — xem
# app/llm/rag.py (lịch sử chỉ dùng để giải đại từ/ngữ cảnh, không phải căn cứ
# trả lời).
MAX_HISTORY_TURNS = 3


@dataclass
class QAContext:
    # None khi capability đã xử lý xong bằng dữ liệu tính sẵn (không cần đọc
    # tài liệu để trả lời) — xem app/services/capability_detector.py.
    document_ids: Optional[Set[str]]
    ready_docs: List[Document]
    conversation_id: str
    history: List[ConversationTurn]


def _load_conversation_history(db: Session, conversation_id: str) -> List[ConversationTurn]:
    """Lấy N lượt hỏi-đáp gần nhất của hội thoại, dùng để giải ngữ cảnh câu hỏi
    tiếp nối (vd: "nó" ám chỉ chủ đề đã hỏi trước đó) — xem app/llm/rag.py."""
    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .all()
    )
    turns: List[ConversationTurn] = []
    pending_question: Optional[str] = None
    for m in messages:
        if m.role == "user":
            pending_question = m.content
        elif m.role == "assistant" and pending_question is not None:
            turns.append(ConversationTurn(question=pending_question, answer=m.content))
            pending_question = None
    return turns[-MAX_HISTORY_TURNS:]


def assemble_context(db: Session, req, needs_document_scope: bool) -> QAContext:
    """Lắp context cho một lượt /chat/ask: phạm vi tài liệu (nếu cần), hội
    thoại (tạo mới nếu chưa có), và lịch sử hội thoại.

    `needs_document_scope=False` cho các capability chỉ đọc dữ liệu tính sẵn
    (study_plan/flashcard_due/recommendation) — không cần và không nên chặn
    bằng HTTPException 400 "chưa có tài liệu sẵn sàng" vì các năng lực đó
    không đọc tài liệu."""
    ready_docs: List[Document] = []
    document_ids: Optional[Set[str]] = None

    if needs_document_scope:
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
        ensure_user(db, req.user_id)
        convo = Conversation(user_id=req.user_id, course_name=req.course_name)
        db.add(convo)
        db.commit()
        conversation_id = convo.id

    history = _load_conversation_history(db, conversation_id)

    return QAContext(
        document_ids=document_ids,
        ready_docs=ready_docs,
        conversation_id=conversation_id,
        history=history,
    )
