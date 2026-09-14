"""Tóm tắt một chủ đề (DocumentTopic) — dùng structural retrieval
(app/services/structural_retrieval.py) thay vì semantic top-k, vì yêu cầu
"tóm tắt chương X" cần PHỦ hết một chương, không phải các đoạn liên quan nhất
tới một câu hỏi cụ thể (khác bản chất so với hỏi đáp thường).

Vẫn đi qua NGUYÊN generator+verifier của app/llm/rag.py::answer_question —
chỉ đổi nguồn đoạn trích (structural thay vì semantic) và output_style="bullets".
Đây là một trong ba intent có output contract riêng đã thống nhất khi thảo
luận thiết kế (Compare/Summarize/Apply) — bảy intent còn lại (Understand,
Explain, Deepen, Clarify, Review, Navigate, Follow-up) tiếp tục dùng đường RAG
chung ở app/routers/chat.py, không qua module này.

`is_summarize_request` dùng regex thuần, KHÔNG gọi LLM — cùng nguyên tắc
rẻ-trước-đắt-sau đã áp dụng cho app/services/capability_detector.py. Summarize
KHÔNG đăng ký vào CAPABILITIES ở đó vì các capability trong bảng đó đều
`needs_grounding=False` (chỉ đọc dữ liệu tính sẵn), còn Summarize bắt buộc qua
generator+verifier như hỏi đáp thường."""

import re
from dataclasses import dataclass
from typing import List, Optional

from sqlalchemy.orm import Session

from app.llm.rag import AnswerResult, LLMClient, answer_question
from app.services.citation import _content_words
from app.services.structural_retrieval import StructuralRetrievalUnavailable, fetch_topic_chunks

_SUMMARIZE_INTENT_RE = re.compile(
    r"tóm tắt|tổng hợp (giúp|cho|lại) (tôi|mình)|summarize|summary",
    re.IGNORECASE,
)

NEEDS_TOPIC_MESSAGE = (
    "Bạn muốn tóm tắt phần nào? Cho biết tên chương/chủ đề cụ thể (ví dụ: \"tóm tắt "
    "chương 3\") để hệ thống tóm tắt đúng chỗ."
)

UNAVAILABLE_MESSAGE = (
    "Tài liệu này cần được xử lý lại mới dùng được tính năng tóm tắt theo chương — "
    "hãy tải lại tài liệu để hệ thống cập nhật."
)


def is_summarize_request(question: str) -> bool:
    return bool(_SUMMARIZE_INTENT_RE.search(question))


@dataclass
class TopicCandidate:
    topic_id: str
    document_id: str
    title: str
    # Trích đoạn ngắn nội dung đầu chủ đề (rỗng nếu chưa lấy được) — mở rộng
    # từ vựng khớp ngoài tiêu đề (xem resolve_topic). Optional/mặc định rỗng
    # để không phá các nơi gọi/test cũ chỉ truyền title.
    preview: str = ""


def resolve_topic(question: str, candidates: List[TopicCandidate]) -> Optional[TopicCandidate]:
    """Khớp tên chương người dùng gõ với danh sách DocumentTopic — tái dùng
    đúng cách xếp hạng theo trùng từ nội dung đã có ở
    app/routers/chat.py::_suggest_topics (không tốn lượt gọi LLM). Trả None
    nếu không có ứng viên nào trùng dù chỉ một từ nội dung — để phía gọi hỏi
    lại thay vì đoán bừa một chủ đề không liên quan.

    Khớp theo TIÊU ĐỀ + PREVIEW (đoạn trích ngắn đầu chủ đề, do phía gọi tự
    lấy sẵn — xem app/routers/chat.py::_build_summarize_result), không chỉ
    riêng tiêu đề. Lý do (Golden Set eval/reports/failure_analysis.md, Finding
    #4): tiêu đề một DocumentTopic thường là một heading NGẮN, trong khi người
    dùng hay mô tả chương/phần mình muốn tóm tắt theo NỘI DUNG bên trong thay
    vì lặp lại đúng từ trong heading gốc (vd hỏi "nguyên lý và ứng dụng của
    CNN" trong khi heading chỉ là "Kiến trúc").

    Ngưỡng chấp nhận KHÁC NHAU giữa hai nguồn: khớp qua TIÊU ĐỀ (ngắn, chính
    xác) vẫn chỉ cần >=1 từ trùng như thiết kế gốc. Khớp chỉ qua PREVIEW (một
    đoạn văn dài hơn, từ vựng chung chung hơn) cần >=2 từ trùng — một từ đơn
    lẻ trùng ngẫu nhiên (vd "liệu" trong "dữ liệu" trùng với "liệu" tách ra từ
    "tài liệu" trong câu hỏi) đủ để khớp NHẦM sang một chủ đề hoàn toàn khác,
    xác nhận qua regression live (case EDU-SUM-008 — tài liệu KHÔNG có chủ đề
    nào để tóm tắt, nhưng bị khớp nhầm sang chủ đề "Overfitting" của tài liệu
    khác chỉ vì trùng đúng 1 từ trong preview)."""
    if not candidates:
        return None

    question_words = _content_words(question)

    def _score(candidate: TopicCandidate) -> int:
        title_overlap = _content_words(candidate.title) & question_words
        preview_overlap = _content_words(candidate.preview) & question_words
        if not title_overlap and len(preview_overlap) < 2:
            return 0
        return len(title_overlap | preview_overlap)

    scored = sorted(candidates, key=_score, reverse=True)
    best = scored[0]
    if _score(best) == 0:
        return None
    return best


def build_summary(
    db: Session,
    user_id: str,
    topic: TopicCandidate,
    llm_client: LLMClient,
) -> AnswerResult:
    """Sinh bản tóm tắt cho một DocumentTopic đã xác định (xem resolve_topic).

    Ném StructuralRetrievalUnavailable ra ngoài cho phía gọi tự quyết định
    thông điệp từ chối — module này không tự bọc lỗi để giữ một nguồn thông
    điệp duy nhất (UNAVAILABLE_MESSAGE ở đây, không lặp lại ở chat.py)."""
    chunks = fetch_topic_chunks(db, user_id, topic.document_id, topic.topic_id)
    if not chunks:
        return AnswerResult(
            answer=f'Không tìm thấy nội dung nào để tóm tắt cho "{topic.title}".',
            is_grounded=False,
            sources=[],
        )

    return answer_question(
        question=f'Tóm tắt chủ đề "{topic.title}".',
        retrieved_chunks=chunks,
        llm_client=llm_client,
        # score=1.0 cố định cho mọi chunk structural (xem
        # structural_retrieval.py) — không phải điểm liên quan ngữ nghĩa nên
        # min_score mặc định (lọc theo relevance) không áp dụng ở đây.
        min_score=0.0,
        output_style="bullets",
    )
