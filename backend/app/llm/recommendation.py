"""Gợi ý chủ đề nên học tiếp theo (TC10, TC24) — hoàn toàn rule-based, KHÔNG
gọi LLM, vì chỉ đọc lại MasteryScore đã tính sẵn (app/services/mastery.py, F4).

TC24 ("recommendation sau quiz") không cần thêm code riêng: MasteryScore được
cập nhật ngay khi nộp quiz (app/routers/quiz.py::submit_attempt), nên lần gọi
build_recommendation() tiếp theo tự động phản ánh kết quả quiz mới nhất.
"""

import re
from dataclasses import dataclass
from typing import Dict, List, Optional

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


# Số mẩu ký ức tối đa nêu làm lý do — nhiều hơn thì gợi ý biến thành một bản
# liệt kê lỗi, đọc mệt và mất trọng tâm.
MAX_EVIDENCE_SHOWN = 2


def _evidence_line(topic_name: str, evidence_by_topic: Optional[Dict[str, List[str]]]) -> str:
    """Lý do một chủ đề bị coi là yếu, lấy từ ký ức episodic (giai đoạn A).

    Đây là điểm khác biệt so với bản cũ: trước đây chỉ nói "chủ đề này điểm
    thấp", giờ nói được ĐÃ SAI Ở ĐÂU."""
    if not evidence_by_topic:
        return ""
    items = evidence_by_topic.get(topic_name) or []
    if not items:
        return ""
    shown = "; ".join(items[:MAX_EVIDENCE_SHOWN])
    return f"Cụ thể, trước đây bạn: {shown}."


def build_recommendation(
    topics: List[TopicMastery],
    evidence_by_topic: Optional[Dict[str, List[str]]] = None,
    due_flashcards: int = 0,
) -> str:
    if not topics:
        return NO_MASTERY_DATA_MESSAGE

    weak = sorted((t for t in topics if t.score < _WEAK_THRESHOLD), key=lambda t: t.score)
    focus = weak[0] if weak else min(topics, key=lambda t: t.score)

    if weak:
        names = ", ".join(f'"{t.topic_name}" ({t.score:.0%})' for t in weak[:3])
        lines = [f"Bạn nên ưu tiên ôn lại: {names} — đây là các chủ đề có điểm thành thạo thấp nhất."]
    else:
        lines = [
            f'Bạn đang nắm khá tốt các chủ đề đã học. Chủ đề thấp điểm nhất hiện tại là '
            f'"{focus.topic_name}" ({focus.score:.0%}) — có thể ôn thêm cho chắc, hoặc '
            "chuyển sang chủ đề mới."
        ]

    evidence = _evidence_line(focus.topic_name, evidence_by_topic)
    if evidence:
        lines.append(evidence)

    actions = [f'làm một quiz mức intermediate về "{focus.topic_name}"']
    if due_flashcards > 0:
        actions.append(f"ôn {due_flashcards} thẻ flashcard đang đến hạn")
    actions.append("đọc lại đoạn tài liệu nguồn của những câu bạn đã trả lời sai")
    lines.append("Việc nên làm tiếp: " + "; ".join(actions) + ".")

    return " ".join(lines)
