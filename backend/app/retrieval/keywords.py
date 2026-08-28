"""Bóc từ khoá nội dung khỏi câu hỏi, phục vụ lượt truy hồi MỞ RỘNG.

Lượt truy hồi thứ hai ngả về BM25 theo từ khoá thay vì ngữ nghĩa, vì điểm mù
cố hữu của truy hồi ngữ nghĩa là thuật ngữ chính xác xuất hiện đúng một lần ở
sâu trong tài liệu — dạng "thông tin bị chôn" mà lượt một hay bỏ sót.

Module thuần, không import gì nặng, để test được độc lập.
"""

import re
from typing import List

_STOPWORDS = {
    "là", "gì", "và", "của", "có", "được", "một", "các", "những", "cho",
    "trong", "với", "để", "khi", "này", "đó", "không", "thì", "mà", "ở",
    "về", "như", "thế", "nào", "sao", "tôi", "bạn", "hãy", "biết",
    "what", "is", "are", "the", "a", "an", "of", "and", "to", "in", "for",
    "how", "does", "do", "me", "tell", "about", "explain",
}

_WORD_RE = re.compile(r"[\w\-]+", re.UNICODE)


def extract_keywords(query: str) -> str:
    """Giữ nguyên chữ hoa/thường của từ gốc — thuật ngữ như BM25, RRF, CNN mất
    ý nghĩa nếu bị hạ về chữ thường trước khi đưa cho BM25."""
    if not query.strip():
        return ""

    kept: List[str] = [
        m.group(0) for m in _WORD_RE.finditer(query) if m.group(0).lower() not in _STOPWORDS
    ]
    if not kept:
        # Bỏ hết thì truy vấn thành rỗng và lượt mở rộng sẽ vô dụng — thà dùng
        # lại nguyên câu hỏi.
        return query
    return " ".join(kept)
