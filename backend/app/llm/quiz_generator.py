"""Sinh Quiz trắc nghiệm từ tài liệu (F3), dùng kỹ thuật generator + verifier.

Cùng nguyên tắc với app/llm/rag.py: 1 lượt gọi sinh nội dung, sau đó VERIFY
TỪNG CÂU HỎI riêng lẻ để phục vụ metric "≥ 85% câu hỏi đúng nội dung" trong
PRD §2. Item nào không xác minh được (JSON hỏng, thiếu field, tham chiếu
chunk không tồn tại, verifier từ chối) đều bị loại thay vì cố gắng sửa/đoán
— tránh trả về nội dung không đáng tin cậy cho người học.

Test bằng fake LLM client — xem tests/test_quiz_generator.py.
"""

import json
from dataclasses import dataclass
from typing import List, Optional

from app.llm.rag import LLMClient, RetrievedChunk


@dataclass
class QuizItem:
    question: str
    options: List[str]
    correct_answer: str
    explanation: str
    source_document: str
    source_position: str


# Trình độ truyền vào tường minh mỗi lần sinh quiz (giống num_questions) — xem
# cùng lý do ở app/llm/rag.py::_LEVEL_INSTRUCTIONS (chưa có Learning Profile).
_DIFFICULTY_INSTRUCTIONS = {
    "beginner": (
        "Ưu tiên câu hỏi kiểm tra định nghĩa/khái niệm cơ bản, không yêu cầu suy "
        "luận nhiều bước. Phần giải thích đáp án phải viết bằng ngôn ngữ đơn "
        "giản, giải nghĩa rõ mọi thuật ngữ chuyên môn xuất hiện trong câu hỏi "
        "hoặc đáp án. Các lựa chọn sai (distractor) nên là hiểu lầm phổ biến dễ "
        "nhận ra, không đánh đố bằng chi tiết kỹ thuật nhỏ."
    ),
    "advanced": (
        "Ưu tiên câu hỏi yêu cầu phân tích, so sánh, hoặc áp dụng kiến thức vào "
        "tình huống mới — không chỉ hỏi lại định nghĩa. Câu hỏi không được trùng "
        "dạng với câu hỏi kiểm tra định nghĩa/khái niệm cơ bản ở mức beginner: "
        "đề bài nên đặt vào một tình huống hoặc ví dụ cụ thể, và các lựa chọn "
        "sai (distractor) phải là kết quả của một sai lầm kỹ thuật hợp lý, "
        "không phải đáp án hiển nhiên sai ai cũng loại được ngay."
    ),
}


def _build_difficulty_instruction(difficulty: Optional[str]) -> str:
    if not difficulty:
        return ""
    text = _DIFFICULTY_INSTRUCTIONS.get(difficulty.strip().lower())
    if not text:
        text = f"Điều chỉnh độ khó câu hỏi phù hợp với trình độ: {difficulty}."
    return f" {text}"


def _build_generator_prompt(
    chunks: List[RetrievedChunk],
    num_questions: int,
    difficulty: Optional[str] = None,
) -> str:
    context = "\n\n".join(
        f"[{i}] Nguồn: {c.document_name}, {c.position_ref}\n{c.text}" for i, c in enumerate(chunks)
    )
    return (
        f"Dựa CHỈ trên các đoạn trích tài liệu dưới đây, hãy soạn {num_questions} câu hỏi "
        "trắc nghiệm (mỗi câu 4 lựa chọn, chỉ 1 đáp án đúng) để kiểm tra kiến thức người học."
        f"{_build_difficulty_instruction(difficulty)} "
        "Viết câu hỏi, các lựa chọn và giải thích bằng đúng ngôn ngữ của đoạn trích tài liệu "
        "dưới đây (ví dụ tài liệu tiếng Anh thì soạn câu hỏi bằng tiếng Anh).\n\n"
        f"Đoạn trích tài liệu:\n{context}\n\n"
        "Trả lời DUY NHẤT bằng JSON, là một mảng object gồm các trường: "
        '"question" (string), "options" (mảng 4 chuỗi), "correct_answer" (string, khớp đúng '
        'một phần tử trong options), "explanation" (string, giải thích ngắn), "chunk_index" '
        "(số nguyên = số thứ tự [n] của đoạn trích dùng làm căn cứ cho câu hỏi này). "
        "Không thêm text nào khác ngoài JSON."
    )


def _build_item_verifier_prompt(question: str, correct_answer: str, chunk_text: str) -> str:
    return (
        "Đọc đoạn trích tài liệu và câu hỏi trắc nghiệm kèm đáp án dưới đây. Trả lời DUY NHẤT "
        "'CÓ' nếu đáp án được nêu trực tiếp/suy ra rõ ràng từ đoạn trích, hoặc 'KHÔNG' nếu không.\n\n"
        f"Đoạn trích tài liệu:\n{chunk_text}\n\n"
        f"Câu hỏi: {question}\nĐáp án: {correct_answer}\n\n"
        "Đáp án (chỉ 'CÓ' hoặc 'KHÔNG'):"
    )


def generate_quiz(
    chunks: List[RetrievedChunk],
    llm_client: LLMClient,
    num_questions: int = 5,
    difficulty: Optional[str] = None,
) -> List[QuizItem]:
    if not chunks:
        return []

    raw_response = llm_client.complete(_build_generator_prompt(chunks, num_questions, difficulty=difficulty))
    try:
        raw_items = json.loads(raw_response)
    except (json.JSONDecodeError, TypeError):
        return []

    if not isinstance(raw_items, list):
        return []

    verified_items: List[QuizItem] = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue

        question = raw.get("question")
        options = raw.get("options")
        correct_answer = raw.get("correct_answer")
        explanation = raw.get("explanation", "")
        chunk_index = raw.get("chunk_index")

        if not question or not options or not correct_answer or chunk_index is None:
            continue  # thiếu field bắt buộc -> bỏ qua, KHÔNG gọi verifier (đỡ tốn quota)

        if not isinstance(chunk_index, int) or not (0 <= chunk_index < len(chunks)):
            continue  # tham chiếu chunk không hợp lệ -> bỏ qua, KHÔNG gọi verifier

        chunk = chunks[chunk_index]
        verdict = llm_client.complete(_build_item_verifier_prompt(question, correct_answer, chunk.text))
        if not verdict.strip().upper().startswith(("CÓ", "YES")):
            continue

        verified_items.append(
            QuizItem(
                question=question,
                options=options,
                correct_answer=correct_answer,
                explanation=explanation,
                source_document=chunk.document_name,
                source_position=chunk.position_ref,
            )
        )

    return verified_items
