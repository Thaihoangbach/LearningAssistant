"""Kiểu dữ liệu dùng chung cho một đoạn trích đã chunk — độc lập với nơi lưu
trữ (app/vectorstore/pgvector_store.py) để module đó và các nơi gọi
(app/ingestion/pipeline.py, app/retrieval/*.py) không phụ thuộc vòng lẫn
nhau."""

from dataclasses import dataclass


@dataclass
class IndexedChunk:
    chunk_id: str
    document_id: str
    document_name: str
    position_ref: str
    text: str
    # Xem app/ingestion/chunker.py::Chunk.section_index — mặc định None cho
    # chunk dựng tay ở test cũ/nơi khác chưa quan tâm structural retrieval.
    section_index: "int | None" = None
