"""Vector store dùng FAISS local, lưu file trên đĩa — miễn phí, không cần server.

Mỗi user có một index FAISS RIÊNG (file riêng theo user_id) — đây là cách đơn
giản nhất để đảm bảo "quyền truy cập là bộ lọc đầu tiên trước khi truy hồi"
(nguyên tắc đã đặt ra khi thiết kế F2/F5): không có cách nào truy hồi lẫn
sang dữ liệu của người dùng khác vì mỗi người có index vật lý tách biệt,
thay vì lọc bằng metadata sau khi đã tìm kiếm trên một index chung.

CHƯA CHẠY ĐƯỢC TRONG SANDBOX NÀY: cần `pip install faiss-cpu` (sandbox không
có mạng). Cần cài đặt và chạy thử ở máy local trước khi tin tưởng module này.
"""

import os
import pickle
from typing import List

import numpy as np

from app.vectorstore.bm25_index import Bm25Index
from app.vectorstore.hybrid import reciprocal_rank_fusion
from app.vectorstore.types import IndexedChunk

__all__ = ["IndexedChunk", "UserVectorStore"]


class UserVectorStore:
    def __init__(self, user_id: str, storage_dir: str = "./data/vectorstore"):
        self.user_id = user_id
        self.storage_dir = storage_dir
        os.makedirs(storage_dir, exist_ok=True)
        self._index_path = os.path.join(storage_dir, f"{user_id}.faiss")
        self._meta_path = os.path.join(storage_dir, f"{user_id}.meta.pkl")
        self._index = None
        self._metadata: List[IndexedChunk] = []
        self._load()

    def _load(self):
        import faiss

        if os.path.exists(self._index_path) and os.path.exists(self._meta_path):
            self._index = faiss.read_index(self._index_path)
            with open(self._meta_path, "rb") as f:
                self._metadata = pickle.load(f)

    def _save(self):
        import faiss

        if self._index is None:
            for path in (self._index_path, self._meta_path):
                if os.path.exists(path):
                    os.remove(path)
            return

        faiss.write_index(self._index, self._index_path)
        with open(self._meta_path, "wb") as f:
            pickle.dump(self._metadata, f)

    def add(self, embeddings: np.ndarray, chunks: List[IndexedChunk]):
        import faiss

        assert len(embeddings) == len(chunks)
        dim = embeddings.shape[1]
        if self._index is None:
            self._index = faiss.IndexFlatIP(dim)  # inner product trên vector đã L2-normalize = cosine similarity
        self._index.add(embeddings)
        self._metadata.extend(chunks)
        self._save()

    def search(self, query_embedding: np.ndarray, top_k: int = 5, document_ids=None):
        if self._index is None or self._index.ntotal == 0:
            return []

        scores, indices = self._index.search(query_embedding.reshape(1, -1), min(top_k * 3, self._index.ntotal))
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:
                continue
            chunk = self._metadata[idx]
            if document_ids is not None and chunk.document_id not in document_ids:
                continue
            results.append((chunk, float(score)))
            if len(results) >= top_k:
                break
        return results

    def hybrid_search(self, query: str, query_embedding: np.ndarray, candidate_pool: int = 20, document_ids=None):
        """Gộp dense retrieval (cosine similarity) + BM25 (lexical) qua
        Reciprocal Rank Fusion — trả về TỐI ĐA candidate_pool ứng viên đã lọc
        theo document_ids, CHƯA rerank. Dùng app/retrieval/reranker.py để
        rerank và cắt về top_k cuối cùng (xem app/retrieval/pipeline.py).

        Fuse trên TOÀN BỘ corpus của user rồi mới lọc document_ids — cùng
        cách tiếp cận với search() ở trên (đơn giản, chấp nhận được ở quy mô
        MVP mỗi user có index riêng, không quá lớn)."""
        if self._index is None or self._index.ntotal == 0:
            return []

        dense_k = min(candidate_pool, self._index.ntotal)
        _, indices = self._index.search(query_embedding.reshape(1, -1), dense_k)
        dense_ranked_ids = [self._metadata[idx].chunk_id for idx in indices[0] if idx != -1]

        bm25_index = Bm25Index(self._metadata)
        bm25_results = bm25_index.search(query, top_k=candidate_pool)
        bm25_ranked_ids = [chunk.chunk_id for chunk, _ in bm25_results]

        fused_scores = reciprocal_rank_fusion([dense_ranked_ids, bm25_ranked_ids])
        chunks_by_id = {c.chunk_id: c for c in self._metadata}

        candidates = []
        for chunk_id, _ in sorted(fused_scores.items(), key=lambda item: item[1], reverse=True):
            chunk = chunks_by_id[chunk_id]
            if document_ids is not None and chunk.document_id not in document_ids:
                continue
            candidates.append(chunk)
            if len(candidates) >= candidate_pool:
                break
        return candidates

    def remove_document(self, document_id: str):
        """Xoá toàn bộ chunk thuộc một document khỏi index, dựng lại index từ các vector còn lại.

        IndexFlatIP không hỗ trợ xoá theo id trực tiếp nên phải reconstruct toàn bộ
        vector còn giữ lại và build index mới — chấp nhận được vì mỗi user có index
        riêng và quy mô nhỏ (MVP).
        """
        import faiss

        if self._index is None or self._index.ntotal == 0:
            return

        keep_indices = [i for i, chunk in enumerate(self._metadata) if chunk.document_id != document_id]
        if len(keep_indices) == len(self._metadata):
            return

        if not keep_indices:
            self._index = None
            self._metadata = []
        else:
            vectors = self._index.reconstruct_n(0, self._index.ntotal)
            kept_vectors = vectors[keep_indices]
            new_index = faiss.IndexFlatIP(kept_vectors.shape[1])
            new_index.add(kept_vectors)
            self._index = new_index
            self._metadata = [self._metadata[i] for i in keep_indices]

        self._save()
