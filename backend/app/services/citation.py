"""Tìm những câu trong đoạn trích thực sự chống đỡ câu trả lời, để giao diện tô
sáng đúng chỗ khi người dùng bấm vào một marker citation.

Tính bằng trùng lặp từ vựng, KHÔNG gọi LLM — đây là một tính năng hiển thị,
không đáng tốn một lượt gọi mô hình cho mỗi lần người dùng mở panel (spec mục
4.3, lớp 2).

Hạn chế đã biết: cách này bỏ sót trường hợp câu trả lời diễn đạt lại hoàn toàn
bằng từ đồng nghĩa. Chấp nhận được vì hậu quả chỉ là không tô sáng được câu
nào — người dùng vẫn đọc được nguyên văn đoạn trích.
"""

import re
from typing import List

# Từ chức năng tiếng Việt và tiếng Anh — trùng nhau ở những từ này không nói
# lên điều gì về nội dung.
_STOPWORDS = {
    "là", "và", "của", "có", "được", "một", "các", "những", "cho", "trong",
    "với", "để", "khi", "này", "đó", "không", "thì", "mà", "ở", "về", "như",
    "đây", "việc", "phần", "câu", "dùng", "the", "a", "an", "is", "are", "of",
    "and", "to", "in", "for", "on", "that", "this", "it", "with", "as", "be",
}

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_WORD_RE = re.compile(r"\w+", re.UNICODE)


def _content_words(text: str) -> set:
    return {w for w in (m.group(0).lower() for m in _WORD_RE.finditer(text)) if w not in _STOPWORDS}


def supporting_sentences(answer: str, chunk_text: str, min_overlap: int = 2) -> List[str]:
    """Trả về các câu trong `chunk_text` chia sẻ ít nhất `min_overlap` từ nội
    dung với `answer`."""
    if not answer.strip() or not chunk_text.strip():
        return []

    answer_words = _content_words(answer)
    if not answer_words:
        return []

    supporting = []
    for sentence in _SENTENCE_SPLIT_RE.split(chunk_text.strip()):
        if not sentence.strip():
            continue
        if len(_content_words(sentence) & answer_words) >= min_overlap:
            supporting.append(sentence.strip())
    return supporting
