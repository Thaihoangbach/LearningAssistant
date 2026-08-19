"""Rerank danh sách chunk ứng viên (sau hybrid retrieval) bằng cross-encoder
— chấm điểm liên quan trực tiếp giữa (câu hỏi, chunk) thay vì dựa vào
similarity gián tiếp qua embedding riêng lẻ như dense retrieval, nên chính
xác hơn ở bước cuối cùng khi chỉ còn một nhóm nhỏ ứng viên cần xếp hạng lại.

`RerankerClient` là Protocol tối thiểu (giống LLMClient ở app/llm/rag.py)
để rerank() test được bằng fake reranker, không cần tải model thật —
xem tests/test_reranker.py.

Điểm trả về được chuẩn hoá qua sigmoid về khoảng (0, 1) để tương thích với
ngưỡng `min_score` đã dùng cho cosine similarity trước đây (app/llm/rag.py) —
ý nghĩa ngưỡng đổi từ "độ giống ngữ nghĩa thô" sang "xác suất ước lượng chunk
liên quan tới câu hỏi", nhưng vẫn dùng chung một thang [0, 1] nên KHÔNG cần
đổi giá trị mặc định min_score=0.3 ở nơi gọi.
"""

import math
from typing import List, Protocol, Tuple

from app.vectorstore.faiss_store import IndexedChunk

DEFAULT_RERANKER_MODEL = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"


class RerankerClient(Protocol):
    def score(self, query: str, texts: List[str]) -> List[float]: ...


class CrossEncoderReranker:
    """Reranker thật, chạy LOCAL bằng sentence-transformers CrossEncoder —
    miễn phí, không tốn quota Gemini, giống lý do embedder.py dùng
    sentence-transformers cho bước embed thay vì gọi API."""

    def __init__(self, model_name: str = DEFAULT_RERANKER_MODEL):
        self.model_name = model_name
        self._model = None

    def _get_model(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(self.model_name)
        return self._model

    def score(self, query: str, texts: List[str]) -> List[float]:
        if not texts:
            return []
        model = self._get_model()
        pairs = [(query, text) for text in texts]
        return [float(s) for s in model.predict(pairs)]


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def rerank(
    query: str,
    candidates: List[IndexedChunk],
    reranker: RerankerClient,
    top_k: int,
) -> List[Tuple[IndexedChunk, float]]:
    if not candidates:
        return []

    raw_scores = reranker.score(query, [c.text for c in candidates])
    scored = [(chunk, _sigmoid(s)) for chunk, s in zip(candidates, raw_scores)]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored[:top_k]
