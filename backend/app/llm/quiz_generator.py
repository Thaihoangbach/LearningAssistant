"""Sinh Quiz trắc nghiệm từ tài liệu (F3), dùng kỹ thuật generator + verifier.

Cùng nguyên tắc với app/llm/rag.py: 1 lượt gọi sinh nội dung, sau đó VERIFY
TỪNG CÂU HỎI riêng lẻ để phục vụ metric "≥ 85% câu hỏi đúng nội dung" trong
PRD §2. Item nào không xác minh được (JSON hỏng, thiếu field, tham chiếu
chunk không tồn tại, verifier từ chối) đều bị loại thay vì cố gắng sửa/đoán
— tránh trả về nội dung không đáng tin cậy cho người học.

Test bằng fake LLM client — xem tests/test_quiz_generator.py.
"""

import json
import re
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
    content_type: str


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
    "intermediate": (
        "Ưu tiên câu hỏi ở mức vận dụng: người học phải hiểu khái niệm rồi áp "
        "dụng vào một tình huống quen thuộc, chứ không chỉ nhắc lại định nghĩa "
        "như mức cơ bản, nhưng cũng không cần phân tích đánh đổi kỹ thuật sâu "
        "như mức nâng cao. Mỗi câu nên hỏi 'khi nào dùng', 'điều gì xảy ra "
        "nếu', hoặc 'chọn phương án nào cho trường hợp này'. Các lựa chọn sai "
        "phải là nhầm lẫn hợp lý giữa hai khái niệm gần nhau, không phải đáp "
        "án hiển nhiên sai."
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


# Learning Loop Phase 5 — LLM-judge cho "không mơ hồ"/"độ khó phù hợp"/phân
# loại nội dung (khái niệm/định nghĩa/công thức/...), gộp CHUNG một lượt gọi
# với việc xác minh nội dung đã có từ trước (verdict CÓ/KHÔNG cũ) thay vì
# thêm một lượt gọi LLM riêng — nếu thêm lượt riêng, mỗi câu hỏi sẽ tốn thêm
# một lượt gọi LLM nữa (bên cạnh generator + verify hiện có), tăng đáng kể
# latency/cost; đây chính là lý do phase này từng bị hoãn lại khi thiết kế
# roadmap ban đầu.
_CONTENT_TYPES = ("concept", "definition", "formula", "fact", "procedure")


def _build_item_judge_prompt(
    question: str,
    options: List[str],
    correct_answer: str,
    chunk_text: str,
    difficulty: Optional[str],
) -> str:
    difficulty_clause = (
        f'Câu hỏi này được yêu cầu ở mức độ khó "{difficulty}". Đặt "difficulty_match": true nếu '
        "câu hỏi phù hợp mức đó, false nếu không."
        if difficulty
        else 'Không có yêu cầu độ khó cụ thể cho câu hỏi này — luôn đặt "difficulty_match": true.'
    )
    options_text = "\n".join(f"- {o}" for o in options)
    return (
        "Đọc đoạn trích tài liệu và câu hỏi trắc nghiệm (kèm các lựa chọn, đáp án) dưới đây, "
        "rồi đánh giá chất lượng câu hỏi.\n\n"
        f"Đoạn trích tài liệu:\n{chunk_text}\n\n"
        f"Câu hỏi: {question}\nCác lựa chọn:\n{options_text}\nĐáp án: {correct_answer}\n\n"
        'Đánh giá "valid": true nếu đáp án được nêu trực tiếp/suy ra rõ ràng từ đoạn trích, '
        "false nếu không.\n"
        '"ambiguous": true nếu câu hỏi có thể hiểu theo nhiều cách hoặc có hơn một lựa chọn hợp '
        "lý đúng, false nếu câu hỏi rõ ràng và chỉ một đáp án đúng.\n"
        f"{difficulty_clause}\n"
        '"content_type": phân loại câu hỏi vào MỘT trong các giá trị sau: "concept" (khái niệm), '
        '"definition" (định nghĩa), "formula" (công thức), "fact" (sự kiện), "procedure" '
        "(quy trình/các bước).\n\n"
        'Trả lời DUY NHẤT bằng JSON dạng {"valid": bool, "ambiguous": bool, "difficulty_match": '
        'bool, "content_type": string}. Không thêm text nào khác ngoài JSON.'
    )


def _parse_judgment(raw_response: str) -> Optional[dict]:
    try:
        data = json.loads(_strip_json_fence(raw_response))
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    if not all(key in data for key in ("valid", "ambiguous", "difficulty_match", "content_type")):
        return None
    return data


def _strip_json_fence(text: str) -> str:
    """Bỏ markdown code fence (```json ... ```) nếu model bọc JSON trong đó.

    OpenAI thường trả JSON kèm fence dù prompt đã yêu cầu "DUY NHẤT JSON" —
    cùng vấn đề đã gặp và xử lý ở app/llm/rag.py::_parse_claim_verdicts."""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    return text.strip()


# Phase 4 (Learning Loop) — dedup DETERMINISTIC bằng độ trùng từ khoá; phát
# hiện trùng lặp vẫn rẻ hơn LLM-judge (_build_item_judge_prompt, Phase 5) nên
# giữ nguyên cách làm này thay vì chuyển sang hỏi LLM. Đo bằng OVERLAP
# COEFFICIENT (giao / độ
# dài tập nhỏ hơn), KHÔNG phải Jaccard (giao / hợp) — Jaccard bị pha loãng khi
# một câu chỉ thêm vài từ tiền tố vào câu kia (vd "Định nghĩa của RAG là gì?"
# so với "RAG là gì?": Jaccard chỉ 0.5 dù thực chất là hỏi lại y hệt), còn
# overlap coefficient cho ra 1.0 đúng cho trường hợp đó. Ngưỡng 0.8 vẫn đủ cao
# để không đánh trượt hai câu hỏi thật khác nhau chỉ tình cờ dùng chung vài từ
# khoá miền (vd "RAG là gì?" vs "RAG dùng để làm gì?" ~ 0.67).
_DUPLICATE_SIMILARITY_THRESHOLD = 0.8


def _question_words(question: str) -> set:
    return set(re.findall(r"\w+", question.lower(), flags=re.UNICODE))


def _is_near_duplicate(question: str, existing_questions: List[str]) -> bool:
    words = _question_words(question)
    if not words:
        return False
    for other in existing_questions:
        other_words = _question_words(other)
        if not other_words:
            continue
        overlap = len(words & other_words) / min(len(words), len(other_words))
        if overlap >= _DUPLICATE_SIMILARITY_THRESHOLD:
            return True
    return False


def _build_avoid_duplicates_note(asked_questions: List[str]) -> str:
    if not asked_questions:
        return ""
    numbered = "\n".join(f"- {q}" for q in asked_questions)
    return (
        "\n\nKHÔNG lặp lại (kể cả diễn đạt lại) các câu hỏi đã có sau đây:\n"
        f"{numbered}"
    )


def _generate_verified_batch(
    chunks: List[RetrievedChunk],
    llm_client: LLMClient,
    count: int,
    difficulty: Optional[str],
    asked_questions: List[str],
) -> List[QuizItem]:
    """Một lượt sinh + verify — tách khỏi `generate_quiz` để hàm đó gọi lại
    được nhiều lần khi thiếu câu hỏi (BUG-003)."""
    prompt = _build_generator_prompt(chunks, count, difficulty=difficulty) + _build_avoid_duplicates_note(
        asked_questions
    )
    raw_response = llm_client.complete(prompt)
    try:
        raw_items = json.loads(_strip_json_fence(raw_response))
    except (json.JSONDecodeError, TypeError):
        return []

    if not isinstance(raw_items, list):
        return []

    verified_items: List[QuizItem] = []
    # Bắt đầu từ các câu đã có TRƯỚC lượt này (lượt bù trước đó) để dedup xuyên
    # suốt cả lượt hiện tại lẫn các câu vừa verify được TRONG lượt này — không
    # chỉ so đầu-cuối một lượt riêng lẻ.
    seen_questions = list(asked_questions)
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

        if _is_near_duplicate(question, seen_questions):
            continue  # trùng hoặc gần trùng (kể cả diễn đạt lại) -> bỏ, KHÔNG gọi verifier

        chunk = chunks[chunk_index]
        judgment = _parse_judgment(
            llm_client.complete(
                _build_item_judge_prompt(question, options, correct_answer, chunk.text, difficulty)
            )
        )
        if judgment is None or not judgment["valid"] or judgment["ambiguous"]:
            continue  # JSON hỏng, thiếu field, nội dung sai, hoặc câu hỏi mơ hồ -> loại
        if difficulty is not None and not judgment["difficulty_match"]:
            continue  # có yêu cầu độ khó cụ thể nhưng câu hỏi không phù hợp -> loại

        seen_questions.append(question)
        verified_items.append(
            QuizItem(
                question=question,
                options=options,
                correct_answer=correct_answer,
                explanation=explanation,
                source_document=chunk.document_name,
                source_position=chunk.position_ref,
                content_type=judgment["content_type"],
            )
        )

    return verified_items


# BUG-003: LLM/verifier có thể loại bớt câu hỏi (JSON hỏng, thiếu field, chunk
# không hợp lệ, verifier từ chối) khiến kết quả ít hơn num_questions yêu cầu
# mà không có cảnh báo. Bù lại bằng MỘT lượt gọi lại (không phải vòng lặp vô
# hạn) khi lượt đầu có kết quả THẬT (>0) nhưng vẫn thiếu — 0 kết quả nghĩa là
# có vấn đề sâu hơn (prompt/định dạng), gọi lại với cùng ngữ cảnh khó có khả
# năng khác đi, và đã có nhánh lỗi 500 riêng ở router khi kết quả rỗng hoàn
# toàn (app/routers/quiz.py).
_MAX_GENERATION_ATTEMPTS = 2


def generate_quiz(
    chunks: List[RetrievedChunk],
    llm_client: LLMClient,
    num_questions: int = 5,
    difficulty: Optional[str] = None,
) -> List[QuizItem]:
    if not chunks:
        return []

    collected: List[QuizItem] = []

    for attempt in range(_MAX_GENERATION_ATTEMPTS):
        remaining = num_questions - len(collected)
        if remaining <= 0:
            break
        if attempt > 0 and not collected:
            # Lượt đầu ra 0 câu hoàn toàn -> không bù, xem docstring hằng số ở trên.
            break

        # Dedup (trùng y hệt LẪN diễn đạt lại) đã xảy ra BÊN TRONG
        # _generate_verified_batch, xuyên suốt các lượt nhờ asked_questions —
        # batch trả về ở đây chắc chắn không trùng collected.
        batch = _generate_verified_batch(
            chunks, llm_client, remaining, difficulty, [c.question for c in collected]
        )
        collected.extend(batch)

    return collected
