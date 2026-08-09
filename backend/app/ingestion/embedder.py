"""Sinh vector embedding cho chunk — chạy LOCAL, miễn phí, không giới hạn.

Dùng sentence-transformers thay vì gọi API để dành quota Gemini free tier
cho bước generate/verify (xem architecture-diagrams.md mục 0). Model được
load một lần và tái sử dụng (tải model lần đầu cần mạng, các lần sau chạy
hoàn toàn offline).

CHƯA CHẠY ĐƯỢC TRONG SANDBOX NÀY: cần `pip install sentence-transformers`
(sandbox không có mạng). Cần cài đặt và chạy thử ở máy local trước khi tin
tưởng module này.
"""

from functools import lru_cache
from typing import List

import numpy as np

MODEL_NAME = "paraphrase-multilingual-mpnet-base-v2"


@lru_cache(maxsize=1)
def _get_model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(MODEL_NAME)


def embed_texts(texts: List[str]) -> np.ndarray:
    """Trả về ma trận (n_texts, dim) vector embedding, đã chuẩn hóa L2."""
    model = _get_model()
    embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return np.asarray(embeddings, dtype="float32")


def embed_query(text: str) -> np.ndarray:
    return embed_texts([text])[0]
