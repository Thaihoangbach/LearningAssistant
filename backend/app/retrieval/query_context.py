"""Bổ sung ngữ cảnh hội thoại vào truy vấn TRUY HỒI.

Vấn đề đang sửa: lịch sử hội thoại được đưa vào prompt của generator
(app/llm/rag.py) nhưng truy hồi lại dùng nguyên văn câu hỏi thô. Khi người
dùng hỏi tiếp "tại sao nó lại tốt hơn?", cả dense retrieval lẫn full-text
search đều đi tìm bằng một chuỗi gần như không có từ nội dung nào, nên lấy về
đoạn không liên quan. Generator có lịch sử nhưng không có đoạn trích đúng —
hoặc từ chối oan, hoặc bịa.

Cố ý KHÔNG gọi LLM để viết lại câu hỏi cho trôi chảy: truy hồi cần TỪ NỘI
DUNG chứ không cần câu văn đúng ngữ pháp, nên chỉ cần ghép thêm từ khoá của
lượt trước là đủ. Đây cũng đúng nguyên tắc chi phí ở PRD §6.

Module thuần, không import gì nặng.
"""

import re
from typing import List, Optional

from app.retrieval.keywords import extract_keywords

# Đại từ và từ chỉ định — dấu hiệu câu hỏi đang trỏ ngược về lượt trước.
#
# Cố ý KHÔNG đưa "thế" trần vào đây: "như thế nào" là từ để hỏi rất phổ biến
# và hoàn toàn không hồi chỉ, đưa vào sẽ đánh dấu nhầm gần như mọi câu hỏi tự
# chứa. Tương tự, "chúng" phải loại trừ "chúng ta/tôi/mình" vì đó là đại từ
# nhân xưng chứ không trỏ về chủ đề đã bàn.
ANAPHORA_RE = re.compile(
    r"(^|\s)("
    r"nó|họ|vậy|đấy|"
    r"chúng(?!\s+(ta|tôi|mình))|"
    r"cái\s+(đó|này|kia|ấy)|điều\s+(đó|này)|phần\s+(đó|này)|"
    r"it|its|they|them|their|this|that|these|those"
    r")(\s|$|\?|,|\.)",
    re.IGNORECASE,
)

# Câu quá ngắn gần như luôn phụ thuộc ngữ cảnh ("còn cái kia?", "vì sao?").
MIN_SELF_CONTAINED_WORDS = 5

MAX_CONTEXT_TERMS = 8


def needs_context(question: str) -> bool:
    """Câu hỏi có vẻ trỏ ngược về lượt trước hay không.

    Cố ý nới rộng một chút: bổ sung thêm vài từ khoá vào truy vấn truy hồi khi
    không cần thiết chỉ làm nhiễu nhẹ, còn bỏ sót một câu hỏi tiếp nối thì mất
    hẳn đoạn trích đúng."""
    stripped = question.strip()
    if not stripped:
        return False
    if len(stripped.split()) < MIN_SELF_CONTAINED_WORDS:
        return True
    return bool(ANAPHORA_RE.search(stripped))


def build_retrieval_query(
    question: str,
    history: Optional[List] = None,
    max_context_terms: int = MAX_CONTEXT_TERMS,
) -> str:
    """Truy vấn dùng cho bước TRUY HỒI. Câu hỏi gốc KHÔNG bị thay đổi và vẫn là
    thứ được đưa vào prompt generator — hàm này chỉ tạo thêm một chuỗi giàu từ
    nội dung hơn để tìm kiếm."""
    stripped = question.strip()
    if not stripped or not history or not needs_context(stripped):
        return question

    already_present = {w.lower() for w in re.findall(r"[\w\-]+", stripped)}

    context_terms: List[str] = []
    # Duyệt từ lượt GẦN NHẤT trở về trước — ngữ cảnh của câu hỏi tiếp nối gần
    # như luôn nằm ở lượt liền trước.
    for turn in reversed(history):
        for source in (getattr(turn, "question", ""), getattr(turn, "answer", "")):
            for term in extract_keywords(source or "").split():
                key = term.lower()
                if key in already_present:
                    continue
                already_present.add(key)
                context_terms.append(term)
                if len(context_terms) >= max_context_terms:
                    return f"{question} {' '.join(context_terms)}"

    if not context_terms:
        return question
    return f"{question} {' '.join(context_terms)}"
