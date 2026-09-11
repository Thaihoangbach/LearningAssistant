"""So sánh hai khái niệm/chủ đề — truy hồi RIÊNG cho từng vế rồi gộp lại, thay
vì một truy vấn gộp duy nhất. Một truy vấn gộp kiểu "so sánh X và Y" có thể bị
lệch điểm số nghiêng hẳn về phía nào có nhiều nội dung hơn trong kho tài liệu,
khiến top-k chỉ toàn đoạn trích về X mà bỏ sót Y — tách truy vấn theo từng vế
đảm bảo cả hai phía đều có cơ hội được trích riêng.

Vẫn đi qua NGUYÊN generator+verifier của app/llm/rag.py::answer_question, tái
dùng output_style="bullets" đã có sẵn cho Tóm tắt — mỗi luận điểm so sánh tự
đứng một dòng, tự mang trích dẫn riêng, đúng hình thức cần cho một kết quả so
sánh dễ đọc, không cần thêm một kiểu trình bày mới.

Đây là một trong ba intent có output contract riêng đã thống nhất khi thảo
luận thiết kế (Compare/Summarize/Apply) — bảy intent còn lại tiếp tục dùng
đường RAG chung ở app/routers/chat.py, không qua module này.

`is_compare_request`/`extract_comparison_entities` dùng regex thuần, KHÔNG gọi
LLM — cùng nguyên tắc rẻ-trước-đắt-sau đã áp dụng cho
app/services/summarize.py và app/services/capability_detector.py."""

import re
from typing import List, Optional, Set, Tuple

from sqlalchemy.orm import Session

from app.llm.rag import AnswerResult, LLMClient, RetrievedChunk, answer_question
from app.retrieval.pipeline import retrieve_chunks

# "khác nhau"/"khác biệt" CHỈ tính khi đi kèm "giữa" — giảm khớp nhầm với câu
# không thực sự yêu cầu so sánh hai vế (vd "các cách khác nhau để...").
_COMPARE_INTENT_RE = re.compile(
    r"so sánh|khác\s*(nhau|biệt)\s*giữa|compare\s|difference(s)?\s+between",
    re.IGNORECASE,
)

_ENTITY_PAIR_PATTERNS = [
    re.compile(r"so sánh\s+(?:giữa\s+)?(.+?)\s+(?:và|với)\s+(.+?)\s*[?.!]*$", re.IGNORECASE),
    re.compile(r"khác\s*(?:nhau|biệt)?\s*giữa\s+(.+?)\s+(?:và|với)\s+(.+?)\s*[?.!]*$", re.IGNORECASE),
    re.compile(r"compare\s+(.+?)\s+(?:and|with|to)\s+(.+?)\s*[?.!]*$", re.IGNORECASE),
    re.compile(r"difference(?:s)?\s+between\s+(.+?)\s+and\s+(.+?)\s*[?.!]*$", re.IGNORECASE),
]

# Phần đuôi lịch sự/nghi vấn thường bị cuốn vào vế thứ hai vì regex ở trên bắt
# tới hết câu (vd "khác nhau giữa X và Y là gì?" -> vế 2 sẽ là "Y là gì" nếu
# không cắt). Lặp lại cho tới khi ổn định vì có thể xếp chồng nhiều cụm.
_TRAILING_FILLER_RE = re.compile(
    r"\s*(giúp\s+tôi|cho\s+tôi|cho\s+mình|được\s+không|nhé|please|"
    r"là\s+gì|là\s+sao|ra\s+sao|như\s+thế\s+nào|thế\s+nào)\s*$",
    re.IGNORECASE,
)

NEEDS_ENTITIES_MESSAGE = (
    "Bạn muốn so sánh những khái niệm/chủ đề nào? Nêu rõ hai vế cần so sánh (ví dụ: "
    "\"so sánh Attention và RNN\") để hệ thống tìm đúng nội dung cho từng phía."
)

# Mỗi vế lấy riêng top_k này — đủ để mỗi phía có nguyên liệu mà không làm
# context quá dài (tổng tối đa 2 x TOP_K_PER_SIDE đoạn trích trước khi gộp).
TOP_K_PER_SIDE = 4


def is_compare_request(question: str) -> bool:
    return bool(_COMPARE_INTENT_RE.search(question))


def _clean_entity(text: str) -> str:
    text = text.strip()
    while True:
        stripped = _TRAILING_FILLER_RE.sub("", text).strip(" ,.:;!?")
        if stripped == text:
            return stripped
        text = stripped


def extract_comparison_entities(question: str) -> Optional[Tuple[str, str]]:
    """Tách 2 vế cần so sánh từ câu hỏi. Trả None nếu không khớp mẫu nào rõ
    ràng — phía gọi hỏi lại thay vì đoán bừa (cùng nguyên tắc với
    summarize.py::resolve_topic)."""
    for pattern in _ENTITY_PAIR_PATTERNS:
        match = pattern.search(question)
        if not match:
            continue
        entity_a, entity_b = _clean_entity(match.group(1)), _clean_entity(match.group(2))
        if entity_a and entity_b:
            return entity_a, entity_b
    return None


def _merge_chunks(a: List[RetrievedChunk], b: List[RetrievedChunk]) -> List[RetrievedChunk]:
    """Gộp hai danh sách, bỏ trùng theo chunk_id — cùng một đoạn có thể được
    cả hai truy vấn riêng lẻ tìm thấy (vd khi tài liệu bàn cả hai khái niệm
    trong cùng một đoạn)."""
    merged: List[RetrievedChunk] = []
    seen_chunk_ids: Set[str] = set()
    for chunk in a + b:
        if chunk.chunk_id and chunk.chunk_id in seen_chunk_ids:
            continue
        if chunk.chunk_id:
            seen_chunk_ids.add(chunk.chunk_id)
        merged.append(chunk)
    return merged


def build_comparison(
    db: Session,
    user_id: str,
    document_ids: Optional[Set[str]],
    entity_a: str,
    entity_b: str,
    question: str,
    llm_client: LLMClient,
) -> AnswerResult:
    """Truy hồi riêng cho từng vế rồi giao NGUYÊN câu hỏi gốc cho
    generator+verifier — xem docstring module."""
    chunks_a = retrieve_chunks(
        db=db, user_id=user_id, query=entity_a, top_k=TOP_K_PER_SIDE, document_ids=document_ids
    )
    chunks_b = retrieve_chunks(
        db=db, user_id=user_id, query=entity_b, top_k=TOP_K_PER_SIDE, document_ids=document_ids
    )
    merged = _merge_chunks(chunks_a, chunks_b)

    return answer_question(
        question=question,
        retrieved_chunks=merged,
        llm_client=llm_client,
        output_style="bullets",
    )
