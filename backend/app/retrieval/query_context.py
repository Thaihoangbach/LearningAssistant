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

# Dấu hiệu một chủ thể đã được nêu tên NGAY TRONG câu hỏi hiện tại — dùng để
# loại trừ false-positive của has_unresolved_reference() cho câu ghép kiểu
# "Gradient descent là gì, và nó luôn tìm được cực tiểu toàn cục, đúng
# không?" (EDU-GRD-022): "nó" ở đây trỏ về "Gradient descent" nêu ngay trước
# đó trong CÙNG câu hỏi, không cần lịch sử hội thoại.
_DEFINITION_ANTECEDENT_RE = re.compile(r"là\s+gì\b", re.IGNORECASE)

# Ngưỡng TỔNG QUÁT hơn cho cùng vấn đề ở trên, không giới hạn ở đúng cụm "là
# gì" — bắt bất kỳ câu hỏi GHÉP nào có mệnh đề đầu đủ dài để chứa chủ thể
# thật trước khi đại từ xuất hiện ở mệnh đề sau (vd "X được định nghĩa như
# thế nào và nó...?", "What is safe reinforcement learning (SRL), and how
# does risk-averse RL differ from it?", "...random forest, and how can this
# number be optimized?"). Phát hiện qua Golden Set live (2026-09-16, hồi quy
# rag_qa 97.8%→80%/retrieval 91.4%→80% sau khi thêm has_unresolved_reference
# ở phiên trước): 11 case rag_qa/retrieval trước đó PASS bị chặn oan vì
# _DEFINITION_ANTECEDENT_RE chỉ bắt đúng 1 cụm từ, không tổng quát cho câu
# ghép tiếng Anh hay câu ghép không dùng "là gì".
#
# Đối chiếu SỐ TỪ THÔ (không lọc stopword — lọc stopword không an toàn ở đây,
# xem bên dưới) đứng TRƯỚC đại từ, trên toàn bộ case đã biết:
#   - True positive (đúng là mồ côi, phải chặn): EDU-ABS-008 "Ai đã phát
#     minh ra nó?" — 5 từ trước "nó", KHÔNG có chủ thể nào (toàn từ để hỏi).
#   - False positive vừa sửa: thấp nhất là 9 từ trước đại từ (EDU-QA-028
#     "What is mean decrease in impurity, and where is it...", EDU-QA-043
#     "When were InstructGPT and ChatGPT released, and how were they...").
# Chọn ngưỡng 7 — nằm giữa, cách đều 2 phía để có biên an toàn, và CỐ Ý
# không lọc theo _STOPWORDS của extract_keywords() vì danh sách đó phục vụ
# truy hồi (giữ lại rất nhiều từ để hỏi như "ai", "đã", "ra" — thử qua
# EDU-ABS-008 cho thấy lọc kiểu đó vẫn còn 5 "từ nội dung", làm ngưỡng mất
# tác dụng phân biệt) — đếm từ thô đơn giản hơn và đã kiểm chứng đủ tách biệt
# 2 nhóm case thật.
_MIN_WORDS_FOR_INQUESTION_ANTECEDENT = 7


def _has_named_antecedent_in_question(prefix: str) -> bool:
    """Mệnh đề TRƯỚC đại từ, trong CÙNG câu hỏi, có đủ dài để đã nêu tên một
    chủ thể cụ thể hay chưa — xem giải thích ngưỡng ở
    _MIN_WORDS_FOR_INQUESTION_ANTECEDENT."""
    return len(prefix.split()) >= _MIN_WORDS_FOR_INQUESTION_ANTECEDENT

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


def has_unresolved_reference(question: str, history: Optional[List] = None) -> bool:
    """Câu hỏi dùng đại từ/chỉ định từ (ANAPHORA_RE) mà KHÔNG có antecedent nào
    để giải — dấu hiệu retrieval sắp phải "tự chọn" một đối tượng thay vì tìm
    đúng cái người dùng hỏi (eval/reports/failure_analysis.md Phát hiện #1,
    case EDU-ABS-008/009/012/013: "Ai đã phát minh ra nó?" không có lượt
    trước, hệ thống vẫn tìm được MỘT đoạn "phát minh" nào đó rồi trả lời tự
    tin — false grounding, nguy hiểm hơn từ chối "không tìm thấy" thông
    thường vì trông có căn cứ).

    Cố ý CHỈ dùng ANAPHORA_RE (đại từ/chỉ định từ THẬT SỰ xuất hiện), không
    dùng `needs_context()` (còn bắt cả câu ngắn <5 từ không có đại từ nào) —
    dùng needs_context() ở đây sẽ chặn oan hàng loạt câu ngắn tự đủ nghĩa
    hợp lệ (vd "Kernel là gì?", "Overfitting là gì?" — cả hai đều đang PASS).

    True khi: có đại từ/chỉ định từ VÀ (không có lịch sử hội thoại HOẶC lịch
    sử không có từ nội dung nào để bổ sung — `build_retrieval_query` trả về
    y hệt câu hỏi gốc). KHÔNG phân biệt được trường hợp lịch sử có NHIỀU đối
    tượng khiến đại từ vẫn mơ hồ dù "giải được" về mặt từ khoá — giới hạn đã
    biết, chưa có case thật trong Golden Set để kiểm chứng hướng xử lý.

    Ngoại lệ đã xác nhận qua Golden Set live (EDU-GRD-022): câu ghép kiểu "X
    là gì, và nó có Y không?" có antecedent nằm NGAY TRONG CÙNG câu hỏi (X),
    không cần lịch sử hội thoại — kiểm tra cụm "là gì" xuất hiện TRƯỚC đại từ
    trong cùng câu hỏi trước khi cần tới lịch sử.

    Ngoại lệ tổng quát hơn (xác nhận qua Golden Set live 2026-09-16, xem
    _MIN_WORDS_FOR_INQUESTION_ANTECEDENT): bất kỳ câu hỏi ghép nào có mệnh đề
    trước đủ dài (>=7 từ thô) trước đại từ cũng được coi là đã có chủ thể nêu
    tên trong cùng câu hỏi, không giới hạn ở đúng cụm "là gì" — bắt thêm cả
    câu ghép tiếng Anh và câu ghép tiếng Việt không dùng "là gì". Biết trước
    một khoảng trống chưa xử lý: đại từ quan hệ tiếng Anh "that" gắn liền
    ngay sau danh từ nó bổ nghĩa với mệnh đề TRƯỚC rất ngắn (vd "trees that
    are grown very deep...", <7 từ) vẫn bị ANAPHORA_RE coi nhầm là chỉ định
    từ hồi chỉ — ANAPHORA_RE hiện không phân biệt được "that" làm đại từ
    quan hệ với "that" hồi chỉ, và case này hiếm/không đáng để đổi cấu trúc
    regex thêm rủi ro cho các trường hợp khác đang đúng."""
    stripped = question.strip()
    if not stripped or not ANAPHORA_RE.search(stripped):
        return False
    match = ANAPHORA_RE.search(stripped)
    prefix = stripped[: match.start()]
    if _DEFINITION_ANTECEDENT_RE.search(prefix) or _has_named_antecedent_in_question(prefix):
        return False
    if not history:
        return True
    enriched = build_retrieval_query(question, history)
    return enriched.strip() == stripped
