"""Nhận diện ý định của câu hỏi để chọn năng lực xử lý — thay cho chuỗi if/else.

Trước module này, `app/routers/chat.py` phân nhánh thủ công bằng đúng một phép
kiểm tra (`is_recommendation_request`), và hệ quả lộ ra ngay: người dùng gõ
"tôi còn 5 ngày nữa thi, ôn thế nào cho kịp?" thì KHÔNG có gì dẫn sang bộ lập
kế hoạch, dù backend đã có sẵn nó. Mỗi năng lực mới lại là một nhánh `elif`
nữa, và sớm muộn sẽ có năng lực bị quên nối vào.

Ở đây năng lực được khai báo thành DỮ LIỆU. Thêm một năng lực là thêm một phần
tử vào `CAPABILITIES`, không phải sửa luồng điều khiển của router.

Nhận diện bằng regex, KHÔNG gọi LLM — cùng nguyên tắc rẻ-trước-đắt-sau mà
`app/llm/guardrail.py` đã áp dụng. Câu hỏi không khớp năng lực nào thì rơi về
đường hỏi đáp có căn cứ mặc định, tức là đường AN TOÀN NHẤT: nó là đường duy
nhất bắt buộc đi qua generator + verifier. Cố ý thiết kế như vậy — điều phối
thì linh hoạt, nhưng đường sinh câu trả lời có căn cứ thì cố định, để điều
kiện chặn "0 kết luận không có trích dẫn" của PRD §7 không bị hở.
"""

import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from app.llm.recommendation import is_recommendation_request

DEFAULT_PLAN_DAYS = 7
# Kế hoạch dài hơn ngưỡng này gần như chắc chắn là người dùng gõ nhầm số, và
# chia lịch cho hàng nghìn ngày chỉ tạo ra một bảng vô nghĩa.
MAX_PLAN_DAYS = 60

_DAYS_RE = re.compile(r"(\d{1,4})\s*(ngày|hôm|day|days)", re.IGNORECASE)

_PLAN_INTENT_RE = re.compile(
    r"kế hoạch ôn|lập lịch|chia lịch|ôn (thế nào|sao|kiểu gì) cho kịp|"
    r"còn\s+\d+\s*(ngày|hôm)|sắp thi|trước kỳ thi|study plan|revision plan|"
    r"plan (my|the) (study|revision)",
    re.IGNORECASE,
)

_FLASHCARD_DUE_RE = re.compile(
    r"thẻ nào (đến hạn|cần ôn)|đến hạn ôn|bao nhiêu thẻ|thẻ cần ôn|"
    r"hôm nay ôn gì|cards? (are )?due|due cards?",
    re.IGNORECASE,
)


@dataclass
class CapabilityMatch:
    name: str
    params: dict = field(default_factory=dict)


@dataclass
class Capability:
    name: str
    description: str
    # True = đầu ra sinh từ tài liệu nên BẮT BUỘC qua generator + verifier.
    # False = chỉ đọc lại dữ liệu đã tính sẵn, không có gì để bịa.
    needs_grounding: bool
    detect: Callable[[str], Optional[dict]]


def _extract_days(question: str) -> int:
    match = _DAYS_RE.search(question)
    if not match:
        return DEFAULT_PLAN_DAYS
    days = int(match.group(1))
    return max(1, min(days, MAX_PLAN_DAYS))


def _detect_study_plan(question: str) -> Optional[dict]:
    if not _PLAN_INTENT_RE.search(question):
        return None
    return {
        "days": _extract_days(question),
        # Nhiều hơn 1 lần nhắc "N ngày" trong cùng câu hỏi là dấu hiệu người
        # dùng cần lịch cho NHIỀU môn/nhiều hạn khác nhau — vượt khả năng một
        # chat capability đơn-hạn (app/routers/chat.py::
        # _build_study_plan_result). Vẫn thuần regex, không LLM.
        "multiple_days_mentioned": len(_DAYS_RE.findall(question)) > 1,
    }


def _detect_recommendation(question: str) -> Optional[dict]:
    return {} if is_recommendation_request(question) else None


def _detect_flashcard_due(question: str) -> Optional[dict]:
    return {} if _FLASHCARD_DUE_RE.search(question) else None


# Thứ tự có ý nghĩa: câu vừa hỏi "nên ôn gì" vừa nêu thời hạn thì một kế hoạch
# chia theo ngày hữu ích hơn hẳn một gợi ý chung chung, nên study_plan đứng
# trước recommendation.
CAPABILITIES: List[Capability] = [
    Capability(
        name="study_plan",
        description="Lập kế hoạch ôn tập theo số ngày còn lại tới hạn",
        needs_grounding=False,
        detect=_detect_study_plan,
    ),
    Capability(
        name="recommendation",
        description="Gợi ý chủ đề nên học tiếp theo dựa trên mức thành thạo",
        needs_grounding=False,
        detect=_detect_recommendation,
    ),
    Capability(
        name="flashcard_due",
        description="Cho biết còn bao nhiêu thẻ flashcard đến hạn ôn",
        needs_grounding=False,
        detect=_detect_flashcard_due,
    ),
]

CAPABILITY_NAMES = [c.name for c in CAPABILITIES]
CAPABILITY_BY_NAME: Dict[str, Capability] = {c.name: c for c in CAPABILITIES}


def detect_capability(question: str) -> Optional[CapabilityMatch]:
    """Năng lực xử lý câu hỏi này, hoặc None để rơi về hỏi đáp có căn cứ."""
    if not question or not question.strip():
        return None

    for capability in CAPABILITIES:
        params = capability.detect(question)
        if params is not None:
            return CapabilityMatch(name=capability.name, params=params)
    return None
