"""Kiểu dữ liệu dùng chung giữa faiss_store.py và bm25_index.py — tách riêng
để tránh circular import (cả hai module đều cần biết cấu trúc IndexedChunk,
và faiss_store.py cũng cần gọi vào bm25_index.py cho hybrid_search())."""

from dataclasses import dataclass


@dataclass
class IndexedChunk:
    chunk_id: str
    document_id: str
    document_name: str
    position_ref: str
    text: str
