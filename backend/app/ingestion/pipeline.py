"""Nối các bước parse -> chunk -> embed -> lưu vector store (F1).

Đây là hàm orchestration chạy trong background task khi người dùng tải tài
liệu lên (xem sequence diagram F1 trong architecture-diagrams.md). Tách
riêng khỏi router để test được logic orchestration độc lập với FastAPI.

Phần parser + chunker bên trong ĐÃ được test riêng (test_parser.py,
test_chunker.py); phần embed+lưu vector cần Postgres+pgvector thật, xem
tests/test_pipeline.py (dùng tests/pg_test_helpers.py).
"""

import uuid

from sqlalchemy.orm import Session

from app.ingestion.chunker import chunk_sections
from app.ingestion.embedder import embed_texts
from app.ingestion.parser import parse_document
from app.vectorstore.pgvector_store import PgVectorStore
from app.vectorstore.types import IndexedChunk


def process_document(
    db: Session,
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

    KHÔNG tự `db.commit()` — caller (app/routers/documents.py::
    _run_processing_job) commit một lần cho cả job (parse+embed+lưu chunk +
    lưu dàn ý + đổi status), để một lỗi giữa chừng không để lại nửa chunk đã
    lưu mà status vẫn còn "đang xử lý"."""
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
            section_index=c.section_index,
        )
        for c in chunks
    ]

    store = PgVectorStore(db=db, user_id=user_id)
    store.add(embeddings, indexed_chunks)

    return len(chunks)
