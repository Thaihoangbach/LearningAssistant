# Giai đoạn B — Vòng ôn tập: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Biến flashcard từ một danh sách sinh ra rồi bỏ đó thành một vòng ôn
tập có lịch lặp lại ngắt quãng, và biến gợi ý học tập từ một câu "chủ đề điểm
thấp nhất" thành đề xuất có lý do và hành động cụ thể.

**Architecture:** Thuật toán xếp lịch là module thuần không chạm DB, theo đúng
khuôn `app/mastery.py`. Truy vấn thẻ đến hạn tách thành `app/flashcard_service.py`
để cả router flashcard lẫn phần gợi ý cùng dùng mà không phải router import
router. Đề xuất học tập lấy lý do từ ký ức episodic đã xây ở giai đoạn A, vẫn
tuyệt đối không gọi LLM.

**Tech Stack:** Python 3.12, SQLAlchemy 2.0.35, FastAPI 0.115, unittest.

**Spec:** `docs/superpowers/specs/2026-08-28-edututor-completion-design.md` (mục 5)

## Global Constraints

- Test chạy bằng `../venv/Scripts/python.exe -m unittest discover -s tests` từ `backend/`.
- Mọi file test bắt đầu bằng `sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))`.
- Comment và docstring tiếng Việt.
- Gợi ý học tập và xếp lịch ôn tập KHÔNG được gọi LLM (PRD §6 và spec mục 5.3).
- `ease` khởi tạo 2.5, kẹp trong [1.3, 2.5].
- Datetime từ SQLite là naive — chuẩn hoá trước khi so sánh, như `app/mastery.py:26-27`.

---

### Task 1: Thuật toán xếp lịch lặp lại ngắt quãng

**Files:**
- Create: `backend/app/spaced_repetition.py`
- Test: `backend/tests/test_spaced_repetition.py`

**Interfaces:**
- Produces:
  - `VALID_RATINGS: tuple = ("again", "hard", "good", "easy")`
  - `DEFAULT_EASE: float = 2.5`, `MIN_EASE: float = 1.3`, `MAX_EASE: float = 2.5`
  - `@dataclass ReviewSchedule(interval_days: float, ease: float, next_due_at: datetime)`
  - `schedule_next_review(rating: str, interval_days: float = 0.0, ease: float = DEFAULT_EASE, now: Optional[datetime] = None) -> ReviewSchedule`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_spaced_repetition.py`:

```python
import os
import sys
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.spaced_repetition import (
    DEFAULT_EASE,
    MAX_EASE,
    MIN_EASE,
    schedule_next_review,
)

NOW = datetime(2026, 8, 28, 12, 0, 0, tzinfo=timezone.utc)


class TestScheduleNextReview(unittest.TestCase):
    def test_new_card_rated_good_is_due_in_one_day(self):
        s = schedule_next_review("good", now=NOW)
        self.assertEqual(s.interval_days, 1)
        self.assertEqual((s.next_due_at - NOW.replace(tzinfo=None)).days, 1)

    def test_new_card_rated_easy_waits_longer_than_good(self):
        good = schedule_next_review("good", now=NOW)
        easy = schedule_next_review("easy", now=NOW)
        self.assertGreater(easy.interval_days, good.interval_days)

    def test_again_makes_card_due_immediately(self):
        s = schedule_next_review("again", interval_days=10, ease=2.5, now=NOW)
        self.assertEqual(s.interval_days, 0)
        self.assertEqual(s.next_due_at, NOW.replace(tzinfo=None))

    def test_again_lowers_ease(self):
        s = schedule_next_review("again", interval_days=10, ease=2.5, now=NOW)
        self.assertLess(s.ease, 2.5)

    def test_good_keeps_ease_unchanged(self):
        s = schedule_next_review("good", interval_days=4, ease=2.1, now=NOW)
        self.assertAlmostEqual(s.ease, 2.1)

    def test_interval_grows_by_ease_on_good(self):
        s = schedule_next_review("good", interval_days=4, ease=2.0, now=NOW)
        self.assertEqual(s.interval_days, 8)

    def test_ease_never_drops_below_floor(self):
        ease = DEFAULT_EASE
        for _ in range(20):
            ease = schedule_next_review("again", interval_days=1, ease=ease, now=NOW).ease
        self.assertGreaterEqual(ease, MIN_EASE)

    def test_ease_never_exceeds_ceiling(self):
        ease = DEFAULT_EASE
        for _ in range(20):
            ease = schedule_next_review("easy", interval_days=1, ease=ease, now=NOW).ease
        self.assertLessEqual(ease, MAX_EASE)

    def test_unknown_rating_is_rejected(self):
        with self.assertRaises(ValueError):
            schedule_next_review("khong_hop_le", now=NOW)

    def test_hard_grows_slower_than_good(self):
        hard = schedule_next_review("hard", interval_days=10, ease=2.5, now=NOW)
        good = schedule_next_review("good", interval_days=10, ease=2.5, now=NOW)
        self.assertLess(hard.interval_days, good.interval_days)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../venv/Scripts/python.exe -m unittest tests.test_spaced_repetition`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.spaced_repetition'`

- [ ] **Step 3: Write minimal implementation**

Create `backend/app/spaced_repetition.py`:

```python
"""Xếp lịch ôn lại flashcard theo lặp lại ngắt quãng — bản rút gọn của SM-2.

Module THUẦN: không chạm DB, không chạm mạng, nhận trạng thái hiện tại và trả
về trạng thái tiếp theo. Cùng khuôn với app/mastery.py để test được độc lập.

Vì sao rút gọn thay vì SM-2 đầy đủ: SM-2 gốc dùng thang chất lượng 0-5 và một
công thức ease phức tạp hơn, nhưng người học phải tự chấm mình theo 6 mức —
quá tinh vi cho một giao diện chỉ có bốn nút. Bốn mức "again/hard/good/easy"
là cách Anki đã đơn giản hoá và đủ để phân biệt trạng thái nhớ.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

VALID_RATINGS = ("again", "hard", "good", "easy")

DEFAULT_EASE = 2.5
MIN_EASE = 1.3
MAX_EASE = 2.5

_EASE_DELTA = {"again": -0.20, "hard": -0.15, "good": 0.0, "easy": 0.15}


@dataclass
class ReviewSchedule:
    interval_days: float
    ease: float
    next_due_at: datetime


def _to_naive_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=None) if value.tzinfo is not None else value


def _next_interval(rating: str, interval_days: float, ease: float) -> float:
    if rating == "again":
        # Quên hẳn thì phải gặp lại NGAY trong cùng phiên, không đẩy sang ngày
        # khác — đó là điểm mấu chốt của lặp lại ngắt quãng.
        return 0
    if rating == "hard":
        return max(1, interval_days * 1.2)
    if rating == "good":
        return max(1, interval_days * ease)
    return max(2, interval_days * ease * 1.3)


def schedule_next_review(
    rating: str,
    interval_days: float = 0.0,
    ease: float = DEFAULT_EASE,
    now: Optional[datetime] = None,
) -> ReviewSchedule:
    if rating not in VALID_RATINGS:
        raise ValueError(f"Mức đánh giá không hợp lệ: {rating!r}. Chỉ nhận {VALID_RATINGS}.")

    now = _to_naive_utc(now or datetime.now(timezone.utc))
    new_interval = _next_interval(rating, interval_days, ease)
    new_ease = max(MIN_EASE, min(MAX_EASE, ease + _EASE_DELTA[rating]))

    return ReviewSchedule(
        interval_days=new_interval,
        ease=new_ease,
        next_due_at=now + timedelta(days=new_interval),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `../venv/Scripts/python.exe -m unittest tests.test_spaced_repetition -v`
Expected: PASS, 10 test

- [ ] **Step 5: Commit**

```bash
git add backend/app/spaced_repetition.py backend/tests/test_spaced_repetition.py
git commit -m "feat: thuat toan xep lich lap lai ngat quang"
```

---

### Task 2: Bảng FlashcardReview và truy vấn thẻ đến hạn

**Files:**
- Modify: `backend/app/models.py` (thêm `FlashcardReview` ở cuối)
- Create: `backend/app/flashcard_service.py`
- Test: `backend/tests/test_flashcard_service.py`

**Interfaces:**
- Produces:
  - `models.FlashcardReview` — `id, user_id, flashcard_item_id, rating, reviewed_at, interval_days, ease, next_due_at`
  - `latest_review_by_item(db, user_id) -> dict[str, FlashcardReview]`
  - `due_items(db, user_id, now=None, limit=20) -> List[tuple[FlashcardItem, Optional[FlashcardReview]]]`
  - `count_due(db, user_id, now=None) -> int`

`app/flashcard_service.py` tồn tại để cả `app/routers/flashcard.py` lẫn phần
gợi ý học tập (`app/routers/chat.py`) cùng dùng một truy vấn — router import
router là kiểu phụ thuộc vòng chực chờ.

- [ ] **Step 1: Thêm model**

Trong `backend/app/models.py`, thêm cuối file:

```python
class FlashcardReview(Base):
    """Một lượt ôn lại flashcard — bảng LỊCH SỬ, mỗi lượt ôn thêm một hàng.

    Trạng thái hiện tại của một thẻ là hàng MỚI NHẤT của thẻ đó (xem
    app/flashcard_service.py::latest_review_by_item). Giữ nguyên lịch sử thay
    vì ghi đè một hàng trạng thái để về sau còn dựng lại được đường cong quên
    của người học nếu cần.

    `interval_days`/`ease`/`next_due_at` do app/spaced_repetition.py tính, module
    đó thuần và không biết gì về bảng này.
    """

    __tablename__ = "flashcard_reviews"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    flashcard_item_id = Column(String, ForeignKey("flashcard_items.id"), nullable=False)
    rating = Column(String, nullable=False)  # again | hard | good | easy
    reviewed_at = Column(DateTime, default=datetime.utcnow)
    interval_days = Column(Float, nullable=False)
    ease = Column(Float, nullable=False)
    next_due_at = Column(DateTime, nullable=False)
```

- [ ] **Step 2: Write the failing test**

Create `backend/tests/test_flashcard_service.py`:

```python
import os
import sys
import unittest
from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.flashcard_service import count_due, due_items, latest_review_by_item
from app.models import Base, FlashcardItem, FlashcardReview, FlashcardSet

NOW = datetime(2026, 8, 28, 12, 0, 0)


class FlashcardServiceTestCase(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.fset = FlashcardSet(user_id="u1", document_id="d1")
        self.db.add(self.fset)
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def _item(self, front="Mặt trước", back="Mặt sau"):
        item = FlashcardItem(flashcard_set_id=self.fset.id, front=front, back=back)
        self.db.add(item)
        self.db.commit()
        return item

    def _review(self, item, next_due_at, reviewed_at, rating="good"):
        review = FlashcardReview(
            user_id="u1",
            flashcard_item_id=item.id,
            rating=rating,
            reviewed_at=reviewed_at,
            interval_days=1,
            ease=2.5,
            next_due_at=next_due_at,
        )
        self.db.add(review)
        self.db.commit()
        return review


class TestDueItems(FlashcardServiceTestCase):
    def test_never_reviewed_card_is_due(self):
        item = self._item()
        due = due_items(self.db, "u1", now=NOW)
        self.assertEqual([i.id for i, _ in due], [item.id])

    def test_card_due_in_future_is_not_returned(self):
        item = self._item()
        self._review(item, next_due_at=NOW + timedelta(days=3), reviewed_at=NOW)
        self.assertEqual(due_items(self.db, "u1", now=NOW), [])

    def test_card_past_due_is_returned(self):
        item = self._item()
        self._review(item, next_due_at=NOW - timedelta(days=1), reviewed_at=NOW - timedelta(days=2))
        due = due_items(self.db, "u1", now=NOW)
        self.assertEqual([i.id for i, _ in due], [item.id])

    def test_only_latest_review_decides_due_state(self):
        item = self._item()
        # lượt cũ đặt hạn trong quá khứ, lượt MỚI đẩy hạn sang tương lai
        self._review(item, next_due_at=NOW - timedelta(days=5), reviewed_at=NOW - timedelta(days=6))
        self._review(item, next_due_at=NOW + timedelta(days=5), reviewed_at=NOW)
        self.assertEqual(due_items(self.db, "u1", now=NOW), [])

    def test_does_not_leak_cards_across_users(self):
        self._item()
        self.assertEqual(due_items(self.db, "nguoi-khac", now=NOW), [])

    def test_respects_limit(self):
        for i in range(5):
            self._item(front=f"Thẻ {i}")
        self.assertEqual(len(due_items(self.db, "u1", now=NOW, limit=2)), 2)

    def test_count_due_matches_number_of_due_cards(self):
        self._item()
        self._item()
        self.assertEqual(count_due(self.db, "u1", now=NOW), 2)


class TestLatestReviewByItem(FlashcardServiceTestCase):
    def test_returns_most_recent_review_per_item(self):
        item = self._item()
        self._review(item, next_due_at=NOW, reviewed_at=NOW - timedelta(days=2), rating="hard")
        self._review(item, next_due_at=NOW, reviewed_at=NOW, rating="easy")
        latest = latest_review_by_item(self.db, "u1")
        self.assertEqual(latest[item.id].rating, "easy")

    def test_empty_when_no_reviews(self):
        self._item()
        self.assertEqual(latest_review_by_item(self.db, "u1"), {})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run test to verify it fails**

Run: `../venv/Scripts/python.exe -m unittest tests.test_flashcard_service`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.flashcard_service'`

- [ ] **Step 4: Write minimal implementation**

Create `backend/app/flashcard_service.py`:

```python
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
```

- [ ] **Step 5: Run test to verify it passes**

Run: `../venv/Scripts/python.exe -m unittest tests.test_flashcard_service -v`
Expected: PASS, 9 test

- [ ] **Step 6: Commit**

```bash
git add backend/app/models.py backend/app/flashcard_service.py backend/tests/test_flashcard_service.py
git commit -m "feat: bang FlashcardReview va truy van the den han"
```

---

### Task 3: Endpoint vòng ôn tập flashcard

**Files:**
- Modify: `backend/app/routers/flashcard.py`

**Interfaces:**
- Produces:
  - `GET /flashcard/due?user_id=...&limit=20` → `{"items": [{id, front, back, source_document, source_position, interval_days, ease}]}`
  - `POST /flashcard/review` body `{user_id, flashcard_item_id, rating}` → `{"rating", "interval_days", "ease", "next_due_at", "back"}`

- [ ] **Step 1: Vá chỗ dựng RetrievedChunk còn thiếu định danh**

Ở giai đoạn C, `RetrievedChunk` đã có thêm `chunk_id`/`document_id` nhưng
`backend/app/routers/flashcard.py` bị bỏ sót. Sửa:

```python
    retrieved_chunks = [
        RetrievedChunk(
            text=c.text,
            document_name=c.document_name,
            position_ref=c.position_ref,
            score=score,
            chunk_id=c.chunk_id,
            document_id=c.document_id,
        )
        for c, score in results
    ]
```

- [ ] **Step 2: Thêm hai endpoint**

Thêm import vào `backend/app/routers/flashcard.py`:

```python
from datetime import datetime, timezone

from app.flashcard_service import due_items
from app.memory.service import record_event
from app.models import FlashcardReview
from app.spaced_repetition import DEFAULT_EASE, VALID_RATINGS, schedule_next_review
```

Thêm vào cuối file:

```python
@router.get("/due")
def list_due(user_id: str, limit: int = 20, db: Session = Depends(get_db)):
    """Thẻ cần ôn hôm nay — chưa từng ôn hoặc đã tới hạn."""
    items = due_items(db, user_id, limit=limit)
    return {
        "items": [
            {
                "id": item.id,
                "front": item.front,
                "back": item.back,
                "source_document": item.source_document,
                "source_position": item.source_position,
                "interval_days": review.interval_days if review else 0,
                "ease": review.ease if review else DEFAULT_EASE,
            }
            for item, review in items
        ]
    }


class ReviewFlashcardRequest(BaseModel):
    user_id: str
    flashcard_item_id: str
    rating: str  # again | hard | good | easy


# Chỉ ghi ký ức cho hai đầu mút của thang đánh giá: "quên hẳn" và "quá dễ" nói
# lên điều gì đó về người học, còn "hard"/"good" là trạng thái bình thường của
# việc ôn tập và ghi lại chỉ làm nhiễu ký ức.
_MEMORY_EVENT_BY_RATING = {"again": "flashcard_again", "easy": "flashcard_easy"}


@router.post("/review")
def review(req: ReviewFlashcardRequest, db: Session = Depends(get_db)):
    if req.rating not in VALID_RATINGS:
        raise HTTPException(400, f"Mức đánh giá không hợp lệ. Chỉ nhận: {', '.join(VALID_RATINGS)}.")

    item = (
        db.query(FlashcardItem)
        .join(FlashcardSet, FlashcardItem.flashcard_set_id == FlashcardSet.id)
        .filter(FlashcardItem.id == req.flashcard_item_id, FlashcardSet.user_id == req.user_id)
        .first()
    )
    if not item:
        raise HTTPException(404, "Không tìm thấy thẻ này.")

    previous = (
        db.query(FlashcardReview)
        .filter(
            FlashcardReview.user_id == req.user_id,
            FlashcardReview.flashcard_item_id == item.id,
        )
        .order_by(FlashcardReview.reviewed_at.desc())
        .first()
    )

    schedule = schedule_next_review(
        rating=req.rating,
        interval_days=previous.interval_days if previous else 0.0,
        ease=previous.ease if previous else DEFAULT_EASE,
    )

    db.add(
        FlashcardReview(
            user_id=req.user_id,
            flashcard_item_id=item.id,
            rating=req.rating,
            interval_days=schedule.interval_days,
            ease=schedule.ease,
            next_due_at=schedule.next_due_at,
        )
    )
    db.commit()

    event_type = _MEMORY_EVENT_BY_RATING.get(req.rating)
    if event_type:
        verb = "quên" if req.rating == "again" else "thấy quá dễ"
        record_event(
            db,
            user_id=req.user_id,
            event_type=event_type,
            content=f"Khi ôn flashcard đã {verb} thẻ: \"{item.front}\"",
            topic_id=item.topic_id,
            source_ref=item.source_position,
        )

    return {
        "rating": req.rating,
        "interval_days": schedule.interval_days,
        "ease": schedule.ease,
        "next_due_at": schedule.next_due_at.isoformat(),
        "back": item.back,
    }
```

- [ ] **Step 3: Kiểm tra route và chạy test**

Run: `../venv/Scripts/python.exe -c "from app.main import app; print([r.path for r in app.routes if 'flashcard' in r.path])"`
Expected: có `/flashcard/generate`, `/flashcard/due`, `/flashcard/review`

Run: `../venv/Scripts/python.exe -m unittest discover -s tests`
Expected: toàn bộ PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/routers/flashcard.py
git commit -m "feat: vong on tap flashcard co lap lai ngat quang"
```

---

### Task 4: Bậc độ khó thứ ba cho quiz

**Files:**
- Modify: `backend/app/llm/quiz_generator.py`
- Test: `backend/tests/test_quiz_generator.py`

**Interfaces:**
- Produces: `_DIFFICULTY_INSTRUCTIONS` có thêm khoá `"intermediate"`

- [ ] **Step 1: Write the failing test**

Thêm vào `backend/tests/test_quiz_generator.py` (đặt trong class test đã có sẵn
cho phần độ khó; nếu chưa có class nào phù hợp thì thêm class mới ở cuối file,
trước `if __name__`):

```python
class TestIntermediateDifficulty(unittest.TestCase):
    def test_intermediate_instruction_is_included_in_prompt(self):
        from app.llm.quiz_generator import _build_generator_prompt
        from app.llm.rag import RetrievedChunk

        chunks = [RetrievedChunk(text="Nội dung.", document_name="a.pdf", position_ref="Trang 1", score=0.9)]
        prompt = _build_generator_prompt(chunks, num_questions=3, difficulty="intermediate")
        self.assertIn("vận dụng", prompt)

    def test_three_difficulty_levels_give_three_distinct_instructions(self):
        from app.llm.quiz_generator import _DIFFICULTY_INSTRUCTIONS

        texts = {
            _DIFFICULTY_INSTRUCTIONS["beginner"],
            _DIFFICULTY_INSTRUCTIONS["intermediate"],
            _DIFFICULTY_INSTRUCTIONS["advanced"],
        }
        self.assertEqual(len(texts), 3)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../venv/Scripts/python.exe -m unittest tests.test_quiz_generator`
Expected: FAIL — `KeyError: 'intermediate'`

- [ ] **Step 3: Write minimal implementation**

Trong `backend/app/llm/quiz_generator.py`, thêm khoá `"intermediate"` vào
`_DIFFICULTY_INSTRUCTIONS`, giữa `beginner` và `advanced`:

```python
    "intermediate": (
        "Ưu tiên câu hỏi ở mức vận dụng: người học phải hiểu khái niệm rồi áp "
        "dụng vào một tình huống quen thuộc, chứ không chỉ nhắc lại định nghĩa "
        "như mức cơ bản, nhưng cũng không cần phân tích đánh đổi kỹ thuật sâu "
        "như mức nâng cao. Mỗi câu nên hỏi 'khi nào dùng', 'điều gì xảy ra "
        "nếu', hoặc 'chọn phương án nào cho trường hợp này'. Các lựa chọn sai "
        "phải là nhầm lẫn hợp lý giữa hai khái niệm gần nhau, không phải đáp "
        "án hiển nhiên sai."
    ),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `../venv/Scripts/python.exe -m unittest discover -s tests`
Expected: toàn bộ PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/llm/quiz_generator.py backend/tests/test_quiz_generator.py
git commit -m "feat: them bac do kho intermediate cho quiz"
```

---

### Task 5: Đề xuất cải thiện học tập có lý do và hành động

**Files:**
- Modify: `backend/app/llm/recommendation.py`
- Test: `backend/tests/test_recommendation.py`

**Interfaces:**
- Produces: `build_recommendation(topics: List[TopicMastery], evidence_by_topic: Optional[Dict[str, List[str]]] = None, due_flashcards: int = 0) -> str`

Hai tham số mới đều có mặc định nên mọi lời gọi hiện có vẫn chạy đúng như cũ.

- [ ] **Step 1: Write the failing test**

Thêm class mới vào cuối `backend/tests/test_recommendation.py`, trước `if __name__`:

```python
class TestStructuredRecommendation(unittest.TestCase):
    def test_includes_reason_from_episodic_evidence(self):
        topics = [TopicMastery(topic_name="Backpropagation", score=0.2)]
        evidence = {"Backpropagation": ["Trả lời sai câu quiz về đạo hàm chuỗi"]}
        result = build_recommendation(topics, evidence_by_topic=evidence)
        self.assertIn("đạo hàm chuỗi", result)

    def test_suggests_reviewing_due_flashcards_when_any(self):
        topics = [TopicMastery(topic_name="CNN", score=0.3)]
        result = build_recommendation(topics, due_flashcards=7)
        self.assertIn("7", result)
        self.assertIn("flashcard", result.lower())

    def test_no_flashcard_line_when_none_due(self):
        topics = [TopicMastery(topic_name="CNN", score=0.3)]
        result = build_recommendation(topics, due_flashcards=0)
        self.assertNotIn("flashcard", result.lower())

    def test_suggests_a_concrete_quiz_action(self):
        topics = [TopicMastery(topic_name="CNN", score=0.3)]
        result = build_recommendation(topics)
        self.assertIn("quiz", result.lower())
        self.assertIn("CNN", result)

    def test_evidence_for_unrelated_topic_is_not_shown(self):
        topics = [TopicMastery(topic_name="CNN", score=0.3)]
        evidence = {"Decision Tree": ["Sai câu về entropy"]}
        result = build_recommendation(topics, evidence_by_topic=evidence)
        self.assertNotIn("entropy", result)

    def test_evidence_is_capped(self):
        topics = [TopicMastery(topic_name="CNN", score=0.3)]
        evidence = {"CNN": [f"Sự kiện số {i}" for i in range(10)]}
        result = build_recommendation(topics, evidence_by_topic=evidence)
        self.assertNotIn("Sự kiện số 3", result)

    def test_still_works_with_no_extra_arguments(self):
        topics = [TopicMastery(topic_name="CNN", score=0.9)]
        result = build_recommendation(topics)
        self.assertIn("CNN", result)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../venv/Scripts/python.exe -m unittest tests.test_recommendation`
Expected: FAIL — `TypeError: build_recommendation() got an unexpected keyword argument 'evidence_by_topic'`

- [ ] **Step 3: Write minimal implementation**

Trong `backend/app/llm/recommendation.py`, đổi import dòng đầu thành
`from typing import Dict, List, Optional`, thêm hằng số và viết lại
`build_recommendation`:

```python
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
    return f" Cụ thể, trước đây bạn: {shown}."


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
        lines.append(evidence.strip())

    actions = [f'làm một quiz mức intermediate về "{focus.topic_name}"']
    if due_flashcards > 0:
        actions.append(f"ôn {due_flashcards} thẻ flashcard đang đến hạn")
    actions.append("đọc lại đoạn tài liệu nguồn của những câu bạn đã trả lời sai")
    lines.append("Việc nên làm tiếp: " + "; ".join(actions) + ".")

    return " ".join(lines)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `../venv/Scripts/python.exe -m unittest discover -s tests`
Expected: toàn bộ PASS. Nếu test cũ về recommendation vỡ vì câu trả lời giờ
dài hơn, kiểm tra xem nó có khẳng định bằng `assertEqual` trên cả chuỗi không —
nếu có, đổi sang `assertIn` cho phần thật sự quan trọng, vì việc thêm dòng
hành động là thay đổi có chủ đích.

- [ ] **Step 5: Commit**

```bash
git add backend/app/llm/recommendation.py backend/tests/test_recommendation.py
git commit -m "feat: de xuat hoc tap co ly do va hanh dong cu the"
```

---

### Task 6: Nối bằng chứng episodic vào gợi ý học tập

**Files:**
- Modify: `backend/app/routers/chat.py` (hàm `_build_recommendation_result`)

**Interfaces:**
- Consumes: `app.flashcard_service.count_due`, `app.models.MemoryEvent`
- Produces: `/chat/ask` với câu hỏi dạng "nên học gì tiếp theo" trả về gợi ý có lý do và hành động

- [ ] **Step 1: Gom bằng chứng và số thẻ đến hạn**

Trong `backend/app/routers/chat.py`, thêm import:

```python
from app.flashcard_service import count_due
from app.models import MemoryEvent
```

(thêm `MemoryEvent` vào dòng import `app.models` đã có.)

Thay `_build_recommendation_result` bằng:

```python
# Loại ký ức dùng làm LÝ DO một chủ đề bị coi là yếu — chỉ lấy các sự kiện
# phản ánh việc không nhớ/không làm được, không lấy sự kiện hỏi đáp thường.
_WEAKNESS_EVENT_TYPES = ("quiz_wrong", "flashcard_again")
MAX_EVIDENCE_PER_TOPIC = 3


def _build_recommendation_result(db: Session, user_id: str, course_name: str | None) -> AnswerResult:
    """TC10/TC24 — gợi ý chủ đề nên học tiếp theo, đọc lại MasteryScore đã có
    sẵn (F4) cộng ký ức episodic (giai đoạn A) để nói được VÌ SAO chủ đề đó
    yếu. Vẫn KHÔNG gọi LLM: toàn bộ là đọc lại dữ liệu đã tính."""
    query = (
        db.query(MasteryScore, Topic)
        .join(Topic, MasteryScore.topic_id == Topic.id)
        .filter(MasteryScore.user_id == user_id)
    )
    if course_name:
        query = query.filter(Topic.course_name == course_name)

    rows = query.all()
    topics = [TopicMastery(topic_name=topic.name, score=score.score) for score, topic in rows]

    topic_name_by_id = {topic.id: topic.name for _, topic in rows}
    evidence_by_topic: dict[str, list[str]] = {}
    if topic_name_by_id:
        events = (
            db.query(MemoryEvent)
            .filter(
                MemoryEvent.user_id == user_id,
                MemoryEvent.topic_id.in_(list(topic_name_by_id.keys())),
                MemoryEvent.event_type.in_(_WEAKNESS_EVENT_TYPES),
            )
            .order_by(MemoryEvent.created_at.desc())
            .all()
        )
        for event in events:
            name = topic_name_by_id.get(event.topic_id)
            if not name:
                continue
            bucket = evidence_by_topic.setdefault(name, [])
            if len(bucket) < MAX_EVIDENCE_PER_TOPIC:
                bucket.append(event.content)

    answer = build_recommendation(
        topics,
        evidence_by_topic=evidence_by_topic,
        due_flashcards=count_due(db, user_id),
    )
    return AnswerResult(answer=answer, is_grounded=True, sources=[])
```

- [ ] **Step 2: Chạy test và kiểm tra import**

Run: `../venv/Scripts/python.exe -m unittest discover -s tests`
Expected: toàn bộ PASS

Run: `../venv/Scripts/python.exe -c "from app.main import app; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add backend/app/routers/chat.py
git commit -m "feat: noi bang chung episodic vao goi y hoc tap"
```

---

## Kiểm chứng cuối giai đoạn B

- [ ] Toàn bộ test PASS
- [ ] Script kiểm chứng trong scratchpad: tạo một flashcard, gọi `/flashcard/due` thấy nó, gọi `/flashcard/review` với `again` rồi xác nhận thẻ VẪN đến hạn ngay; đánh giá `good` rồi xác nhận thẻ biến khỏi danh sách đến hạn
- [ ] Xác nhận đánh giá `again` sinh một `MemoryEvent` loại `flashcard_again`
- [ ] Gọi `/chat/ask` với câu "tôi nên học gì tiếp theo" trên một user có mastery thấp và có ký ức `quiz_wrong`, xác nhận câu trả lời nêu được lý do lấy từ ký ức đó
