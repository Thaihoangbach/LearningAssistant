"""Gợi ý chủ đề nên học tiếp theo (TC10, TC24) — hoàn toàn rule-based, KHÔNG
gọi LLM, vì chỉ đọc lại MasteryScore đã tính sẵn (app/mastery.py, F4).

TC24 ("recommendation sau quiz") không cần thêm code riêng: MasteryScore được
cập nhật ngay khi nộp quiz (app/routers/quiz.py::submit_attempt), nên lần gọi
build_recommendation() tiếp theo tự động phản ánh kết quả quiz mới nhất.
"""

import re
from dataclasses import dataclass
from typing import List, Optional

_INTENT_RE = re.compile(
    r"nên (học|ôn|tập trung)\s*(vào)?\s*(gì|chủ đề nào|phần nào)|"
    r"học (gì|phần nào|chủ đề nào) tiếp theo|tiếp theo (nên )?học gì|"
    r"what should i (study|learn|focus on) next|which topic should i study",
    re.IGNORECASE,
)

NO_MASTERY_DATA_MESSAGE = (
    "Bạn chưa làm quiz nào để hệ thống đánh giá mức độ thành thạo. Hãy thử làm "
    "một quiz trước, hệ thống sẽ gợi ý chủ đề cần ôn tập dựa trên kết quả đó."
)

_WEAK_THRESHOLD = 0.4


@dataclass
class TopicMastery:
    topic_name: str
    score: float


def is_recommendation_request(question: str) -> bool:
    return bool(_INTENT_RE.search(question))


def build_recommendation(topics: List[TopicMastery]) -> str:
    if not topics:
        return NO_MASTERY_DATA_MESSAGE

    weak = sorted((t for t in topics if t.score < _WEAK_THRESHOLD), key=lambda t: t.score)
    if weak:
        names = ", ".join(f'"{t.topic_name}" ({t.score:.0%})' for t in weak[:3])
        return f"Bạn nên ưu tiên ôn lại: {names} — đây là các chủ đề có điểm thành thạo thấp nhất."

    lowest = min(topics, key=lambda t: t.score)
    return (
        f'Bạn đang nắm khá tốt các chủ đề đã học. Chủ đề thấp điểm nhất hiện tại là '
        f'"{lowest.topic_name}" ({lowest.score:.0%}) — có thể ôn thêm cho chắc, hoặc '
        "chuyển sang chủ đề mới."
    )
