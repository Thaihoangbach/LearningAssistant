"""Sinh Flashcard từ tài liệu (TC14), dùng kỹ thuật generator + verifier.

Cùng cấu trúc với app/llm/quiz_generator.py — chỉ đổi output shape sang
front/back thay vì question/options. Mỗi cặp front/back được verify riêng
để đảm bảo nội dung nằm trong hoặc suy ra hợp lý từ tài liệu, không "bịa".

Test bằng fake LLM client — xem tests/test_flashcard_generator.py.
"""

import json
from dataclasses import dataclass
from typing import List

from app.llm.rag import LLMClient, RetrievedChunk


@dataclass
class FlashcardItem:
    front: str
    back: str
    source_document: str
    source_position: str


def _build_generator_prompt(chunks: List[RetrievedChunk], num_cards: int) -> str:
    context = "\n\n".join(
        f"[{i}] Nguồn: {c.document_name}, {c.position_ref}\n{c.text}" for i, c in enumerate(chunks)
    )
    return (
        f"Dựa CHỈ trên các đoạn trích tài liệu dưới đây, hãy soạn {num_cards} flashcard để "
        "ôn tập nhanh (mỗi flashcard gồm mặt trước là thuật ngữ/câu hỏi ngắn, mặt sau là "
        "định nghĩa/câu trả lời ngắn gọn). Viết bằng đúng ngôn ngữ của đoạn trích tài liệu "
        "dưới đây (ví dụ tài liệu tiếng Anh thì soạn flashcard bằng tiếng Anh).\n\n"
        f"Đoạn trích tài liệu:\n{context}\n\n"
        "Trả lời DUY NHẤT bằng JSON, là một mảng object gồm các trường: "
        '"front" (string), "back" (string), "chunk_index" (số nguyên = số thứ tự [n] của '
        "đoạn trích dùng làm căn cứ cho flashcard này). Không thêm text nào khác ngoài JSON."
    )


def _build_item_verifier_prompt(front: str, back: str, chunk_text: str) -> str:
    return (
        "Đọc đoạn trích tài liệu và flashcard (mặt trước/mặt sau) dưới đây. Trả lời DUY NHẤT "
        "'CÓ' nếu nội dung mặt sau được nêu trực tiếp/suy ra rõ ràng từ đoạn trích, hoặc "
        "'KHÔNG' nếu không.\n\n"
        f"Đoạn trích tài liệu:\n{chunk_text}\n\n"
        f"Mặt trước: {front}\nMặt sau: {back}\n\n"
        "Đáp án (chỉ 'CÓ' hoặc 'KHÔNG'):"
    )


def generate_flashcards(
    chunks: List[RetrievedChunk],
    llm_client: LLMClient,
    num_cards: int = 10,
) -> List[FlashcardItem]:
    if not chunks:
        return []

    raw_response = llm_client.complete(_build_generator_prompt(chunks, num_cards))
    try:
        raw_items = json.loads(raw_response)
    except (json.JSONDecodeError, TypeError):
        return []

    if not isinstance(raw_items, list):
        return []

    verified_items: List[FlashcardItem] = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue

        front = raw.get("front")
        back = raw.get("back")
        chunk_index = raw.get("chunk_index")

        if not front or not back or chunk_index is None:
            continue  # thiếu field bắt buộc -> bỏ qua, KHÔNG gọi verifier (đỡ tốn quota)

        if not isinstance(chunk_index, int) or not (0 <= chunk_index < len(chunks)):
            continue  # tham chiếu chunk không hợp lệ -> bỏ qua, KHÔNG gọi verifier

        chunk = chunks[chunk_index]
        verdict = llm_client.complete(_build_item_verifier_prompt(front, back, chunk.text))
        if not verdict.strip().upper().startswith(("CÓ", "YES")):
            continue

        verified_items.append(
            FlashcardItem(
                front=front,
                back=back,
                source_document=chunk.document_name,
                source_position=chunk.position_ref,
            )
        )

    return verified_items
