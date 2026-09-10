"""Sinh Flashcard từ tài liệu (TC14), dùng kỹ thuật generator + verifier.

Cùng cấu trúc với app/llm/quiz_generator.py — chỉ đổi output shape sang
front/back thay vì question/options. Mỗi cặp front/back được verify riêng
để đảm bảo nội dung nằm trong hoặc suy ra hợp lý từ tài liệu, không "bịa".

Test bằng fake LLM client — xem tests/test_flashcard_generator.py.
"""

import json
import re
from dataclasses import dataclass
from typing import List

from app.llm.rag import LLMClient, RetrievedChunk


@dataclass
class FlashcardItem:
    front: str
    back: str
    source_document: str
    source_position: str
    content_type: str


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


# Phase 4 (Learning Loop) — mirror app/llm/quiz_generator.py: dedup
# DETERMINISTIC bằng overlap coefficient (giao / độ dài tập nhỏ hơn), rẻ hơn
# LLM-judge (_build_item_judge_prompt, Phase 5) nên giữ nguyên cách làm này.
# Xem docstring cùng tên bên quiz_generator.py để biết lý do chọn overlap
# coefficient thay vì Jaccard.
_DUPLICATE_SIMILARITY_THRESHOLD = 0.8


def _card_words(front: str) -> set:
    return set(re.findall(r"\w+", front.lower(), flags=re.UNICODE))


def _is_near_duplicate(front: str, existing_fronts: List[str]) -> bool:
    words = _card_words(front)
    if not words:
        return False
    for other in existing_fronts:
        other_words = _card_words(other)
        if not other_words:
            continue
        overlap = len(words & other_words) / min(len(words), len(other_words))
        if overlap >= _DUPLICATE_SIMILARITY_THRESHOLD:
            return True
    return False


def _build_avoid_duplicates_note(asked_fronts: List[str]) -> str:
    if not asked_fronts:
        return ""
    numbered = "\n".join(f"- {f}" for f in asked_fronts)
    return (
        "\n\nKHÔNG lặp lại (kể cả diễn đạt lại) các flashcard đã có sau đây:\n"
        f"{numbered}"
    )


# Learning Loop Phase 5 — LLM-judge cho "không mơ hồ"/phân loại nội dung
# (khái niệm/định nghĩa/công thức/...), gộp CHUNG một lượt gọi với việc xác
# minh nội dung đã có từ trước thay vì thêm một lượt gọi LLM riêng — mirror
# app/llm/quiz_generator.py::_build_item_judge_prompt (xem docstring ở đó để
# biết lý do gộp thay vì thêm lượt gọi mới). Flashcard không có khái niệm
# "độ khó yêu cầu" như quiz nên không có trường difficulty_match.
def _build_item_judge_prompt(front: str, back: str, chunk_text: str) -> str:
    return (
        "Đọc đoạn trích tài liệu và flashcard (mặt trước/mặt sau) dưới đây, rồi đánh giá "
        "chất lượng flashcard.\n\n"
        f"Đoạn trích tài liệu:\n{chunk_text}\n\n"
        f"Mặt trước: {front}\nMặt sau: {back}\n\n"
        'Đánh giá "valid": true nếu nội dung mặt sau được nêu trực tiếp/suy ra rõ ràng từ '
        "đoạn trích, false nếu không.\n"
        '"ambiguous": true nếu mặt trước có thể hiểu theo nhiều cách hoặc có nhiều câu trả '
        "lời hợp lý khác với mặt sau, false nếu mặt trước rõ ràng, chỉ ứng với một câu trả "
        "lời.\n"
        '"content_type": phân loại flashcard vào MỘT trong các giá trị sau: "concept" (khái '
        'niệm), "definition" (định nghĩa), "formula" (công thức), "fact" (sự kiện), '
        '"procedure" (quy trình/các bước).\n\n'
        'Trả lời DUY NHẤT bằng JSON dạng {"valid": bool, "ambiguous": bool, "content_type": '
        'string}. Không thêm text nào khác ngoài JSON.'
    )


def _parse_judgment(raw_response: str) -> dict | None:
    try:
        data = json.loads(_strip_json_fence(raw_response))
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    if not all(key in data for key in ("valid", "ambiguous", "content_type")):
        return None
    return data


def _strip_json_fence(text: str) -> str:
    """Bỏ markdown code fence (```json ... ```) nếu model bọc JSON trong đó.

    Cùng vấn đề và cách xử lý ở app/llm/quiz_generator.py::_strip_json_fence."""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    return text.strip()


def _generate_verified_batch(
    chunks: List[RetrievedChunk],
    llm_client: LLMClient,
    count: int,
    asked_fronts: List[str],
) -> List[FlashcardItem]:
    """Một lượt sinh + verify — tách khỏi `generate_flashcards` để hàm đó gọi
    lại được nhiều lần khi thiếu thẻ (mirror app/llm/quiz_generator.py::
    _generate_verified_batch, BUG-003)."""
    prompt = _build_generator_prompt(chunks, count) + _build_avoid_duplicates_note(asked_fronts)
    raw_response = llm_client.complete(prompt)
    try:
        raw_items = json.loads(_strip_json_fence(raw_response))
    except (json.JSONDecodeError, TypeError):
        return []

    if not isinstance(raw_items, list):
        return []

    verified_items: List[FlashcardItem] = []
    seen_fronts = list(asked_fronts)
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

        if _is_near_duplicate(front, seen_fronts):
            continue  # trùng hoặc gần trùng (kể cả diễn đạt lại) -> bỏ, KHÔNG gọi verifier

        chunk = chunks[chunk_index]
        judgment = _parse_judgment(llm_client.complete(_build_item_judge_prompt(front, back, chunk.text)))
        if judgment is None or not judgment["valid"] or judgment["ambiguous"]:
            continue  # JSON hỏng, thiếu field, nội dung sai, hoặc mặt trước mơ hồ -> loại

        seen_fronts.append(front)
        verified_items.append(
            FlashcardItem(
                front=front,
                back=back,
                source_document=chunk.document_name,
                source_position=chunk.position_ref,
                content_type=judgment["content_type"],
            )
        )

    return verified_items


# Mirror app/llm/quiz_generator.py::_MAX_GENERATION_ATTEMPTS (BUG-003) — xem
# docstring ở đó để biết lý do chỉ bù MỘT lượt, không lặp vô hạn.
_MAX_GENERATION_ATTEMPTS = 2


def generate_flashcards(
    chunks: List[RetrievedChunk],
    llm_client: LLMClient,
    num_cards: int = 10,
) -> List[FlashcardItem]:
    if not chunks:
        return []

    collected: List[FlashcardItem] = []

    for attempt in range(_MAX_GENERATION_ATTEMPTS):
        remaining = num_cards - len(collected)
        if remaining <= 0:
            break
        if attempt > 0 and not collected:
            break  # lượt đầu ra 0 thẻ hoàn toàn -> không bù, xem docstring hằng số ở trên

        batch = _generate_verified_batch(chunks, llm_client, remaining, [c.front for c in collected])
        collected.extend(batch)

    return collected
