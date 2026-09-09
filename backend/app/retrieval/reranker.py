"""Rerank danh sách chunk ứng viên (sau hybrid retrieval) bằng Cohere Rerank
API — trước đây dùng cross-encoder cục bộ (sentence-transformers), đổi sang
Cohere cùng lý do và cùng provider với embedder.py: bỏ được torch/
sentence-transformers khỏi image, chỉ cần một COHERE_API_KEY.

`RerankerClient` là Protocol tối thiểu (giống LLMClient ở app/llm/rag.py) để
rerank() test được bằng fake reranker, không cần key/network thật — xem
tests/test_reranker.py. `rerank()` (hàm thuần bên dưới) giữ NGUYÊN, không đổi
gì: nó chỉ biết gọi `.score(query, texts) -> List[float]` rồi tự sigmoid +
sắp xếp + cắt top_k, không quan tâm điểm đến từ đâu.

`CohereReranker.score()` phải trả về ĐÚNG một điểm cho MỖI text trong texts,
theo ĐÚNG THỨ TỰ đầu vào (hợp đồng của RerankerClient) — nhưng Cohere rerank
trả về danh sách KẾT QUẢ đã xếp hạng lại kèm `index` trỏ ngược về vị trí gốc,
không phải một mảng song song. Gọi với `top_n=len(texts)` để luôn nhận đủ
điểm cho mọi text, rồi dựng lại đúng thứ tự gốc theo `index`.

Cohere trả `relevance_score` đã CHUẨN HOÁ về [0, 1] (không phải logit thô như
cross-encoder cũ) — nhưng `rerank()` bên dưới áp `_sigmoid()` lên MỌI điểm
nhận được, y hệt như với logit của cross-encoder cũ. Để không phải sửa/nhân
đôi logic của `rerank()`, `score()` trả về LOGIT NGƯỢC của relevance_score
(`_logit`, nghịch đảo của sigmoid) — `sigmoid(logit(p)) == p`, nên điểm cuối
cùng người dùng thấy vẫn đúng bằng relevance_score gốc của Cohere, không bị
nén lại qua hai lớp biến đổi chồng nhau.
"""

import math
import os
from functools import lru_cache
from typing import List, Protocol, Tuple

from app.vectorstore.types import IndexedChunk

DEFAULT_RERANK_MODEL = "rerank-multilingual-v3.0"

# Kẹp trước khi lấy logit — relevance_score đúng 0 hoặc 1 làm ln(p/(1-p))
# thành ±vô cực. Biên rất sát 0/1 nên không ảnh hưởng thứ hạng thực tế.
_CLIP_EPSILON = 1e-6


class RerankerClient(Protocol):
    def score(self, query: str, texts: List[str]) -> List[float]: ...


@lru_cache(maxsize=1)
def _get_cohere_client():
    import cohere

    # .strip(): cùng lý do ở app/ingestion/embedder.py::_get_client() — key
    # dính newline/khoảng trắng thừa làm header "Bearer ..." bị httpx từ
    # chối (LocalProtocolError) thay vì lỗi xác thực bình thường.
    api_key = (os.environ.get("COHERE_API_KEY") or "").strip()
    if not api_key:
        raise ValueError(
            "Thiếu COHERE_API_KEY. Lấy key tại https://dashboard.cohere.com/api-keys "
            "và đặt vào biến môi trường."
        )
    return cohere.ClientV2(api_key=api_key)


def clear_client_cache() -> None:
    """Chỉ dùng trong test — dọn cache client giữa các trường hợp kiểm thử."""
    _get_cohere_client.cache_clear()


def _logit(p: float) -> float:
    p = min(max(p, _CLIP_EPSILON), 1 - _CLIP_EPSILON)
    return math.log(p / (1 - p))


class CohereReranker:
    def __init__(self, model_name: str = None):
        self.model_name = model_name or os.environ.get("COHERE_RERANK_MODEL", DEFAULT_RERANK_MODEL)

    def score(self, query: str, texts: List[str]) -> List[float]:
        if not texts:
            return []

        client = _get_cohere_client()
        response = client.rerank(
            model=self.model_name,
            query=query,
            documents=list(texts),
            top_n=len(texts),
        )

        scores: List[float] = [None] * len(texts)  # type: ignore[list-item]
        for result in response.results:
            scores[result.index] = _logit(result.relevance_score)

        # Phòng hờ Cohere trả thiếu kết quả cho vài text (không nên xảy ra
        # khi top_n=len(texts), nhưng không để None lọt xuống _sigmoid()).
        return [s if s is not None else _logit(_CLIP_EPSILON) for s in scores]


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
