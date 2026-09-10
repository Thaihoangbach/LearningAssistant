"""Rule-based policy — quyết định hành động ưu tiên tiếp theo (Quiz/
Flashcard/Learn) cho MỘT chủ đề, dựa trên Learning State
(app/services/learning_state.py).

CỐ Ý dùng luật tường minh (if/elif), KHÔNG dùng công thức trọng số hay ML —
dễ giải thích, dễ debug, dễ đánh giá hơn khi còn ít dữ liệu thực tế để tune
một mô hình. `reason` luôn là câu tiếng Việt đọc được trực tiếp, để UI hiển
thị "vì sao được đề xuất" (nguyên tắc AI đề xuất, học sinh kiểm soát) mà
không cần dịch lại từ mã hành động ở tầng frontend.
"""

from dataclasses import dataclass
from typing import Optional

from app.services.learning_state import LearningState
from app.services.mastery import classify_mastery


@dataclass
class PolicyRecommendation:
    action: Optional[str]  # "quiz" | "flashcard" | "learn" | None
    reason: str


def recommend_action(state: LearningState) -> PolicyRecommendation:
    comprehension_label = (
        classify_mastery(state.comprehension) if state.comprehension is not None else None
    )
    retention_label = classify_mastery(state.retention) if state.retention is not None else None

    if comprehension_label is None and retention_label is None:
        return PolicyRecommendation(
            action="learn",
            reason="Chưa có dữ liệu học tập cho chủ đề này, nên bắt đầu học.",
        )

    comprehension_weak = comprehension_label == "yếu"
    retention_weak = retention_label == "yếu"

    if comprehension_weak and retention_weak:
        return PolicyRecommendation(
            action="learn",
            reason="Cả mức hiểu và mức nhớ đều đang yếu, nên học lại từ đầu.",
        )
    if comprehension_weak:
        return PolicyRecommendation(
            action="quiz",
            reason=f"Điểm hiểu bài đang yếu ({state.comprehension:.0%}), nên làm quiz để kiểm tra lại.",
        )
    if retention_weak:
        return PolicyRecommendation(
            action="flashcard",
            reason=f"Khả năng ghi nhớ đang yếu ({state.retention:.0%}), nên ôn flashcard.",
        )
    return PolicyRecommendation(
        action=None,
        reason="Chủ đề đã ổn, không cần ưu tiên ôn tập ngay.",
    )
