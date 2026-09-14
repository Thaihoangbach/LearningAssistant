"""Bóc từ khoá nội dung khỏi câu hỏi, phục vụ lượt truy hồi MỞ RỘNG.

Lượt truy hồi thứ hai ngả về tìm kiếm từ khoá (Postgres full-text search)
thay vì ngữ nghĩa, vì điểm mù cố hữu của truy hồi ngữ nghĩa là thuật ngữ
chính xác xuất hiện đúng một lần ở sâu trong tài liệu — dạng "thông tin bị
chôn" mà lượt một hay bỏ sót.

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

# Hai vế lệnh diễn đạt PHỔ BIẾN và HỢP LỆ trong EdTech (guardrail đã xác
# nhận không phải jailbreak — app/llm/guardrail.py phân biệt rõ "đóng vai
# gia sư" với "đóng vai AI không giới hạn", và "bỏ qua NỘI DUNG TÀI LIỆU"
# với "bỏ qua HƯỚNG DẪN/CHỈ DẪN"), nhưng cả câu lệnh vẫn nằm nguyên trong
# query đưa vào embedding/rerank ở lượt truy hồi — càng dài càng lấn át phần
# "hỏi cái gì thật sự", làm loãng điểm liên quan tới đúng đoạn trích cần tìm
# (Golden Set eval/reports/failure_analysis.md, việc còn lại #2 — case
# EDU-GRD2-017/EDU-GRD2-009 bị từ chối dù tài liệu có nội dung, xác nhận qua
# retest live). Mỗi mẫu chỉ xoá ĐÚNG cụm lệnh đã biết, không đoán/cắt phần
# nào khác của câu — cùng nguyên tắc "chặn nhiễu RÕ RÀNG, không suy diễn"
# dùng ở app/ingestion/outline.py::is_plausible_topic.
_META_INSTRUCTION_PATTERNS = [
    re.compile(
        r"(đóng vai|hãy đóng vai|roleplay as|act as|pretend (to be |you are )?|"
        r"imagine you are|giả sử bạn là|hãy tưởng tượng bạn là)\b[^,]*,?\s*",
        re.IGNORECASE,
    ),
    re.compile(r"bỏ qua nội dung tài liệu( đi)?,?\s*", re.IGNORECASE),
    re.compile(
        r"chỉ dựa vào kiến thức chung( của (bạn|mô hình))?( để trả lời)?( câu hỏi)?( về)?\s*",
        re.IGNORECASE,
    ),
    re.compile(r"ignore the document[s]?( content)?,?\s*", re.IGNORECASE),
    re.compile(
        r"(just |only )?(use|rely on) (your )?general knowledge( only)?( to answer)?\s*",
        re.IGNORECASE,
    ),
]


def strip_roleplay_preamble(query: str) -> str:
    """Xoá các vế lệnh diễn đạt đã biết (đóng vai .../bỏ qua tài liệu, chỉ
    dùng kiến thức chung...) khỏi câu hỏi, dùng để dựng truy vấn cho lượt
    truy hồi MỞ RỘNG (xem app/retrieval/pipeline.py). Trả lại nguyên câu hỏi
    nếu không khớp mẫu nào, hoặc nếu xoá xong không còn gì (câu hỏi CHỈ có
    mỗi vế lệnh, không có nội dung nào khác để giữ)."""
    result = query
    for pattern in _META_INSTRUCTION_PATTERNS:
        result = pattern.sub("", result)
    result = result.strip(" ,")
    return result or query


def extract_keywords(query: str) -> str:
    """Giữ nguyên chữ hoa/thường của từ gốc — thuật ngữ như RRF, CNN, LSTM mất
    ý nghĩa nếu bị hạ về chữ thường trước khi đưa vào truy vấn full-text
    search."""
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
