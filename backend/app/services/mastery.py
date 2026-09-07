"""Tính mức độ thành thạo theo chủ đề (F4) — công thức rule-based đơn giản.

Đây là quyết định đã chốt trong kịch bản hạ cấp của PRD: KHÔNG dùng mô hình
Knowledge Tracing học sâu (kiểu MLFBK trong TutorLLM) ở MVP, mà dùng trọng
số suy giảm theo thời gian (recency-weighted average) — dễ hiểu, dễ giải
thích cho người dùng, và đủ để phục vụ F4/F5/F7.

Công thức: mỗi lượt làm bài đúng góp +1, sai góp 0, nhưng lượt càng gần đây
càng có trọng số cao hơn (nửa chu kỳ suy giảm 14 ngày) để phản ánh đúng
trạng thái "hiện tại" thay vì coi mọi lượt làm bài quan trọng như nhau.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

HALF_LIFE_DAYS = 14.0

# Bán rã của việc QUÊN khi không luyện tập. Khác hẳn HALF_LIFE_DAYS ở trên:
# HALF_LIFE_DAYS cân trọng số giữa các lượt làm bài ĐÃ CÓ, còn hằng số này mô
# tả kiến thức phai đi khi KHÔNG có lượt nào mới.
MASTERY_HALF_LIFE_DAYS = 30.0

# Trọng số bất đối xứng theo trực giác đo lường: làm ĐÚNG câu KHÓ là bằng chứng
# mạnh về năng lực, làm SAI câu DỄ là bằng chứng mạnh về lỗ hổng. Hai trường
# hợp còn lại (đúng câu dễ, sai câu khó) nói lên ít hơn nhiều.
DIFFICULTY_WEIGHT = {"beginner": 0.7, "intermediate": 1.0, "advanced": 1.4}
DEFAULT_DIFFICULTY_WEIGHT = 1.0


@dataclass
class Attempt:
    is_correct: bool
    attempted_at: datetime
    difficulty: Optional[str] = None


def _to_naive_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=None) if value.tzinfo is not None else value


def _recency_weight(attempted_at: datetime, now: datetime) -> float:
    # Attempt.attempted_at đọc từ DB luôn là naive (cột SQLAlchemy DateTime
    # không khai báo timezone=True không giữ tzinfo khi round-trip), trong khi
    # `now` mặc định ở dưới là aware — chuẩn hoá cả hai về naive trước khi trừ
    # để không crash khi trộn hai kiểu.
    age_days = max((_to_naive_utc(now) - _to_naive_utc(attempted_at)).total_seconds() / 86400.0, 0.0)
    return 0.5 ** (age_days / HALF_LIFE_DAYS)


def _difficulty_weight(attempt: Attempt) -> float:
    base = DIFFICULTY_WEIGHT.get(
        (attempt.difficulty or "").strip().lower(), DEFAULT_DIFFICULTY_WEIGHT
    )
    # Đúng câu khó -> trọng số cao. Sai câu dễ -> cũng trọng số cao, vì đó là
    # tín hiệu hổng kiến thức rõ hơn hẳn việc sai một câu khó.
    return base if attempt.is_correct else 1.0 / base


def decay_unpractised(
    score: float, updated_at: Optional[datetime], now: Optional[datetime] = None
) -> float:
    """Điểm mastery ước lượng ở HIỆN TẠI, sau khi tính đến việc lâu không luyện.

    Tính LÚC ĐỌC, không bao giờ ghi ngược xuống DB — ghi ngược sẽ khiến phân rã
    cộng dồn mỗi lần đọc và điểm tụt về 0 rất nhanh một cách sai lệch.

    Nhờ hàm này, một chủ đề từng đạt 90% nhưng ba tháng không đụng tới sẽ tự
    trôi xuống nhóm "yếu" và được gợi ý ôn lại — trước đây nó ở nguyên 90% mãi
    mãi nên không bao giờ được nhắc, dù đó chính là lúc quên rơi vào.
    """
    if updated_at is None:
        return score

    now = now or datetime.now(timezone.utc)
    age_days = max((_to_naive_utc(now) - _to_naive_utc(updated_at)).total_seconds() / 86400.0, 0.0)
    decayed = score * (0.5 ** (age_days / MASTERY_HALF_LIFE_DAYS))
    return max(0.0, min(1.0, decayed))


def compute_mastery(attempts: List[Attempt], now: Optional[datetime] = None) -> Optional[float]:
    """Trả về điểm mastery trong khoảng [0, 1], hoặc None nếu chưa có dữ liệu."""
    if not attempts:
        return None

    now = now or datetime.now(timezone.utc)
    total_weight = 0.0
    weighted_correct = 0.0

    for a in attempts:
        w = _recency_weight(a.attempted_at, now) * _difficulty_weight(a)
        total_weight += w
        if a.is_correct:
            weighted_correct += w

    if total_weight == 0:
        return None

    score = weighted_correct / total_weight
    return max(0.0, min(1.0, score))


def classify_mastery(score: float) -> str:
    if score >= 0.75:
        return "tốt"
    if score >= 0.4:
        return "trung bình"
    return "yếu"
