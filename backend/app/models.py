"""SQLAlchemy models — phạm vi F1-F4 (quản lý tài liệu, hỏi đáp, quiz,
mastery) cộng Flashcard. Kế hoạch học tập (F5) không có bảng riêng — tính
trực tiếp từ Topic/MasteryScore mỗi lần gọi, xem app/study_planner.py.

CHƯA CHẠY ĐƯỢC TRONG SANDBOX NÀY: cần `pip install sqlalchemy`.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def _uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=_uuid)
    email = Column(String, unique=True, nullable=False)
    display_name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    documents = relationship("Document", back_populates="user")
    conversations = relationship("Conversation", back_populates="user")


class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    file_name = Column(String, nullable=False)
    doc_type = Column(String, nullable=True)  # "slide" | "giáo trình" | "ghi chú"
    course_name = Column(String, nullable=True)
    status = Column(String, default="đang xử lý")  # đang xử lý | sẵn sàng | lỗi
    error_reason = Column(Text, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    # Versioning: khi upload lại cùng file_name+course_name, bản cũ được đánh
    # dấu is_latest=False thay vì xoá, để hỏi đáp/quiz chỉ dùng bản mới nhất
    # (xem app/routers/documents.py) nhưng vẫn giữ lịch sử.
    version = Column(Integer, default=1)
    is_latest = Column(Boolean, default=True)

    user = relationship("User", back_populates="documents")


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    course_name = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation")


class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=_uuid)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False)
    role = Column(String, nullable=False)  # "user" | "assistant"
    content = Column(Text, nullable=False)
    cited_sources = Column(Text, nullable=True)  # JSON string: [{document_name, position_ref}, ...]
    is_grounded = Column(Boolean, nullable=True)  # null nếu role="user"
    created_at = Column(DateTime, default=datetime.utcnow)

    conversation = relationship("Conversation", back_populates="messages")


class Topic(Base):
    """Chủ đề — dùng để nhóm câu hỏi/flashcard và tính mastery (F4)."""

    __tablename__ = "topics"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    course_name = Column(String, nullable=True)
    name = Column(String, nullable=False)


class Quiz(Base):
    __tablename__ = "quizzes"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    items = relationship("QuizItem", back_populates="quiz")


class QuizItem(Base):
    __tablename__ = "quiz_items"

    id = Column(String, primary_key=True, default=_uuid)
    quiz_id = Column(String, ForeignKey("quizzes.id"), nullable=False)
    topic_id = Column(String, ForeignKey("topics.id"), nullable=True)
    question = Column(Text, nullable=False)
    options = Column(Text, nullable=False)  # JSON string
    correct_answer = Column(String, nullable=False)
    explanation = Column(Text, nullable=True)
    source_document = Column(String, nullable=True)
    source_position = Column(String, nullable=True)

    quiz = relationship("Quiz", back_populates="items")


class FlashcardSet(Base):
    """Cùng cấu trúc với Quiz/QuizItem — chỉ đổi output shape sang front/back."""

    __tablename__ = "flashcard_sets"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    items = relationship("FlashcardItem", back_populates="flashcard_set")


class FlashcardItem(Base):
    __tablename__ = "flashcard_items"

    id = Column(String, primary_key=True, default=_uuid)
    flashcard_set_id = Column(String, ForeignKey("flashcard_sets.id"), nullable=False)
    topic_id = Column(String, ForeignKey("topics.id"), nullable=True)
    front = Column(Text, nullable=False)
    back = Column(Text, nullable=False)
    source_document = Column(String, nullable=True)
    source_position = Column(String, nullable=True)

    flashcard_set = relationship("FlashcardSet", back_populates="items")


class Attempt(Base):
    """Kết quả một lượt làm câu hỏi — input duy nhất cho công thức mastery (app/mastery.py)."""

    __tablename__ = "attempts"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    quiz_item_id = Column(String, ForeignKey("quiz_items.id"), nullable=False)
    topic_id = Column(String, ForeignKey("topics.id"), nullable=True)
    is_correct = Column(Boolean, nullable=False)
    attempted_at = Column(DateTime, default=datetime.utcnow)


class MasteryScore(Base):
    """Điểm mastery hiện tại theo (topic_id, user_id) — cache kết quả app/mastery.py.

    Tính lại và ghi đè mỗi khi có Attempt mới, để F4/F5/F7 đọc nhanh không
    phải quét lại toàn bộ lịch sử Attempt mỗi lần hiển thị dashboard.
    """

    __tablename__ = "mastery_scores"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    topic_id = Column(String, ForeignKey("topics.id"), nullable=False)
    score = Column(Float, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow)


class LearningProfile(Base):
    """Hồ sơ cá nhân hóa DÀI HẠN theo user — Giai đoạn 1 trong hướng phát
    triển (docs/thesis, Chương 8), lấp khoảng trống đã đo được: Personalization
    chỉ đạt 0.13/1.00 trên Golden Set một phần vì `level` phải khai báo lại
    tường minh mỗi request, không có nơi nào "nhớ" trình độ người học.

    Đây là dữ liệu cá nhân hóa TĨNH (người dùng tự khai báo), khác hẳn dữ liệu
    tiến độ suy ra được từ Attempt/MasteryScore (cá nhân hóa ĐỘNG, xem
    app/mastery.py) — hai loại này cố tình tách riêng theo đúng thiết kế đã
    mô tả ở architecture-diagrams.md, không gộp vào một bảng.

    `learning_goal` hiện chỉ lưu và trả về qua GET/PUT /profile để hiển thị,
    CHƯA được đưa vào prompt của generator (app/llm/rag.py) — đây là input tự
    do do người dùng nhập, đưa thẳng vào prompt mỗi câu hỏi mà không qua
    guardrail (guardrail chỉ chạy trên trường `question`) sẽ mở một đường
    prompt injection dai dẳng qua nhiều lượt hỏi. Cần thêm bước kiểm soát
    trước khi nối trường này vào ngữ cảnh sinh câu trả lời.
    """

    __tablename__ = "learning_profiles"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, unique=True)
    preferred_level = Column(String, nullable=True)  # "beginner" | "advanced" | None
    learning_goal = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow)
