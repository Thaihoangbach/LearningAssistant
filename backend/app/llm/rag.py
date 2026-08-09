"""Logic hỏi đáp RAG (F2) theo kỹ thuật generator + verifier.

Đây KHÔNG phải multi-agent — là một pipeline 2 bước cố định, không có agent
tự quyết định hành động tiếp theo (đã thống nhất trong architecture-diagrams.md
mục 0). `llm_client` được inject qua tham số (Dependency Injection) để module
này test được bằng fake client, không cần gọi Gemini API thật — xem
`tests/test_rag.py`.

Điều kiện chặn theo PRD §8: "0 trường hợp câu trả lời hỏi đáp không có trích
dẫn nguồn khi đưa ra kết luận chắc chắn". Bước verifier là cơ chế chính thực
thi điều kiện này — không được bỏ qua để tiết kiệm quota Gemini.
"""

from dataclasses import dataclass
from typing import List, Protocol


class LLMClient(Protocol):
    """Interface tối thiểu mà mọi LLM client (thật hoặc giả) phải có."""

    def complete(self, prompt: str) -> str: ...


@dataclass
class RetrievedChunk:
    text: str
    document_name: str
    position_ref: str
    score: float


@dataclass
class AnswerResult:
    answer: str
    is_grounded: bool
    sources: List[RetrievedChunk]


NO_CONTEXT_MESSAGE = "Nội dung này chưa có trong tài liệu bạn đã tải lên."
NOT_GROUNDED_MESSAGE = (
    "Chưa đủ căn cứ trong kho tài liệu để trả lời chắc chắn câu hỏi này."
)

_POSITIVE_VERDICTS = ("CÓ", "YES", "TRUE")


def _build_context(chunks: List[RetrievedChunk]) -> str:
    parts = []
    for c in chunks:
        parts.append(f"[Nguồn: {c.document_name}, {c.position_ref}]\n{c.text}")
    return "\n\n".join(parts)


def _build_generator_prompt(question: str, context: str) -> str:
    return (
        "Bạn là trợ lý học tập. CHỈ trả lời dựa trên đoạn trích tài liệu dưới đây.\n"
        "Nếu đoạn trích không chứa câu trả lời, hãy nói rõ là không có thông tin.\n\n"
        f"Đoạn trích tài liệu:\n{context}\n\n"
        f"Câu hỏi: {question}\n\n"
        "Trả lời ngắn gọn, chính xác, chỉ dựa trên đoạn trích trên:"
    )


def _build_verifier_prompt(draft_answer: str, context: str) -> str:
    return (
        "Bạn là bộ kiểm tra tính xác thực. Đọc đoạn trích tài liệu và câu trả lời nháp "
        "dưới đây. Trả lời DUY NHẤT 'CÓ' nếu toàn bộ nội dung câu trả lời được nêu "
        "trực tiếp trong đoạn trích, hoặc 'KHÔNG' nếu câu trả lời có bất kỳ phần nào "
        "không được nêu trực tiếp trong đoạn trích.\n\n"
        f"Đoạn trích tài liệu:\n{context}\n\n"
        f"Câu trả lời nháp:\n{draft_answer}\n\n"
        "Đáp án (chỉ 'CÓ' hoặc 'KHÔNG'):"
    )


def answer_question(
    question: str,
    retrieved_chunks: List[RetrievedChunk],
    llm_client: LLMClient,
    min_score: float = 0.3,
) -> AnswerResult:
    relevant = [c for c in retrieved_chunks if c.score >= min_score]
    if not relevant:
        return AnswerResult(answer=NO_CONTEXT_MESSAGE, is_grounded=False, sources=[])

    context = _build_context(relevant)

    # Lượt gọi 1/2 — Generator
    draft_answer = llm_client.complete(_build_generator_prompt(question, context))

    # Lượt gọi 2/2 — Verifier
    verdict = llm_client.complete(_build_verifier_prompt(draft_answer, context))
    is_grounded = verdict.strip().upper().startswith(_POSITIVE_VERDICTS)

    if not is_grounded:
        return AnswerResult(answer=NOT_GROUNDED_MESSAGE, is_grounded=False, sources=[])

    return AnswerResult(answer=draft_answer, is_grounded=True, sources=relevant)
