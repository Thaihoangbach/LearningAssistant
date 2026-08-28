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
