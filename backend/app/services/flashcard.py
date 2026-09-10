"""Truy vấn trạng thái ôn tập của flashcard — dùng chung giữa router flashcard
và phần gợi ý học tập.

Tách ra thành module riêng vì cả app/routers/flashcard.py lẫn
app/routers/chat.py đều cần biết "người này còn bao nhiêu thẻ đến hạn"; để một
router import router kia là kiểu phụ thuộc vòng chực chờ xảy ra.

Gộp "lượt ôn mới nhất của mỗi thẻ" trong Python thay vì bằng một truy vấn SQL
con: quy mô MVP mỗi người vài trăm thẻ, và cách này đọc dễ hơn hẳn một câu
window function.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from app.models import FlashcardItem, FlashcardReview, FlashcardSet

DEFAULT_DUE_LIMIT = 20

# Ngưỡng "đã thuộc lâu dài" kiểu Anki (mature card): interval >= 21 ngày nghĩa
# là ba lần ôn liên tiếp đều đạt "good" trở lên từ mức khởi điểm, đủ bằng
# chứng để coi là nhớ chắc thay vì còn đang học.
MASTERED_INTERVAL_DAYS = 21


def _to_naive_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=None) if value.tzinfo is not None else value


def latest_review_by_item(db, user_id: str) -> Dict[str, FlashcardReview]:
    """Lượt ôn MỚI NHẤT của từng thẻ — đây là trạng thái hiện tại của thẻ đó."""
    reviews = (
        db.query(FlashcardReview)
        .filter(FlashcardReview.user_id == user_id)
        .order_by(FlashcardReview.reviewed_at.asc())
        .all()
    )
    latest: Dict[str, FlashcardReview] = {}
    for r in reviews:
        latest[r.flashcard_item_id] = r  # lượt sau ghi đè lượt trước
    return latest


def _user_items(db, user_id: str) -> List[FlashcardItem]:
    return (
        db.query(FlashcardItem)
        .join(FlashcardSet, FlashcardItem.flashcard_set_id == FlashcardSet.id)
        .filter(FlashcardSet.user_id == user_id)
        .all()
    )


def due_items(
    db, user_id: str, now: Optional[datetime] = None, limit: int = DEFAULT_DUE_LIMIT
) -> List[Tuple[FlashcardItem, Optional[FlashcardReview]]]:
    """Thẻ CHƯA từng ôn, hoặc đã tới hạn ôn lại. Trả kèm lượt ôn gần nhất để
    phía gọi biết interval/ease hiện tại mà không phải truy vấn lại."""
    now = _to_naive_utc(now or datetime.now(timezone.utc))
    latest = latest_review_by_item(db, user_id)

    due: List[Tuple[FlashcardItem, Optional[FlashcardReview]]] = []
    for item in _user_items(db, user_id):
        review = latest.get(item.id)
        if review is None or _to_naive_utc(review.next_due_at) <= now:
            due.append((item, review))
        if len(due) >= limit:
            break
    return due


def count_due(db, user_id: str, now: Optional[datetime] = None) -> int:
    # limit rất lớn để đếm được toàn bộ, không bị chặn bởi DEFAULT_DUE_LIMIT
    return len(due_items(db, user_id, now=now, limit=10**6))


def classify_status(review: Optional[FlashcardReview], now: datetime) -> str:
    """"due" | "learning" | "mastered" — CHIA BA, không chồng lắp, cho MỘT
    thẻ dựa trên lượt ôn GẦN NHẤT của nó (hoặc None nếu chưa ôn lần nào).
    Khác due_items() (chỉ lọc thẻ đến hạn), hàm này phân loại MỌI thẻ để dựng
    bảng tiến độ tổng quan (app/routers/flashcard.py::get_board).

    Đến hạn LUÔN thắng bất kể interval đã dài bao nhiêu — một thẻ "đã thuộc"
    nhưng tới hạn vẫn cần ôn ngay, không được xếp nhầm sang "mastered" khiến
    người học tưởng không cần động vào."""
    if review is None or _to_naive_utc(review.next_due_at) <= now:
        return "due"
    if review.interval_days >= MASTERED_INTERVAL_DAYS:
        return "mastered"
    return "learning"


def board(
    db, user_id: str, now: Optional[datetime] = None
) -> Dict[str, List[Tuple[FlashcardItem, Optional[FlashcardReview]]]]:
    """Toàn bộ thẻ của người dùng, chia vào đúng MỘT trong ba nhóm
    due/learning/mastered — dùng cho màn tổng quan tiến độ ôn tập."""
    now = _to_naive_utc(now or datetime.now(timezone.utc))
    latest = latest_review_by_item(db, user_id)

    buckets: Dict[str, List[Tuple[FlashcardItem, Optional[FlashcardReview]]]] = {
        "due": [], "learning": [], "mastered": [],
    }
    for item in _user_items(db, user_id):
        review = latest.get(item.id)
        buckets[classify_status(review, now)].append((item, review))
    return buckets
