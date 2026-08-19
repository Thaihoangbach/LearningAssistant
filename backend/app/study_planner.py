"""Lập kế hoạch học tập (TC15, TC16) — rule-based, KHÔNG lưu bảng StudyPlan
riêng. Kế hoạch được TÍNH LẠI TOÀN BỘ mỗi lần gọi từ Topic/MasteryScore hiện
có (app/mastery.py, F4) — nhờ vậy khi tiến độ người học thay đổi (hoàn thành
chủ đề, làm thêm quiz), lần gọi tiếp theo tự động phản ánh đúng, không cần
đồng bộ trạng thái kế hoạch cũ (TC16) hay migrate schema riêng cho tính năng
này (TC15).

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


@dataclass
class DayPlan:
    day: int
    topics: List[str]


def generate_plan(topics: List[TopicPriority], days: int) -> List[DayPlan]:
    if days <= 0 or not topics:
        return []

    # Chủ đề chưa có điểm (None) ưu tiên như điểm 0 (chưa học = cần học sớm),
    # rồi tới điểm thấp nhất trước.
    ordered = sorted(topics, key=lambda t: t.score if t.score is not None else 0.0)

    plan = [DayPlan(day=d, topics=[]) for d in range(1, days + 1)]
    for i, topic in enumerate(ordered):
        plan[i % days].topics.append(topic.topic_name)

    return [d for d in plan if d.topics]
