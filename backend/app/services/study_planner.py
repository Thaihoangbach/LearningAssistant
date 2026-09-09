"""Lập kế hoạch học tập (TC15, TC16) — rule-based, KHÔNG lưu bảng StudyPlan
riêng. Kế hoạch được TÍNH LẠI TOÀN BỘ mỗi lần gọi từ Topic/MasteryScore hiện
có (app/services/mastery.py, F4) — nhờ vậy khi tiến độ người học thay đổi
(hoàn thành chủ đề, làm thêm quiz), lần gọi tiếp theo tự động phản ánh đúng,
không cần đồng bộ trạng thái kế hoạch cũ (TC16) hay migrate schema riêng cho
tính năng này (TC15).

Nguyên tắc phân bổ: chủ đề CHƯA có điểm mastery (chưa từng làm quiz) và chủ đề
điểm thấp được ưu tiên xếp trước; chia đều số chủ đề còn lại theo số ngày còn
lại tới hạn.
"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class TopicPriority:
    topic_name: str
    score: Optional[float]  # None = chưa có dữ liệu mastery (chủ đề mới/chưa học)
    # Thứ tự chủ đề trong tài liệu gốc (app/ingestion/outline.py). Đây là một
    # dạng phụ thuộc trước-sau CHO KHÔNG: tác giả tài liệu đã sắp sẵn thứ tự
    # hợp lý để học, nên dùng nó thay vì phải xây đồ thị tiên quyết — thứ mà
    # PRD đã cố tình để ngoài phạm vi vì không có nguồn dữ liệu.
    order_index: Optional[int] = None


# HAI nhóm ưu tiên, không phải ba. "Chưa học" và "đã học nhưng đã quên" được
# gộp làm một vì về mặt sư phạm chúng giống nhau: đều cần học lại từ đầu.
#
# Tách chúng ra từng gây đúng lỗi mà thứ tự tài liệu sinh ra để tránh: một chủ
# đề nền tảng đã rơi xuống 11% bị xếp SAU các chủ đề dựa trên nó chỉ vì những
# chủ đề kia chưa từng học. Gộp lại thì trong cùng nhóm "cần học", thứ tự tài
# liệu quyết định — nền tảng luôn đứng trước phần dựa trên nó.
_BAND_NEEDS_WORK = 0
_BAND_REST = 1
_WEAK_THRESHOLD = 0.4
_NO_ORDER = 10**6

# Lưới an toàn cuối cùng cho BUG-001: dù topic đã qua lọc chất lượng
# (app/ingestion/outline.py::is_plausible_topic) ở tầng gọi, một tài khoản có
# nhiều tài liệu vẫn có thể dồn về hàng trăm Topic hợp lệ — chia hết cho vài
# ngày sẽ ra một "kế hoạch" dài không dùng được. Giữ lại nhóm ưu tiên cao nhất
# (yếu/chưa học trước, theo đúng thứ tự đã sắp) thay vì cắt ngẫu nhiên.
_MAX_PLAN_TOPICS = 60


def _priority_band(score: Optional[float]) -> int:
    if score is None or score < _WEAK_THRESHOLD:
        return _BAND_NEEDS_WORK
    return _BAND_REST


@dataclass
class DayPlan:
    day: int
    topics: List[str]


def generate_plan(topics: List[TopicPriority], days: int) -> List[DayPlan]:
    if days <= 0 or not topics:
        return []

    ordered = sorted(
        topics,
        key=lambda t: (
            _priority_band(t.score),
            t.order_index if t.order_index is not None else _NO_ORDER,
            t.score if t.score is not None else 0.0,
        ),
    )[:_MAX_PLAN_TOPICS]

    plan = [DayPlan(day=d, topics=[]) for d in range(1, days + 1)]
    for i, topic in enumerate(ordered):
        plan[i % days].topics.append(topic.topic_name)

    return [d for d in plan if d.topics]
