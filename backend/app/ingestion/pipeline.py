"""Nối các bước parse -> chunk -> embed -> lưu vector store (F1).

Đây là hàm orchestration chạy trong background task khi người dùng tải tài
liệu lên (xem sequence diagram F1 trong architecture-diagrams.md). Tách
riêng khỏi router để test được logic orchestration độc lập với FastAPI.

CHƯA CHẠY END-TO-END ĐƯỢC TRONG SANDBOX NÀY vì phụ thuộc embedder.py và
faiss_store.py (cần sentence-transformers, faiss — chưa cài được). Phần
parser + chunker bên trong ĐÃ được test riêng và pass (test_parser.py,
test_chunker.py).
"""

import uuid

from app.ingestion.chunker import chunk_sections
from app.ingestion.embedder import embed_texts
from app.ingestion.parser import parse_document
from app.vectorstore.faiss_store import IndexedChunk, UserVectorStore


def process_document(
    file_path: str,
    document_id: str,
    document_name: str,
    user_id: str,
    max_chars: int = 800,
    overlap_chars: int = 100,
) -> int:
    """Xử lý một tài liệu đã tải lên: trả về số chunk đã index.

    Ném exception nếu bước nào lỗi — caller (router) chịu trách nhiệm bắt
    lỗi và cập nhật Document.status = "lỗi" kèm error_reason, đúng AC F1.
    """
    sections = parse_document(file_path)
    chunks = chunk_sections(sections, max_chars=max_chars, overlap_chars=overlap_chars)

    if not chunks:
        raise ValueError("Tài liệu không có nội dung text trích xuất được.")

    texts = [c.text for c in chunks]
    embeddings = embed_texts(texts)

    indexed_chunks = [
        IndexedChunk(
            chunk_id=str(uuid.uuid4()),
            document_id=document_id,
            document_name=document_name,
            position_ref=c.position_ref,
            text=c.text,
        )
        for c in chunks
    ]

    store = UserVectorStore(user_id=user_id)
    store.add(embeddings, indexed_chunks)

    return len(chunks)
