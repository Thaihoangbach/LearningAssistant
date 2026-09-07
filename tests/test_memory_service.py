"""record_event()/recall_events() giờ đọc/ghi thẳng embedding trên
MemoryEvent (app/models.py), không còn qua MemoryStore/MemoryRecord riêng
(app/memory/store.py, đã gỡ bỏ khi chuyển sang Postgres+pgvector).

`test_returns_relevant_recent_event` và các test recall khác cần
cosine_distance() THẬT — chỉ Postgres chạy được (xem tests/pg_test_helpers.py)
— nên dùng Postgres test container, không phải SQLite in-memory như bản cũ.
Nhóm TestRecordEvent (không cần truy vấn cosine, chỉ cần INSERT thành công)
vẫn có thể chạy trên SQLite, nhưng dùng chung Postgres cho cả file để không
phải bảo trì 2 cách dựng DB khác nhau."""
import os
import sys
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np

from app.memory.service import recall_events, record_event
from app.models import MemoryEvent, User
from pg_test_helpers import fresh_test_session_factory


def fake_embed(text):
    # Bắt chước ĐÚNG shape của app/ingestion/embedder.py::embed_query — mảng
    # 1 CHIỀU (dim,), khớp EMBEDDING_DIM=1024 để giống dữ liệu thật.
    v = np.zeros(1024, dtype="float32")
    v[0] = 1.0
    return v


def fake_embed_orthogonal(text):
    """Vector VUÔNG GÓC với fake_embed() (cosine similarity = 0) — dùng để
    dựng sự kiện KHÔNG liên quan tới truy vấn trong test recall."""
    v = np.zeros(1024, dtype="float32")
    v[1] = 1.0
    return v


class MemoryServiceTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine, cls.SessionLocal = fresh_test_session_factory()

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()

    def setUp(self):
        self.db = self.SessionLocal()
        self.addCleanup(self.db.close)
        # setUpClass chỉ drop/create schema MỘT LẦN cho cả file — dọn sạch dữ
        # liệu giữa các test trong CÙNG class ở đây, tránh đụng UNIQUE
        # constraint của users.id khi test sau chạy với cùng id "u1".
        self.db.query(MemoryEvent).delete()
        self.db.query(User).delete()
        self.db.commit()
        self.db.add(User(id="u1", email="u1@test.local", display_name="U1"))
        self.db.add(User(id="nguoi_khac", email="nguoi-khac@test.local", display_name="Người khác"))
        self.db.commit()


class TestRecordEvent(MemoryServiceTestCase):
    def test_writes_row_with_importance_from_lookup_table(self):
        event = record_event(
            self.db, user_id="u1", event_type="quiz_wrong",
            content="Sai câu về Gradient Descent", embed_fn=fake_embed,
        )
        self.assertAlmostEqual(event.importance, 0.9)

        rows = self.db.query(MemoryEvent).filter(MemoryEvent.user_id == "u1").all()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].event_type, "quiz_wrong")

    def test_embedding_is_stored_on_the_row_itself(self):
        """Khác bản cũ (embedding sống trong FAISS index riêng) — giờ
        embedding nằm NGAY trên dòng MemoryEvent, cùng transaction."""
        event = record_event(
            self.db, user_id="u1", event_type="question_asked",
            content="Hỏi về CNN", embed_fn=fake_embed,
        )

        row = self.db.query(MemoryEvent).filter(MemoryEvent.id == event.id).first()
        self.assertIsNotNone(row.embedding)
        self.assertEqual(len(row.embedding), 1024)

    def test_unknown_event_type_uses_default_importance(self):
        event = record_event(
            self.db, user_id="u1", event_type="loai_la", content="nội dung", embed_fn=fake_embed,
        )
        self.assertAlmostEqual(event.importance, 0.3)

    def test_embedding_failure_does_not_block_writing_the_event(self):
        """Lỗi API embedding (Cohere lỗi/rớt mạng) không được chặn đứng việc
        ghi lại sự kiện học tập — embedding nullable đúng vì lý do này."""
        def failing_embed(text):
            raise RuntimeError("Cohere API lỗi")

        event = record_event(
            self.db, user_id="u1", event_type="question_asked",
            content="Hỏi về RNN", embed_fn=failing_embed,
        )

        self.assertIsNotNone(event.id)
        row = self.db.query(MemoryEvent).filter(MemoryEvent.id == event.id).first()
        self.assertIsNone(row.embedding)


class TestRecallEvents(MemoryServiceTestCase):
    def _seed_with_created_at(self, user_id, event_type, content, created_at, embed_fn=fake_embed):
        event = record_event(
            self.db, user_id=user_id, event_type=event_type, content=content, embed_fn=embed_fn,
        )
        row = self.db.query(MemoryEvent).filter(MemoryEvent.id == event.id).first()
        row.created_at = created_at
        self.db.commit()
        return row

    def test_returns_empty_when_user_has_no_memory(self):
        result = recall_events(self.db, "u1", "câu hỏi", embed_fn=fake_embed)
        self.assertEqual(result, [])

    def test_returns_relevant_recent_event(self):
        now = datetime.utcnow()
        self._seed_with_created_at("u1", "quiz_wrong", "Sai câu về Gradient Descent", now)

        result = recall_events(self.db, "u1", "gradient descent", embed_fn=fake_embed)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].content, "Sai câu về Gradient Descent")

    def test_does_not_leak_memory_across_users(self):
        now = datetime.utcnow()
        self._seed_with_created_at("nguoi_khac", "quiz_wrong", "Bí mật của người khác", now)

        result = recall_events(self.db, "u1", "bất kỳ", embed_fn=fake_embed)

        self.assertEqual(result, [])

    def test_event_without_embedding_is_excluded_from_semantic_recall(self):
        """Sự kiện ghi lúc embedding lỗi (embedding IS NULL) không có gì để so
        cosine — phải bị loại khỏi kết quả, không gây lỗi so sánh với NULL."""
        def failing_embed(text):
            raise RuntimeError("lỗi")

        self._seed_with_created_at("u1", "question_asked", "Sự kiện không có vector", datetime.utcnow(), embed_fn=failing_embed)

        result = recall_events(self.db, "u1", "bất kỳ", embed_fn=fake_embed)

        self.assertEqual(result, [])

    def test_irrelevant_old_event_is_filtered_out(self):
        old = datetime.utcnow() - timedelta(days=400)
        # Vector VUÔNG GÓC với truy vấn (cosine ~ 0) VÀ đã cũ — cả relevance
        # lẫn recency đều thấp, select_top_events (app/memory/scoring.py)
        # phải loại bỏ.
        self._seed_with_created_at(
            "u1", "question_asked", "Chuyện rất cũ, không liên quan", old,
            embed_fn=fake_embed_orthogonal,
        )

        result = recall_events(self.db, "u1", "gradient descent", embed_fn=fake_embed)

        self.assertEqual(result, [])

    def test_updates_access_bookkeeping_for_recalled_events(self):
        now = datetime.utcnow()
        row = self._seed_with_created_at("u1", "quiz_wrong", "Sai câu về CNN", now)

        recall_events(self.db, "u1", "cnn", embed_fn=fake_embed)

        refreshed = self.db.query(MemoryEvent).filter(MemoryEvent.id == row.id).first()
        self.assertEqual(refreshed.access_count, 1)
        self.assertIsNotNone(refreshed.last_accessed_at)


if __name__ == "__main__":
    unittest.main()
