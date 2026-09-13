"""Truy hồi CẤU TRÚC (structural retrieval) — lấy toàn bộ chunk thuộc một
DocumentTopic theo đúng thứ tự đọc gốc, khác hẳn truy hồi semantic top-k của
app/retrieval/pipeline.py::retrieve_chunks (chọn theo độ liên quan tới MỘT câu
hỏi cụ thể). Dùng cho tính năng Tóm tắt — "tóm tắt chương 3" không có một
"điểm ngữ nghĩa" rõ để so khớp, và semantic top-k quá hẹp để phủ hết một
chương.

Dựa trên `section_index` — chỉ số 0-based của section (trang PDF/nhóm đoạn văn
DOCX) mà một chunk/topic sinh ra từ đó (app/ingestion/chunker.py,
app/ingestion/outline.py). Phần TÍNH BOUNDS (compute_section_bounds) là hàm
thuần, test được không cần DB; phần fetch_topic_chunks mới chạm DB."""

from dataclasses import dataclass
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.llm.rag import RetrievedChunk
from app.models import DocumentChunk, DocumentTopic

# Trần số chunk lấy cho một lượt tóm tắt — giống tinh thần CANDIDATE_POOL ở
# app/memory/service.py: đủ để phủ một chương/section thông thường, nhưng
# không để một chương quá dài làm phình vô hạn prompt generator (mỗi request
# Tóm tắt vốn đã tốn nhiều token hơn một câu hỏi QA thường vì lấy CẢ một
# chương thay vì top_k=5-8 đoạn liên quan nhất).
MAX_STRUCTURAL_CHUNKS = 40


class StructuralRetrievalUnavailable(Exception):
    """Tài liệu/chủ đề này chưa có section_index (tải lên trước khi cột này
    tồn tại, chưa backfill) — KHÔNG lùi về suy luận position_ref như một
    fallback, vì làm vậy tái nhập đúng cái fragile mà section_index sinh ra để
    loại bỏ. Phía gọi (chat.py) bắt exception này để trả lời từ chối rõ ràng,
    yêu cầu xử lý lại tài liệu, thay vì tóm tắt dựa trên suy luận không chắc."""


@dataclass
class TopicSectionInfo:
    topic_id: str
    section_index: Optional[int]


def compute_section_bounds(
    topics: List[TopicSectionInfo], target_topic_id: str
) -> Optional[Tuple[int, Optional[int]]]:
    """Trả (start, end_exclusive) theo section_index cho chủ đề `target_topic_id`,
    hoặc None nếu không tìm thấy chủ đề đó hoặc chủ đề đó chưa có section_index.

    `end_exclusive` là section_index của chủ đề KẾ TIẾP (số nhỏ nhất lớn hơn
    start trong cùng tài liệu) — hoặc None nếu đây là chủ đề cuối cùng, nghĩa
    là lấy tới hết tài liệu. Chủ đề khác chưa có section_index (None) bị bỏ
    qua khi tìm mốc kế tiếp — không thể dùng None làm biên."""
    target = next((t for t in topics if t.topic_id == target_topic_id), None)
    if target is None or target.section_index is None:
        return None

    start = target.section_index
    later = sorted(t.section_index for t in topics if t.section_index is not None and t.section_index > start)
    end = later[0] if later else None
    return (start, end)


def fetch_topic_chunks(
    db: Session,
    user_id: str,
    document_id: str,
    topic_id: str,
    max_chunks: int = MAX_STRUCTURAL_CHUNKS,
) -> List[RetrievedChunk]:
    """Lấy toàn bộ chunk thuộc `topic_id` trong tài liệu `document_id`, theo
    đúng thứ tự đọc gốc (section_index tăng dần, rồi tới thứ tự chèn trong
    cùng section). `score=1.0` cho mọi chunk trả về — đây không phải điểm liên
    quan ngữ nghĩa, phía gọi answer_question() nên truyền min_score=0.0 khi
    dùng kết quả này (xem app/services/summarize.py)."""
    topic_rows = (
        db.query(DocumentTopic)
        .filter(DocumentTopic.user_id == user_id, DocumentTopic.document_id == document_id)
        .all()
    )
    bounds = compute_section_bounds(
        [TopicSectionInfo(topic_id=t.id, section_index=t.section_index) for t in topic_rows],
        topic_id,
    )
    if bounds is None:
        raise StructuralRetrievalUnavailable(
            f"Chủ đề {topic_id} chưa có section_index — tài liệu cần xử lý lại."
        )
    start, end = bounds

    query = (
        db.query(DocumentChunk)
        .filter(
            DocumentChunk.user_id == user_id,
            DocumentChunk.document_id == document_id,
            DocumentChunk.section_index >= start,
        )
        .order_by(DocumentChunk.section_index.asc(), DocumentChunk.created_at.asc())
    )
    if end is not None:
        query = query.filter(DocumentChunk.section_index < end)

    rows = query.limit(max_chunks).all()

    return [
        RetrievedChunk(
            text=row.text,
            document_name=row.document_name,
            position_ref=row.position_ref,
            score=1.0,
            chunk_id=row.id,
            document_id=row.document_id,
        )
        for row in rows
    ]
