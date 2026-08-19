"""Reciprocal Rank Fusion (RRF) — gộp nhiều danh sách xếp hạng (dense, BM25)
thành một điểm số duy nhất, KHÔNG cần chuẩn hoá thang điểm giữa các phương
pháp khác nhau (cosine similarity ~ [-1, 1] vs điểm BM25 không giới hạn) —
đây là lý do chọn RRF thay vì cộng trọng số trực tiếp hai loại điểm.

Công thức chuẩn: score(doc) = sum(1 / (k + rank)) trên mọi danh sách mà doc
xuất hiện, k=60 là hằng số phổ biến trong literature (Cormack et al., 2009).

Pure function, không phụ thuộc FAISS/BM25 thật — test bằng
tests/test_hybrid.py.
"""

from typing import Dict, List


def reciprocal_rank_fusion(ranked_lists: List[List[str]], k: int = 60) -> Dict[str, float]:
    """Mỗi phần tử của ranked_lists là một danh sách id (vd chunk_id) đã sắp
    xếp giảm dần theo độ liên quan. Trả về dict id -> điểm RRF (càng cao
    càng liên quan), gồm mọi id xuất hiện ở ÍT NHẤT một danh sách."""
    scores: Dict[str, float] = {}
    for ranked in ranked_lists:
        for rank, item_id in enumerate(ranked, start=1):
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + rank)
    return scores
