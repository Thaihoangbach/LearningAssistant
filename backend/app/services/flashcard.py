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
