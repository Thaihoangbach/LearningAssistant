"""Sinh vector embedding cho chunk — gọi Cohere Embed API.

Trước đây dùng sentence-transformers chạy LOCAL (miễn phí nhưng kéo theo
torch + tải model ~1GB, không deploy được lên host không có đĩa bền vững/
không đủ RAM cho free tier). Cohere free tier đủ dùng cho quy mô cá nhân,
đổi lấy: image nhẹ hơn nhiều, không cần tải model lúc cold start, và cùng
provider với bước rerank (app/retrieval/reranker.py) — chỉ cần một
COHERE_API_KEY duy nhất.

`embed-multilingual-v3.0`: 1024 chiều, hỗ trợ tiếng Việt tốt — khớp đúng
kiểu dữ liệu (tài liệu học tập tiếng Việt) mà paraphrase-multilingual-MiniLM
trước đây phục vụ.

`input_type` phân biệt "search_document" (nội dung được lập chỉ mục, dùng khi
add tài liệu — app/ingestion/pipeline.py) và "search_query" (câu hỏi/truy vấn
dùng để tìm, mọi nơi khác gọi `embed_query`) — Cohere v3 khuyến nghị tách hai
loại này để tối ưu chất lượng truy hồi, khác hẳn sentence-transformers cũ
(không phân biệt gì).

Giữ NGUYÊN chữ ký `embed_texts(texts) -> np.ndarray` / `embed_query(text) ->
np.ndarray` (vector đã chuẩn hoá L2) như bản cũ — mọi nơi gọi hàm này
(pipeline.py, retrieval/pipeline.py, memory/service.py, routers/quiz.py,
routers/flashcard.py) không cần đổi gì.
"""

import os
from functools import lru_cache
from typing import List

import numpy as np

EMBED_MODEL = os.environ.get("COHERE_EMBED_MODEL", "embed-multilingual-v3.0")

# Cohere giới hạn tối đa 96 text/lần gọi — một tài liệu dài chunk ra vài trăm
# đoạn vẫn phải tách thành nhiều lượt gọi.
_MAX_TEXTS_PER_CALL = 96


@lru_cache(maxsize=1)
def _get_client():
    import cohere

    # .strip(): key dán vào biến môi trường (Render...) dễ dính thêm khoảng
    # trắng/newline ở đầu/cuối — header "Bearer <key>\n" chứa newline bị
    # httpx từ chối thẳng với LocalProtocolError, sập MỌI request cần embed.
    api_key = (os.environ.get("COHERE_API_KEY") or "").strip()
    if not api_key:
        raise ValueError(
            "Thiếu COHERE_API_KEY. Lấy key tại https://dashboard.cohere.com/api-keys "
            "và đặt vào biến môi trường."
        )
    return cohere.ClientV2(api_key=api_key)


def _normalize(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0  # tránh chia 0 cho vector toàn số 0 (text rỗng)
    return vectors / norms


def _embed_batch(texts: List[str], input_type: str) -> np.ndarray:
    client = _get_client()
    response = client.embed(
        model=EMBED_MODEL,
        input_type=input_type,
        texts=texts,
        embedding_types=["float"],
    )
    return np.asarray(response.embeddings.float, dtype="float32")


def embed_texts(texts: List[str], input_type: str = "search_document") -> np.ndarray:
    """Trả về ma trận (n_texts, dim) vector embedding, đã chuẩn hóa L2."""
    if not texts:
        return np.zeros((0, 0), dtype="float32")

    batches = [
        texts[i : i + _MAX_TEXTS_PER_CALL] for i in range(0, len(texts), _MAX_TEXTS_PER_CALL)
    ]
    parts = [_embed_batch(batch, input_type) for batch in batches]
    combined = parts[0] if len(parts) == 1 else np.concatenate(parts, axis=0)
    return _normalize(combined)


def embed_query(text: str) -> np.ndarray:
    return embed_texts([text], input_type="search_query")[0]
