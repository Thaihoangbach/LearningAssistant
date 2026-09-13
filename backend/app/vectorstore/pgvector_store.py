"""Truy hồi hybrid (dense qua pgvector + từ khoá qua Postgres full-text
search) trên bảng `document_chunks` — thay cho FAISS/rank_bm25 cục bộ
(app/vectorstore/faiss_store.py, app/vectorstore/bm25_index.py, đã gỡ bỏ).

Cùng chữ ký phương thức với `UserVectorStore` cũ (`add`/`search`/
`hybrid_search`/`remove_document`) — nơi gọi (app/ingestion/pipeline.py,
app/retrieval/pipeline.py, app/routers/*.py) chỉ đổi cách khởi tạo (cần thêm
`db: Session`), không đổi cách dùng.

Khác biệt cốt lõi so với bản FAISS: mỗi lượt gọi giờ là một truy vấn SQL
trong transaction của REQUEST đang chạy, không phải nạp/ghi đè nguyên một
file trên đĩa — Postgres tự lo tính đúng đắn khi nhiều request chạy đồng thời
(chính là BUG-2 trước đây phải vá tạm bằng khoá app/concurrency.py).

`add()`/`remove_document()` CHỈ `flush()`, KHÔNG tự `commit()` — quyền quyết
định lúc nào commit thuộc về phía gọi, dùng CHUNG session/transaction với
các thay đổi khác của cùng lượt xử lý. Đây là điểm sửa ARCH-3 (trước đây xoá
tài liệu là 2 lệnh COMMIT rời nhau — xoá xong vector rồi mới xoá Document —
lỗi giữa chừng để lại Document đã xoá dở, chunk còn nguyên trong index):
app/routers/documents.py::delete_document giờ gộp chung một `db.commit()`
cuối cùng, xoá chunk và xoá Document cùng-thành-công hoặc cùng-rollback.
`flush()` vẫn cần để các thay đổi VỪA gọi hiện ra ngay cho câu SELECT tiếp
theo trong CÙNG transaction (session dùng autoflush=False)."""

from typing import List, Optional, Set, Tuple

import numpy as np
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models import DocumentChunk
from app.vectorstore.hybrid import reciprocal_rank_fusion
from app.vectorstore.types import IndexedChunk

# 'simple' — KHÔNG stemming tiếng Việt (chỉ tách từ + hạ chữ thường). Áp
# stemmer 'english' lên nội dung tiếng Việt sẽ cắt sai hình vị. Phải khớp
# CHÍNH XÁC config đã dùng để tạo index GIN hàm ở migration (xem
# alembic/versions/835b411f101a_initial_schema.py) — lệch config thì
# Postgres không dùng được index, phải full scan.
_FTS_CONFIG = "simple"


def _to_indexed_chunk(row: DocumentChunk) -> IndexedChunk:
    return IndexedChunk(
        chunk_id=row.id,
        document_id=row.document_id,
        document_name=row.document_name,
        position_ref=row.position_ref,
        text=row.text,
        section_index=row.section_index,
    )


class PgVectorStore:
    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id

    def add(self, embeddings: np.ndarray, chunks: List[IndexedChunk]) -> None:
        assert len(embeddings) == len(chunks)
        if not chunks:
            return

        for embedding, chunk in zip(embeddings, chunks):
            self.db.add(
                DocumentChunk(
                    id=chunk.chunk_id,
                    user_id=self.user_id,
                    document_id=chunk.document_id,
                    document_name=chunk.document_name,
                    position_ref=chunk.position_ref,
                    text=chunk.text,
                    embedding=embedding,
                    section_index=chunk.section_index,
                )
            )
        self.db.flush()

    def _dense_query(self, query_embedding: np.ndarray, top_k: int, document_ids: Optional[Set[str]]):
        stmt = (
            select(DocumentChunk, DocumentChunk.embedding.cosine_distance(query_embedding).label("distance"))
            .where(DocumentChunk.user_id == self.user_id)
        )
        if document_ids is not None:
            stmt = stmt.where(DocumentChunk.document_id.in_(document_ids))
        stmt = stmt.order_by("distance").limit(top_k)
        return self.db.execute(stmt).all()

    def search(
        self, query_embedding: np.ndarray, top_k: int = 5, document_ids: Optional[Set[str]] = None
    ) -> List[Tuple[IndexedChunk, float]]:
        rows = self._dense_query(query_embedding, top_k, document_ids)
        # cosine_distance = 1 - cosine_similarity (pgvector) — chuyển lại về
        # similarity để giữ đúng thang điểm mà code gọi (routers, mastery
        # gating...) đã quen dùng với FAISS IndexFlatIP (cosine similarity).
        return [(_to_indexed_chunk(chunk), 1.0 - float(distance)) for chunk, distance in rows]

    def _keyword_query(self, query: str, top_k: int, document_ids: Optional[Set[str]]):
        tsquery = func.plainto_tsquery(_FTS_CONFIG, query)
        tsvector = func.to_tsvector(_FTS_CONFIG, DocumentChunk.text)
        stmt = (
            select(DocumentChunk)
            .where(DocumentChunk.user_id == self.user_id, tsvector.op("@@")(tsquery))
        )
        if document_ids is not None:
            stmt = stmt.where(DocumentChunk.document_id.in_(document_ids))
        stmt = stmt.order_by(func.ts_rank(tsvector, tsquery).desc()).limit(top_k)
        return self.db.execute(stmt).scalars().all()

    def hybrid_search(
        self,
        query: str,
        query_embedding: np.ndarray,
        candidate_pool: int = 20,
        document_ids: Optional[Set[str]] = None,
    ) -> List[IndexedChunk]:
        """Gộp dense retrieval (cosine similarity) + full-text search (từ
        khoá) qua Reciprocal Rank Fusion — trả về TỐI ĐA candidate_pool ứng
        viên, CHƯA rerank. Dùng app/retrieval/reranker.py để rerank và cắt về
        top_k cuối cùng (xem app/retrieval/pipeline.py)."""
        dense_rows = self._dense_query(query_embedding, candidate_pool, document_ids)
        dense_ranked_ids = [chunk.id for chunk, _ in dense_rows]

        keyword_rows = self._keyword_query(query, candidate_pool, document_ids)
        keyword_ranked_ids = [chunk.id for chunk in keyword_rows]

        fused_scores = reciprocal_rank_fusion([dense_ranked_ids, keyword_ranked_ids])
        if not fused_scores:
            return []

        chunks_by_id = {chunk.id: chunk for chunk, _ in dense_rows}
        chunks_by_id.update({chunk.id: chunk for chunk in keyword_rows})

        ranked_ids = sorted(fused_scores.items(), key=lambda item: item[1], reverse=True)
        return [_to_indexed_chunk(chunks_by_id[chunk_id]) for chunk_id, _ in ranked_ids[:candidate_pool]]

    def remove_document(self, document_id: str) -> None:
        self.db.execute(
            delete(DocumentChunk).where(
                DocumentChunk.user_id == self.user_id, DocumentChunk.document_id == document_id
            )
        )
        self.db.flush()
