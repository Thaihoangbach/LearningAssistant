"""Điểm gọi retrieval dùng chung cho chat.py — hybrid retrieval (dense + BM25
qua RRF, app/vectorstore/hybrid.py) rồi rerank bằng cross-encoder
(app/retrieval/reranker.py) để lấy top_k cuối cùng.

reranker được truyền vào qua tham số (Dependency Injection) để test được
bằng fake reranker — mặc định dùng CrossEncoderReranker thật khi không
truyền (xem app/retrieval/reranker.py).

Biến môi trường EDUTUTOR_RETRIEVAL_MODE=dense_only ép về dense-only (bỏ qua
BM25 + rerank) — CHỈ dùng để benchmark so sánh cấu hình (eval/run_eval.py),
không set trong vận hành thật nên hành vi mặc định (hybrid+rerank) không đổi.
"""

import os
from typing import List, Optional, Set

from app.ingestion.embedder import embed_query
from app.llm.rag import RetrievedChunk
from app.retrieval.reranker import CrossEncoderReranker, RerankerClient, rerank
from app.vectorstore.faiss_store import UserVectorStore

DEFAULT_CANDIDATE_POOL = 20


def retrieve_chunks(
    user_id: str,
    query: str,
    top_k: int = 5,
    document_ids: Optional[Set[str]] = None,
    reranker: Optional[RerankerClient] = None,
) -> List[RetrievedChunk]:
    store = UserVectorStore(user_id=user_id)
    query_embedding = embed_query(query)

    if os.environ.get("EDUTUTOR_RETRIEVAL_MODE") == "dense_only":
        results = store.search(query_embedding, top_k=top_k, document_ids=document_ids)
        return [
            RetrievedChunk(text=chunk.text, document_name=chunk.document_name, position_ref=chunk.position_ref, score=score)
            for chunk, score in results
        ]

    reranker = reranker or CrossEncoderReranker()
    candidates = store.hybrid_search(
        query=query,
        query_embedding=query_embedding,
        candidate_pool=max(DEFAULT_CANDIDATE_POOL, top_k * 3),
        document_ids=document_ids,
    )
    reranked = rerank(query, candidates, reranker, top_k=top_k)

    return [
        RetrievedChunk(text=chunk.text, document_name=chunk.document_name, position_ref=chunk.position_ref, score=score)
        for chunk, score in reranked
    ]
