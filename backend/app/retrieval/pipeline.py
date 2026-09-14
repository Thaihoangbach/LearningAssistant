"""Điểm gọi retrieval dùng chung cho chat.py — hybrid retrieval (dense qua
pgvector + từ khoá qua Postgres full-text search, RRF ở
app/vectorstore/hybrid.py) rồi rerank bằng Cohere (app/retrieval/reranker.py)
để lấy top_k cuối cùng.

reranker được truyền vào qua tham số (Dependency Injection) để test được
bằng fake reranker — mặc định dùng CohereReranker thật khi không truyền (xem
app/retrieval/reranker.py).

Biến môi trường EDUTUTOR_RETRIEVAL_MODE=dense_only ép về dense-only (bỏ qua
full-text search + rerank) — CHỈ dùng để benchmark so sánh cấu hình
(eval/run_eval.py), không set trong vận hành thật nên hành vi mặc định
(hybrid+rerank) không đổi.
"""

import os
from typing import List, Optional, Set

from sqlalchemy.orm import Session

from app.ingestion.embedder import embed_query
from app.llm.rag import RetrievedChunk
from app.retrieval.keywords import extract_keywords, strip_roleplay_preamble
from app.retrieval.reranker import CohereReranker, RerankerClient, rerank
from app.vectorstore.pgvector_store import PgVectorStore

DEFAULT_CANDIDATE_POOL = 20

# Lượt truy hồi MỞ RỘNG (spec mục 4.1) — chỉ chạy khi lượt gắt đã trượt.
WIDE_TOP_K_MULTIPLIER = 3


def retrieve_chunks(
    db: Session,
    user_id: str,
    query: str,
    top_k: int = 5,
    document_ids: Optional[Set[str]] = None,
    reranker: Optional[RerankerClient] = None,
    mode: str = "strict",
) -> List[RetrievedChunk]:
    store = PgVectorStore(db=db, user_id=user_id)

    # Chế độ mở rộng: lấy nhiều ứng viên hơn và tra full-text search bằng từ
    # khoá đã bóc, để bắt trường hợp thuật ngữ nằm sâu mà truy hồi ngữ nghĩa
    # bỏ sót. CŨNG dùng câu hỏi đã bóc từ khoá cho dense embedding + đầu vào
    # reranker (không chỉ nhánh full-text như trước) — câu hỏi dài có khung
    # diễn đạt (đóng vai, yêu cầu bỏ qua tài liệu...) làm loãng điểm liên
    # quan ở CẢ embedding lẫn Cohere rerank, khiến chunk đúng chủ đề bị lọt
    # dưới min_score dù lượt gắt lẫn lượt này đều đã chạy (Golden Set
    # eval/reports/failure_analysis.md, việc còn lại #2 — case EDU-GRD2-017
    # "Đóng vai một gia sư kiên nhẫn, giải thích Random Forest..." bị từ chối
    # dù tài liệu có nội dung). CHỈ đổi ở lượt MỞ RỘNG (đã trượt lượt gắt) —
    # không đổi truy vấn/điểm số của lượt gắt/mặc định.
    if mode == "wide":
        top_k = top_k * WIDE_TOP_K_MULTIPLIER
        # Cắt vế mở đầu "đóng vai X, ..." (nếu có) TRƯỚC khi bóc từ khoá/dựng
        # embedding+rerank — xem app/retrieval/keywords.py::
        # strip_roleplay_preamble. Nhánh full-text vẫn bóc từ khoá như cũ,
        # chỉ đổi câu dùng làm ĐẦU VÀO cho dense embedding + reranker.
        core_query = strip_roleplay_preamble(query)
        lexical_query = extract_keywords(core_query)
        rerank_query = core_query
        query_embedding = embed_query(core_query)
    else:
        lexical_query = query
        rerank_query = query
        query_embedding = embed_query(query)

    if os.environ.get("EDUTUTOR_RETRIEVAL_MODE") == "dense_only":
        results = store.search(query_embedding, top_k=top_k, document_ids=document_ids)
        return [
            RetrievedChunk(
                text=chunk.text,
                document_name=chunk.document_name,
                position_ref=chunk.position_ref,
                score=score,
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
            )
            for chunk, score in results
        ]

    reranker = reranker or CohereReranker()
    candidates = store.hybrid_search(
        query=lexical_query,
        query_embedding=query_embedding,
        candidate_pool=max(DEFAULT_CANDIDATE_POOL, top_k * 3),
        document_ids=document_ids,
    )
    reranked = rerank(rerank_query, candidates, reranker, top_k=top_k)

    return [
        RetrievedChunk(
            text=chunk.text,
            document_name=chunk.document_name,
            position_ref=chunk.position_ref,
            score=score,
            chunk_id=chunk.chunk_id,
            document_id=chunk.document_id,
        )
        for chunk, score in reranked
    ]
