"""Rerank danh sách chunk ứng viên (sau hybrid retrieval) bằng cross-encoder
— chấm điểm liên quan trực tiếp giữa (câu hỏi, chunk) thay vì dựa vào
similarity gián tiếp qua embedding riêng lẻ như dense retrieval, nên chính
xác hơn ở bước cuối cùng khi chỉ còn một nhóm nhỏ ứng viên cần xếp hạng lại.

`RerankerClient` là Protocol tối thiểu (giống LLMClient ở app/llm/rag.py)
để rerank() test được bằng fake reranker, không cần tải model thật —
xem tests/test_reranker.py.

Điểm trả về được chuẩn hoá qua sigmoid về khoảng (0, 1).

LƯU Ý quan trọng rút ra từ test thực tế: điểm này KHÔNG đáng tin để dùng làm
ngưỡng "có liên quan hay không" một mình, vì cross-encoder được huấn luyện
trên câu hỏi factoid ngắn (kiểu MS MARCO) nên chấm rất thấp cho câu hỏi diễn
đạt tự nhiên/hội thoại dù nội dung đúng vẫn nằm trong ứng viên, và ngược lại
có thể chấm cao cho câu hỏi ngoài phạm vi tài liệu nhưng còn liên quan chủ đề.
Vì vậy `min_score` ở app/llm/rag.py::answer_question chỉ nên đặt rất thấp
(lọc trường hợp cực đoan để đỡ tốn lượt gọi LLM), còn việc phán đoán đúng/sai
thật sự giao cho bước verifier (LLM) phía sau, không giao cho điểm số này.
"""

import math
from typing import List, Protocol, Tuple

from app.vectorstore.faiss_store import IndexedChunk

DEFAULT_RERANKER_MODEL = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"

# Model được nạp MỘT LẦN cho mỗi tên model rồi tái dùng cho mọi lượt truy hồi.
# Không có cache này, app/retrieval/pipeline.py tạo một CrossEncoderReranker
# mới mỗi lần gọi và nạp lại model — đo được ~2,8s overhead mỗi lượt truy hồi,
# nhân đôi khi truy hồi hai lượt. Cùng khuôn với @lru_cache đã dùng ở
# app/ingestion/embedder.py cho model embedding.
_MODEL_CACHE: dict = {}


def _load_model(model_name: str):
    """Tách riêng phần nạp thật để test thay được bằng hàm giả."""
    from sentence_transformers import CrossEncoder

    return CrossEncoder(model_name)


def get_cached_model(model_name: str):
    if model_name not in _MODEL_CACHE:
        _MODEL_CACHE[model_name] = _load_model(model_name)
    return _MODEL_CACHE[model_name]


def clear_model_cache() -> None:
    """Chỉ dùng trong test — dọn cache giữa các trường hợp kiểm thử."""
    _MODEL_CACHE.clear()


class RerankerClient(Protocol):
    def score(self, query: str, texts: List[str]) -> List[float]: ...


class CrossEncoderReranker:
    """Reranker thật, chạy LOCAL bằng sentence-transformers CrossEncoder —
    miễn phí, không tốn quota Gemini, giống lý do embedder.py dùng
    sentence-transformers cho bước embed thay vì gọi API."""

    def __init__(self, model_name: str = DEFAULT_RERANKER_MODEL):
        self.model_name = model_name

    def _get_model(self):
        # Lấy từ cache cấp module chứ KHÔNG giữ trong instance: pipeline tạo
        # instance mới mỗi lượt truy hồi nên cache theo instance là vô dụng.
        return get_cached_model(self.model_name)

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
