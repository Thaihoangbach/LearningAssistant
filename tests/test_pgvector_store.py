"""Test THẬT trên Postgres+pgvector (không mock) — xem tests/pg_test_helpers.py
cho lý do và yêu cầu hạ tầng.

BUG-2 (race điều kiện load-mutate-overwrite của FAISS cục bộ) không còn
CÓ THỂ xảy ra ở đây theo thiết kế: mỗi `add()`/`remove_document()` là một
INSERT/DELETE thật trong transaction của Postgres, không có bước "nạp cả
file vào RAM rồi ghi đè" nào để race vào — nên không cần (và không có) test
concurrency riêng cho module này như đã làm với UserVectorStore cũ."""
import os
import sys
import unittest
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np

from app.models import Document, User
from app.vectorstore.pgvector_store import PgVectorStore
from app.vectorstore.types import IndexedChunk
from pg_test_helpers import fresh_test_session_factory


def _chunk(i: int, document_id: str = "doc-1", text: str = None) -> IndexedChunk:
    return IndexedChunk(
        chunk_id=str(uuid.uuid4()),
        document_id=document_id,
        document_name="tai-lieu.pdf",
        position_ref=f"Trang {i}",
        text=text or f"Nội dung đoạn {i}",
    )


def _embedding(seed: float, dim: int = 1024) -> np.ndarray:
    rng = np.random.default_rng(int(seed * 1000))
    v = rng.random(dim).astype("float32")
    return v / np.linalg.norm(v)


class PgVectorStoreTestCase(unittest.TestCase):
    """setUpClass dựng schema MỘT LẦN cho cả file (nhanh hơn mỗi test tự
    drop/create) — mỗi test tự tạo user_id/document_id RIÊNG (uuid4) để
    không đụng dữ liệu của test khác chạy trước trong cùng bảng."""

    @classmethod
    def setUpClass(cls):
        cls.engine, cls.SessionLocal = fresh_test_session_factory()

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()

    def setUp(self):
        self.db = self.SessionLocal()
        self.addCleanup(self.db.close)
        self.user_id = str(uuid.uuid4())
        self.db.add(User(id=self.user_id, email=f"{self.user_id}@test.local", display_name="Test User"))
        self.document_id = str(uuid.uuid4())
        self.db.add(Document(id=self.document_id, user_id=self.user_id, file_name="a.pdf", status="sẵn sàng"))
        self.db.commit()
        self.store = PgVectorStore(db=self.db, user_id=self.user_id)


class TestAddAndSearch(PgVectorStoreTestCase):
    def test_search_finds_nearest_chunk_by_cosine_similarity(self):
        target = _chunk(0, document_id=self.document_id)
        other = _chunk(1, document_id=self.document_id)
        target_vec, other_vec = _embedding(1), _embedding(99)
        self.store.add(np.array([target_vec, other_vec]), [target, other])

        results = self.store.search(target_vec, top_k=1)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0].chunk_id, target.chunk_id)
        self.assertAlmostEqual(results[0][1], 1.0, places=4)  # cosine với chính nó = 1.0

    def test_search_filters_by_document_ids(self):
        other_document_id = str(uuid.uuid4())
        self.db.add(Document(id=other_document_id, user_id=self.user_id, file_name="b.pdf", status="sẵn sàng"))
        self.db.commit()

        chunk_a = _chunk(0, document_id=self.document_id)
        chunk_b = _chunk(0, document_id=other_document_id)
        vec = _embedding(5)
        self.store.add(np.array([vec, vec]), [chunk_a, chunk_b])

        results = self.store.search(vec, top_k=10, document_ids={self.document_id})

        self.assertEqual([c.chunk_id for c, _ in results], [chunk_a.chunk_id])

    def test_different_users_do_not_share_data(self):
        chunk = _chunk(0, document_id=self.document_id)
        self.store.add(np.array([_embedding(3)]), [chunk])

        other_user_id = str(uuid.uuid4())
        self.db.add(User(id=other_user_id, email=f"{other_user_id}@test.local", display_name="Other"))
        self.db.commit()
        other_store = PgVectorStore(db=self.db, user_id=other_user_id)

        self.assertEqual(other_store.search(_embedding(3), top_k=5), [])


class TestRemoveDocument(PgVectorStoreTestCase):
    def test_remove_document_drops_only_its_chunks(self):
        other_document_id = str(uuid.uuid4())
        self.db.add(Document(id=other_document_id, user_id=self.user_id, file_name="b.pdf", status="sẵn sàng"))
        self.db.commit()

        keep = _chunk(0, document_id=other_document_id)
        remove = _chunk(0, document_id=self.document_id)
        self.store.add(np.array([_embedding(1), _embedding(2)]), [keep, remove])

        self.store.remove_document(self.document_id)

        remaining = self.store.search(_embedding(1), top_k=10)
        self.assertEqual([c.chunk_id for c, _ in remaining], [keep.chunk_id])


class TestHybridSearch(PgVectorStoreTestCase):
    def test_keyword_only_match_is_still_found_via_fts(self):
        """Chunk có TỪ KHOÁ khớp đúng nhưng vector KHÔNG gần (embedding ngẫu
        nhiên, không liên quan) vẫn phải lọt vào candidate pool nhờ nhánh
        full-text search — đây chính là lý do cần hybrid thay vì chỉ dense."""
        needle = _chunk(0, document_id=self.document_id, text="Hạn mức tạm ứng tối đa năm triệu đồng")
        noise = [_chunk(i, document_id=self.document_id, text=f"Nội dung không liên quan số {i}") for i in range(1, 5)]
        chunks = [needle] + noise
        vectors = np.array([_embedding(i) for i in range(len(chunks))])
        self.store.add(vectors, chunks)

        # Vector truy vấn CỐ TÌNH xa mọi chunk (embedding riêng, không trùng
        # seed nào) — chỉ nhánh từ khoá có cơ hội tìm ra `needle`.
        results = self.store.hybrid_search(
            query="hạn mức tạm ứng", query_embedding=_embedding(999), candidate_pool=10
        )

        self.assertIn(needle.chunk_id, [c.chunk_id for c in results])

    def test_hybrid_search_respects_document_ids_filter(self):
        other_document_id = str(uuid.uuid4())
        self.db.add(Document(id=other_document_id, user_id=self.user_id, file_name="b.pdf", status="sẵn sàng"))
        self.db.commit()

        in_scope = _chunk(0, document_id=self.document_id, text="học máy và mạng nơ-ron")
        out_of_scope = _chunk(0, document_id=other_document_id, text="học máy và mạng nơ-ron")
        self.store.add(np.array([_embedding(1), _embedding(1)]), [in_scope, out_of_scope])

        results = self.store.hybrid_search(
            query="học máy", query_embedding=_embedding(1), candidate_pool=10,
            document_ids={self.document_id},
        )

        self.assertEqual([c.chunk_id for c in results], [in_scope.chunk_id])


if __name__ == "__main__":
    unittest.main()
