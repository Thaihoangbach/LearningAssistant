"""Chỉ mục BM25 (lexical/keyword retrieval) — bổ sung cho dense retrieval
(embedder.py + FAISS) để bắt được các thuật ngữ hiếm/chính xác mà dense
embedding có thể bỏ sót (vd tên riêng, ký hiệu công thức).

Tokenizer ở đây CHỈ tách theo \\w+ + lowercase — không phải word
segmentation tiếng Việt thật (loại "học_máy" thành 1 từ...). Đây là baseline
đơn giản chấp nhận được cho MVP; nếu cần chính xác hơn, thay _tokenize bằng
một bộ tách từ tiếng Việt thật (vd underthesea, pyvi).

Build lại từ đầu mỗi lần gọi UserVectorStore.hybrid_search() — chấp nhận
được vì mỗi user có corpus nhỏ (cùng lý do đã chấp nhận trong
faiss_store.py::remove_document).
"""

import re
from typing import List, Tuple

from rank_bm25 import BM25Okapi

from app.vectorstore.types import IndexedChunk

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def _tokenize(text: str) -> List[str]:
    return _TOKEN_RE.findall(text.lower())


class Bm25Index:
    def __init__(self, chunks: List[IndexedChunk]):
        self._chunks = chunks
        self._bm25 = BM25Okapi([_tokenize(c.text) for c in chunks]) if chunks else None

    def search(self, query: str, top_k: int) -> List[Tuple[IndexedChunk, float]]:
        if self._bm25 is None:
            return []

        # LƯU Ý: điểm BM25 CÓ THỂ âm với corpus nhỏ (idf âm khi 1 từ xuất
        # hiện ở hầu hết/mọi document — quirk đã biết của công thức Okapi
        # BM25 chuẩn, không phải lỗi). Vì vậy KHÔNG lọc theo dấu điểm số —
        # chỉ loại các chunk hoàn toàn không có từ nào trùng với câu hỏi
        # (điểm đúng bằng 0.0 tuyệt đối, không phải làm tròn). Điểm tương
        # đối vẫn dùng đúng để xếp hạng vì RRF (app/vectorstore/hybrid.py)
        # chỉ quan tâm THỨ HẠNG, không quan tâm giá trị điểm tuyệt đối.
        scores = self._bm25.get_scores(_tokenize(query))
        ranked_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        return [(self._chunks[i], float(scores[i])) for i in ranked_indices if scores[i] != 0.0]
