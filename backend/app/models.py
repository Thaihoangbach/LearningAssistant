"""SQLAlchemy models — phạm vi F1-F4 (quản lý tài liệu, hỏi đáp, quiz,
mastery) cộng Flashcard. Kế hoạch học tập (F5) không có bảng riêng — tính
trực tiếp từ Topic/MasteryScore mỗi lần gọi, xem app/services/study_planner.py.
"""

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

# Chiều embedding của Cohere embed-multilingual-v3.0 (app/ingestion/embedder.py)
# — cố định vì đổi model embedding mà không re-embed lại toàn bộ dữ liệu cũ sẽ
# trộn vector khác chiều/không gian vào cùng một cột.
EMBEDDING_DIM = 1024


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
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    file_name = Column(String, nullable=False)
    # Tên hiển thị người dùng tự đặt lúc upload, tách khỏi `file_name` (tên
    # file OS gốc, có thể là chuỗi khó đọc kiểu "slide_ch3_v2_final.pdf").
    # Nullable — UI hiển thị display_name nếu có, fallback về file_name nếu
    # không (frontend/src/pages/UploadPage.jsx và mọi nơi khác đang hiển thị
    # d.file_name).
    display_name = Column(String, nullable=True)
    doc_type = Column(String, nullable=True)  # "slide" | "giáo trình" | "ghi chú"
    course_name = Column(String, nullable=True)
    status = Column(String, default="đang xử lý")  # đang xử lý | sẵn sàng | lỗi
    error_reason = Column(Text, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    # Versioning: khi upload lại CÙNG NỘI DUNG (content_hash) trong cùng
    # course_name, bản cũ được đánh dấu is_latest=False thay vì xoá, để hỏi
    # đáp/quiz chỉ dùng bản mới nhất (xem app/routers/documents.py) nhưng vẫn
    # giữ lịch sử.
    version = Column(Integer, default=1)
    is_latest = Column(Boolean, default=True)
    # SHA-256 nội dung file (BUG-005) — nhận diện bản trùng bằng NỘI DUNG THẬT,
    # không phải file_name: hai file khác nhau có thể trùng tên, và cùng một
    # file có thể đổi tên giữa hai lần tải lên. Nullable vì tài liệu tạo trước
    # khi cột này tồn tại không có giá trị hồi tố (không migrate ngược dữ liệu
    # cũ — xem migration thêm cột).
    content_hash = Column(String, nullable=True, index=True)

    user = relationship("User", back_populates="documents")


class DocumentChunk(Base):
    """Một đoạn trích đã chunk + embed của tài liệu — đơn vị truy hồi RAG.

    Trước đây sống trong file FAISS riêng theo user_id (app/vectorstore/
    faiss_store.py, đã gỡ bỏ) vì SQLite không có kiểu vector. Chuyển hẳn vào
    Postgres (pgvector) xoá luôn lớp "hai nguồn sự thật" đó — chunk, vị trí
    nguồn, VÀ vector embedding giờ nằm chung một bảng, một transaction với
    Document, không còn nguy cơ lệch pha giữa DB và file index rời (chính là
    BUG-2 đã vá tạm bằng khoá theo user_id ở app/concurrency.py; giờ nhường
    lại cho transaction thật của Postgres).

    Nhánh từ khoá của hybrid search (trước đây rank_bm25 tự tính lại mỗi lần
    gọi, app/vectorstore/bm25_index.py, đã gỡ bỏ) dùng full-text search có
    sẵn của Postgres qua index hàm `to_tsvector('simple', text)` — xem
    scripts/migrations hoặc Alembic revision tạo index này.
    """

    __tablename__ = "document_chunks"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False, index=True)
    document_name = Column(String, nullable=False)
    position_ref = Column(String, nullable=True)
    text = Column(Text, nullable=False)
    embedding = Column(Vector(EMBEDDING_DIM), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    course_name = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation")


class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=_uuid)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False, index=True)
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
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    course_name = Column(String, nullable=True)
    name = Column(String, nullable=False)


class CourseDeadline(Base):
    """Ngày thi riêng của một môn học, khoá theo (user_id, course_name) — dùng
    để lập kế hoạch ôn tập đa môn (app/services/study_planner.py::
    generate_multi_course_plan, app/routers/study_plan.py). `course_name`
    vẫn là chuỗi tự do như trên Document/Topic, KHÔNG có bảng Course riêng
    với khoá ngoại — bảng này chỉ lưu thêm một thuộc tính (ngày thi) mà
    course_name không suy ra được từ dữ liệu khác, khác với kết quả kế hoạch
    (luôn tính lại, không lưu — xem docstring app/services/study_planner.py).

    `exam_date` dùng kiểu Date (không phải DateTime như phần còn lại của
    models.py) vì đây là một NGÀY LỊCH thuần tuý — giờ trong ngày không có ý
    nghĩa với "còn bao nhiêu ngày tới kỳ thi", và DateTime dễ lệch 1 ngày khi
    so sánh qua ranh giới múi giờ.
    """

    __tablename__ = "course_deadlines"
    __table_args__ = (
        UniqueConstraint("user_id", "course_name", name="uq_course_deadlines_user_course"),
    )

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    course_name = Column(String, nullable=False)
    exam_date = Column(Date, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow)


class Quiz(Base):
    __tablename__ = "quizzes"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    items = relationship("QuizItem", back_populates="quiz")


class QuizItem(Base):
    __tablename__ = "quiz_items"

    id = Column(String, primary_key=True, default=_uuid)
    quiz_id = Column(String, ForeignKey("quizzes.id"), nullable=False, index=True)
    topic_id = Column(String, ForeignKey("topics.id"), nullable=True, index=True)
    question = Column(Text, nullable=False)
    options = Column(Text, nullable=False)  # JSON string
    correct_answer = Column(String, nullable=False)
    explanation = Column(Text, nullable=True)
    source_document = Column(String, nullable=True)
    source_position = Column(String, nullable=True)
    # Độ khó lúc sinh câu hỏi — dùng để cân trọng số mastery (app/services/mastery.py).
    # Không lưu thì trả lời đúng một câu dễ cộng điểm y hệt một câu khó.
    difficulty = Column(String, nullable=True)

    quiz = relationship("Quiz", back_populates="items")


class FlashcardSet(Base):
    """Cùng cấu trúc với Quiz/QuizItem — chỉ đổi output shape sang front/back."""

    __tablename__ = "flashcard_sets"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    items = relationship("FlashcardItem", back_populates="flashcard_set")


class FlashcardItem(Base):
    __tablename__ = "flashcard_items"

    id = Column(String, primary_key=True, default=_uuid)
    flashcard_set_id = Column(String, ForeignKey("flashcard_sets.id"), nullable=False, index=True)
    topic_id = Column(String, ForeignKey("topics.id"), nullable=True, index=True)
    front = Column(Text, nullable=False)
    back = Column(Text, nullable=False)
    source_document = Column(String, nullable=True)
    source_position = Column(String, nullable=True)

    flashcard_set = relationship("FlashcardSet", back_populates="items")


class Attempt(Base):
    """Kết quả một lượt làm câu hỏi — input duy nhất cho công thức mastery (app/services/mastery.py)."""

    __tablename__ = "attempts"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    quiz_item_id = Column(String, ForeignKey("quiz_items.id"), nullable=False, index=True)
    topic_id = Column(String, ForeignKey("topics.id"), nullable=True, index=True)
    is_correct = Column(Boolean, nullable=False)
    # Đáp án người học đã chọn. Quiz generator cố tình thiết kế đáp án nhiễu là
    # "nhầm lẫn hợp lý giữa hai khái niệm gần nhau", nên CHỌN NHẦM CÁI NÀO mang
    # thông tin chẩn đoán thật — không lưu thì chỉ cá nhân hoá được tới mức
    # "chủ đề yếu", thô hơn nhiều so với mức dữ liệu cho phép.
    selected_answer = Column(Text, nullable=True)
    attempted_at = Column(DateTime, default=datetime.utcnow)


class MasteryScore(Base):
    """Điểm mastery hiện tại theo (topic_id, user_id) — cache kết quả app/services/mastery.py.

    Tính lại và ghi đè mỗi khi có Attempt mới, để F4/F5/F7 đọc nhanh không
    phải quét lại toàn bộ lịch sử Attempt mỗi lần hiển thị dashboard.

    `UniqueConstraint` là sửa TẬN GỐC cho race điều kiện từng vá tạm bằng
    khoá theo user_id (app/concurrency.py, đã gỡ) — 2 lượt nộp bài gần nhau
    từng có thể cùng thấy "chưa có record" rồi cùng INSERT, sinh 2 dòng
    trùng (user_id, topic_id). Giờ ràng buộc ở tầng DB: `submit_attempt`
    dùng INSERT ... ON CONFLICT DO UPDATE (Postgres upsert nguyên tử), nên
    kể cả 2 transaction thật sự chạy đồng thời cũng không thể tạo ra 2 dòng
    trùng — DB tự chặn, không cần khoá ở tầng ứng dụng nữa.
    """

    __tablename__ = "mastery_scores"
    __table_args__ = (UniqueConstraint("user_id", "topic_id", name="uq_mastery_scores_user_topic"),)

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    topic_id = Column(String, ForeignKey("topics.id"), nullable=False, index=True)
    score = Column(Float, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow)


class LearningProfile(Base):
    """Hồ sơ cá nhân hóa DÀI HẠN theo user — lấp khoảng trống đã đo được:
    Personalization chỉ đạt 0.13/1.00 trên Golden Set một phần vì `level` phải
    khai báo lại tường minh mỗi request, không có nơi nào "nhớ" trình độ
    người học.

    Đây là dữ liệu cá nhân hóa TĨNH (người dùng tự khai báo), khác hẳn dữ liệu
    tiến độ suy ra được từ Attempt/MasteryScore (cá nhân hóa ĐỘNG, xem
    app/services/mastery.py) — hai loại này cố tình tách riêng theo đúng
    thiết kế đã mô tả ở architecture-diagrams.md, không gộp vào một bảng.

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


class DocumentTopic(Base):
    """Dàn ý chủ đề rút được từ tài liệu ngay lúc nạp (app/ingestion/outline.py).

    Giải quyết hai vấn đề cùng lúc. Người dùng tải tài liệu lên là thấy ngay
    nó gồm những phần gì, thay vì đối diện một ô chat trống không biết hỏi gì.
    Và hệ thống có `Topic` để bám vào NGAY, thay vì phải đợi tới lúc người dùng
    tự gõ tên chủ đề khi sinh quiz — nhờ vậy kế hoạch ôn tập lập được từ trước
    khi làm bài lần nào.

    Tách khỏi bảng `Topic` vì hai thứ khác nhau: bảng này mô tả CẤU TRÚC của
    một tài liệu cụ thể, còn `Topic` là đơn vị theo dõi tiến độ của người học
    và có thể gộp nhiều tài liệu.
    """

    __tablename__ = "document_topics"

    id = Column(String, primary_key=True, default=_uuid)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String, nullable=False)
    position_ref = Column(String, nullable=True)
    order_index = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class FlashcardReview(Base):
    """Một lượt ôn lại flashcard — bảng LỊCH SỬ, mỗi lượt ôn thêm một hàng.

    Trạng thái hiện tại của một thẻ là hàng MỚI NHẤT của thẻ đó (xem
    app/services/flashcard.py::latest_review_by_item). Giữ nguyên lịch sử thay
    vì ghi đè một hàng trạng thái để về sau còn dựng lại được đường cong quên
    của người học nếu cần.

    `interval_days`/`ease`/`next_due_at` do app/services/spaced_repetition.py
    tính, module đó thuần và không biết gì về bảng này.
    """

    __tablename__ = "flashcard_reviews"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    flashcard_item_id = Column(String, ForeignKey("flashcard_items.id"), nullable=False, index=True)
    rating = Column(String, nullable=False)  # again | hard | good | easy
    reviewed_at = Column(DateTime, default=datetime.utcnow)
    interval_days = Column(Float, nullable=False)
    ease = Column(Float, nullable=False)
    next_due_at = Column(DateTime, nullable=False)


class MemoryEvent(Base):
    """Ký ức EPISODIC — từng sự kiện học tập rời rạc, xuyên phiên làm việc.

    Khác với LearningProfile (cá nhân hoá TĨNH, người dùng tự khai) và
    MasteryScore (cá nhân hoá ĐỘNG dạng tổng hợp, một điểm số cho mỗi chủ đề),
    bảng này giữ lại TỪNG sự kiện cụ thể: đã hỏi câu gì, sai câu quiz nào, quên
    thẻ nào. Nhờ vậy hệ thống nhắc lại được đúng chi tiết ("lần trước bạn nhầm
    giữa X và Y") thay vì chỉ biết "chủ đề này điểm thấp".

    `importance` gán lúc ghi bằng bảng tra cứu tĩnh trong
    app/memory/scoring.py, không gọi LLM.

    `last_accessed_at`/`access_count` hiện CHỈ để quan sát và hiển thị ở trang
    Memory — chưa đưa vào công thức chấm điểm truy hồi.

    `embedding` trước đây sống trong một file FAISS riêng theo user_id
    (app/memory/store.py, đã gỡ bỏ) — SQLite không có kiểu vector nên phải
    tách ra một kho khác, kéo theo đúng lớp "hai nguồn sự thật" (và race điều
    kiện BUG-2) như DocumentChunk từng gặp. Đưa thẳng vào bảng này: ghi/xoá
    một MemoryEvent giờ ghi/xoá luôn cả vector, cùng một transaction.
    Nullable vì việc TÍNH điểm importance/lưu sự kiện không phụ thuộc có
    embed được hay không — một lỗi API embedding không được chặn đứng việc
    ghi lại sự kiện học tập.
    """

    __tablename__ = "memory_events"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    event_type = Column(String, nullable=False)
    topic_id = Column(String, ForeignKey("topics.id"), nullable=True, index=True)
    content = Column(Text, nullable=False)
    importance = Column(Float, nullable=False)
    source_ref = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_accessed_at = Column(DateTime, nullable=True)
    access_count = Column(Integer, default=0)
    embedding = Column(Vector(EMBEDDING_DIM), nullable=True)
