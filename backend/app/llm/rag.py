"""Logic hỏi đáp RAG (F2) theo kỹ thuật generator + verifier.

Đây KHÔNG phải multi-agent — là một pipeline 2 bước cố định, không có agent
tự quyết định hành động tiếp theo (đã thống nhất trong architecture-diagrams.md
mục 0). `llm_client` được inject qua tham số (Dependency Injection) để module
này test được bằng fake client, không cần gọi Gemini API thật — xem
`tests/test_rag.py`.

Điều kiện chặn theo PRD §8: "0 trường hợp câu trả lời hỏi đáp không có trích
dẫn nguồn khi đưa ra kết luận chắc chắn". Bước verifier là cơ chế chính thực
thi điều kiện này — không được bỏ qua để tiết kiệm quota Gemini.

`conversation_history` (nếu có) chỉ đưa vào prompt của GENERATOR để giải
quyết đại từ/ngữ cảnh câu hỏi tiếp nối (vd: "nó" trong "tại sao nó không cần
RNN?"), KHÔNG đưa vào prompt của verifier — verifier vẫn chỉ được phép chấp
nhận câu trả lời có căn cứ trực tiếp trong đoạn trích tài liệu hiện tại, để
giữ đúng điều kiện chặn ở trên (lịch sử hội thoại không phải "tài liệu").
"""

import re
from dataclasses import dataclass
from typing import List, Optional, Protocol


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
class ConversationTurn:
    """Một lượt hỏi-đáp trước đó trong cùng hội thoại, dùng để giải ngữ cảnh."""

    question: str
    answer: str


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

# Câu hỏi tự nêu rõ chưa hiểu / muốn giải thích lại đơn giản hơn (vd: "tôi
# chưa hiểu...", "giải thích đơn giản hơn", "explain simpler") -> chỉnh
# hướng dẫn generator dùng ví dụ/thuật ngữ cơ bản hơn, thay vì lặp lại y hệt
# câu trả lời trước. Đây là phản ứng theo yêu cầu tường minh trong câu hỏi,
# không phải cá nhân hoá theo hồ sơ người học (chưa có Learning Profile).
_SIMPLIFY_REQUEST_RE = re.compile(
    r"chưa hiểu|đơn giản hơn|dễ hiểu hơn|giải thích lại|explain (it )?simpl|"
    r"in simple terms|simpler terms",
    re.IGNORECASE,
)

# Trình độ do người gọi truyền vào tường minh mỗi request (giống top_k/min_score)
# — KHÔNG phải một hồ sơ Learning Profile lưu trữ lâu dài (chưa xây dựng), chỉ
# đủ để cùng một câu hỏi trả lời khác độ sâu theo trình độ khai báo (TC08).
_LEVEL_INSTRUCTIONS = {
    "beginner": (
        "Người hỏi ở trình độ mới bắt đầu — dùng ví dụ cụ thể, giải thích từng "
        "bước. BẮT BUỘC: mọi thuật ngữ chuyên môn xuất hiện trong câu trả lời "
        "(kể cả khi lấy nguyên văn từ đoạn trích) đều phải kèm theo giải thích "
        "bằng ngôn ngữ đời thường ngay khi dùng lần đầu, không được để thuật "
        "ngữ trần trụi không giải nghĩa."
    ),
    "advanced": (
        "Người hỏi ở trình độ nâng cao — BẮT BUỘC câu trả lời phải rõ ràng "
        "chuyên sâu HƠN hẳn một câu trả lời cơ bản: đi thẳng vào chi tiết kỹ "
        "thuật/công thức có trong đoạn trích, dùng thuật ngữ chuyên ngành "
        "không giải nghĩa lại, và nếu đoạn trích có đủ dữ liệu thì phân "
        "tích/so sánh/chỉ ra giới hạn hoặc trường hợp đặc biệt thay vì chỉ mô "
        "tả khái quát. KHÔNG được trả lời hời hợt như thể đang giải thích cho "
        "người mới bắt đầu."
    ),
}


def _build_level_instruction(level: Optional[str]) -> str:
    if not level:
        return ""
    text = _LEVEL_INSTRUCTIONS.get(level.strip().lower())
    if not text:
        text = f"Điều chỉnh độ sâu câu trả lời phù hợp với trình độ người học: {level}."
    return f"\n{text}\n"


def _build_context(chunks: List[RetrievedChunk]) -> str:
    parts = []
    for c in chunks:
        parts.append(f"[Nguồn: {c.document_name}, {c.position_ref}]\n{c.text}")
    return "\n\n".join(parts)


def _dedupe_sources(chunks: List[RetrievedChunk]) -> List[RetrievedChunk]:
    # Nhiều chunk khác nhau có thể trùng (document_name, position_ref) khi tài
    # liệu được chia section thô (vd DOCX nhóm 10 đoạn văn/section) — vẫn giữ
    # NGUYÊN VẸN cho _build_context() để generator có đủ ngữ cảnh, nhưng danh
    # sách citation trả cho người dùng chỉ nên hiện MỖI vị trí nguồn một lần.
    seen = set()
    deduped = []
    for c in chunks:
        key = (c.document_name, c.position_ref)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(c)
    return deduped


def _build_history_block(history: Optional[List[ConversationTurn]]) -> str:
    if not history:
        return ""
    lines = [
        "Lịch sử hội thoại gần đây (CHỈ để hiểu ngữ cảnh/đại từ trong câu hỏi hiện "
        "tại, KHÔNG dùng làm căn cứ để trả lời):"
    ]
    for turn in history:
        lines.append(f"Người dùng: {turn.question}")
        lines.append(f"Trợ lý: {turn.answer}")
    lines.append("")
    return "\n".join(lines) + "\n"


def _build_generator_prompt(
    question: str,
    context: str,
    history: Optional[List[ConversationTurn]] = None,
    level: Optional[str] = None,
) -> str:
    history_block = _build_history_block(history)
    simplify_instruction = (
        "\nNgười dùng cho biết chưa hiểu hoặc muốn giải thích đơn giản hơn — hãy "
        "dùng ví dụ cụ thể và thuật ngữ cơ bản, đừng chỉ lặp lại câu trả lời trước.\n"
        if _SIMPLIFY_REQUEST_RE.search(question)
        else ""
    )
    level_instruction = _build_level_instruction(level)
    return (
        "Bạn là trợ lý học tập. CHỈ trả lời dựa trên đoạn trích tài liệu dưới đây.\n"
        "Nếu đoạn trích không chứa câu trả lời, hãy nói rõ là không có thông tin.\n"
        "Nếu các đoạn trích đến từ nhiều nguồn khác nhau và có thông tin mâu thuẫn "
        "nhau, hãy nêu rõ sự khác biệt đó và trích dẫn riêng từng nguồn thay vì tự "
        "chọn một câu trả lời duy nhất.\n"
        "Trả lời bằng đúng ngôn ngữ của câu hỏi (nếu câu hỏi bằng tiếng Anh thì trả lời "
        "bằng tiếng Anh, kể cả khi đoạn trích tài liệu là ngôn ngữ khác)."
        f"{simplify_instruction}"
        f"{level_instruction}\n"
        f"{history_block}"
        f"Đoạn trích tài liệu:\n{context}\n\n"
        f"Câu hỏi: {question}\n\n"
        "Trả lời ngắn gọn, chính xác, chỉ dựa trên đoạn trích trên:"
    )


def _build_verifier_prompt(draft_answer: str, context: str) -> str:
    return (
        "Bạn là bộ kiểm tra tính xác thực. Đọc đoạn trích tài liệu và câu trả lời nháp "
        "dưới đây. Trả lời DUY NHẤT 'CÓ' nếu toàn bộ nội dung thực chất (khái niệm, số "
        "liệu, kết luận) của câu trả lời được nêu trực tiếp HOẶC suy ra rõ ràng từ đoạn "
        "trích — kể cả khi câu trả lời diễn đạt lại, tổng hợp từ nhiều phần của đoạn "
        "trích, hoặc nêu ví dụ minh hoạ hợp lý cho một khái niệm đã có trong đoạn trích. "
        "Trả lời 'KHÔNG' CHỈ KHI câu trả lời có nội dung thực chất KHÔNG xuất hiện và "
        "KHÔNG suy ra được từ đoạn trích (bịa đặt khái niệm/số liệu không có căn cứ).\n\n"
        f"Đoạn trích tài liệu:\n{context}\n\n"
        f"Câu trả lời nháp:\n{draft_answer}\n\n"
        "Đáp án (chỉ 'CÓ' hoặc 'KHÔNG'):"
    )


def answer_question(
    question: str,
    retrieved_chunks: List[RetrievedChunk],
    llm_client: LLMClient,
    min_score: float = 0.3,
    conversation_history: Optional[List[ConversationTurn]] = None,
    level: Optional[str] = None,
) -> AnswerResult:
    relevant = [c for c in retrieved_chunks if c.score >= min_score]
    if not relevant:
        return AnswerResult(answer=NO_CONTEXT_MESSAGE, is_grounded=False, sources=[])

    context = _build_context(relevant)

    # Lượt gọi 1/2 — Generator
    draft_answer = llm_client.complete(
        _build_generator_prompt(question, context, history=conversation_history, level=level)
    )

    # Lượt gọi 2/2 — Verifier (KHÔNG nhận lịch sử hội thoại, chỉ xét đoạn trích hiện tại)
    verdict = llm_client.complete(_build_verifier_prompt(draft_answer, context))
    is_grounded = verdict.strip().upper().startswith(_POSITIVE_VERDICTS)

    if not is_grounded:
        return AnswerResult(answer=NOT_GROUNDED_MESSAGE, is_grounded=False, sources=[])

    return AnswerResult(answer=draft_answer, is_grounded=True, sources=_dedupe_sources(relevant))
