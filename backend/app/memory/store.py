"""FAISS index RIÊNG cho ký ức episodic, tách hẳn khỏi index tài liệu.

Cố tình KHÔNG tái dùng app/vectorstore/faiss_store.py::UserVectorStore: lớp đó
mang những mối bận tâm chỉ đúng với tài liệu (remove_document, hybrid_search
kèm BM25, lọc theo document_ids), và ép ký ức vào các trường document_id /
position_ref sẽ là lạm dụng tên trường, khiến cả hai phía khó đọc. Chấp nhận
trùng khoảng 30 dòng logic nạp/ghi FAISS để đổi lấy hai đơn vị có ranh giới
sạch.

Mỗi user một file index riêng — cùng nguyên tắc cách ly dữ liệu đã áp dụng cho
vector store tài liệu: không có cách nào truy hồi lẫn sang ký ức của người khác
vì index tách biệt vật lý.

CHƯA CHẠY ĐƯỢC TRONG SANDBOX NÀY: cần `pip install faiss-cpu`.
"""

import os
import pickle
from dataclasses import dataclass
from typing import List, Tuple

import numpy as np


@dataclass
class MemoryRecord:
    event_id: str
    text: str


class MemoryStore:
    def __init__(self, user_id: str, storage_dir: str = "./data/memory"):
        self.user_id = user_id
        self.storage_dir = storage_dir
        os.makedirs(storage_dir, exist_ok=True)
        self._index_path = os.path.join(storage_dir, f"{user_id}.faiss")
        self._meta_path = os.path.join(storage_dir, f"{user_id}.meta.pkl")
        self._index = None
        self._metadata: List[MemoryRecord] = []
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
            return
        faiss.write_index(self._index, self._index_path)
        with open(self._meta_path, "wb") as f:
            pickle.dump(self._metadata, f)

    def add(self, embeddings: np.ndarray, records: List[MemoryRecord]) -> None:
        import faiss

        assert len(embeddings) == len(records)
        if not records:
            return
        if self._index is None:
            # inner product trên vector đã L2-normalize = cosine similarity,
            # giống app/vectorstore/faiss_store.py
            self._index = faiss.IndexFlatIP(embeddings.shape[1])
        self._index.add(embeddings)
        self._metadata.extend(records)
        self._save()

    def search(self, query_embedding: np.ndarray, top_k: int = 20) -> List[Tuple[MemoryRecord, float]]:
        if self._index is None or self._index.ntotal == 0:
            return []

        scores, indices = self._index.search(
            query_embedding.reshape(1, -1), min(top_k, self._index.ntotal)
        )
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:
                continue
            results.append((self._metadata[idx], float(score)))
        return results
