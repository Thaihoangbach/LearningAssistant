import os
import sys
import unittest
from datetime import datetime, timedelta

import numpy as np
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.memory.service import recall_events, record_event
from app.memory.store import MemoryRecord
from app.models import Base, MemoryEvent


class FakeStore:
    """Thay MemoryStore thật để test không cần faiss. Trả về độ liên quan đã
    định sẵn theo event_id qua `relevance_by_id`."""

    def __init__(self, relevance_by_id=None):
        self.records = []
        self.relevance_by_id = relevance_by_id or {}
        self.added_embeddings = []

    def add(self, embeddings, records):
        self.added_embeddings.append(embeddings)
        self.records.extend(records)

    def search(self, query_embedding, top_k=20):
        return [(r, self.relevance_by_id.get(r.event_id, 0.0)) for r in self.records]


def fake_embed(text):
    # Bắt chước ĐÚNG shape của app/ingestion/embedder.py::embed_query — nó trả
    # về mảng 1 CHIỀU (dim,) vì cài đặt là embed_texts([text])[0]. Fake trả về
    # (1, dim) sẽ giấu mất lỗi thiếu reshape trong record_event.
    return np.array([1.0, 0.0, 0.0], dtype="float32")


class MemoryServiceTestCase(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        self.db = sessionmaker(bind=self.engine)()

    def tearDown(self):
        self.db.close()


class TestRecordEvent(MemoryServiceTestCase):
    def test_writes_row_with_importance_from_lookup_table(self):
        store = FakeStore()
        event = record_event(
            self.db,
            user_id="u1",
            event_type="quiz_wrong",
            content="Sai câu về Gradient Descent",
            embed_fn=fake_embed,
            store=store,
        )
        self.assertAlmostEqual(event.importance, 0.9)

        rows = self.db.query(MemoryEvent).filter(MemoryEvent.user_id == "u1").all()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].event_type, "quiz_wrong")

    def test_also_indexes_into_store(self):
        store = FakeStore()
        event = record_event(
            self.db,
            user_id="u1",
            event_type="question_asked",
            content="Hỏi về CNN",
            embed_fn=fake_embed,
            store=store,
        )
        self.assertEqual(len(store.records), 1)
        self.assertEqual(store.records[0].event_id, event.id)

    def test_embedding_is_reshaped_to_two_dimensions(self):
        # embed_query() trả mảng 1 chiều; nếu không reshape thì FAISS nhận sai
        # shape và assert len(embeddings) == len(records) sẽ so 3 với 1.
        store = FakeStore()
        record_event(
            self.db,
            user_id="u1",
            event_type="question_asked",
            content="Hỏi về CNN",
            embed_fn=fake_embed,
            store=store,
        )
        self.assertEqual(store.added_embeddings[0].shape, (1, 3))

    def test_unknown_event_type_uses_default_importance(self):
        store = FakeStore()
        event = record_event(
            self.db,
            user_id="u1",
            event_type="loai_la",
            content="nội dung",
            embed_fn=fake_embed,
            store=store,
        )
        self.assertAlmostEqual(event.importance, 0.3)


class TestRecallEvents(MemoryServiceTestCase):
    def _seed(self, user_id, event_type, content, created_at):
        row = MemoryEvent(
            user_id=user_id,
            event_type=event_type,
            content=content,
            importance=0.9 if event_type == "quiz_wrong" else 0.3,
            created_at=created_at,
        )
        self.db.add(row)
        self.db.commit()
        return row

    def test_returns_empty_when_user_has_no_memory(self):
        store = FakeStore()
        result = recall_events(self.db, "u1", "câu hỏi", embed_fn=fake_embed, store=store)
        self.assertEqual(result, [])

    def test_returns_relevant_recent_event(self):
        now = datetime.utcnow()
        row = self._seed("u1", "quiz_wrong", "Sai câu về Gradient Descent", now)
        store = FakeStore(relevance_by_id={row.id: 1.0})
        store.records = [MemoryRecord(event_id=row.id, text=row.content)]

        result = recall_events(self.db, "u1", "gradient descent", embed_fn=fake_embed, store=store)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].content, "Sai câu về Gradient Descent")

    def test_does_not_leak_memory_across_users(self):
        now = datetime.utcnow()
        row = self._seed("nguoi_khac", "quiz_wrong", "Bí mật của người khác", now)
        store = FakeStore(relevance_by_id={row.id: 1.0})
        store.records = [MemoryRecord(event_id=row.id, text=row.content)]

        result = recall_events(self.db, "u1", "bất kỳ", embed_fn=fake_embed, store=store)
        self.assertEqual(result, [])

    def test_irrelevant_old_event_is_filtered_out(self):
        old = datetime.utcnow() - timedelta(days=400)
        row = self._seed("u1", "question_asked", "Chuyện rất cũ", old)
        store = FakeStore(relevance_by_id={row.id: 0.0})
        store.records = [MemoryRecord(event_id=row.id, text=row.content)]

        result = recall_events(self.db, "u1", "bất kỳ", embed_fn=fake_embed, store=store)
        self.assertEqual(result, [])

    def test_updates_access_bookkeeping_for_recalled_events(self):
        now = datetime.utcnow()
        row = self._seed("u1", "quiz_wrong", "Sai câu về CNN", now)
        store = FakeStore(relevance_by_id={row.id: 1.0})
        store.records = [MemoryRecord(event_id=row.id, text=row.content)]

        recall_events(self.db, "u1", "cnn", embed_fn=fake_embed, store=store)

        refreshed = self.db.query(MemoryEvent).filter(MemoryEvent.id == row.id).first()
        self.assertEqual(refreshed.access_count, 1)
        self.assertIsNotNone(refreshed.last_accessed_at)


if __name__ == "__main__":
    unittest.main()
