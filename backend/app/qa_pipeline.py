"""Điều phối hỏi đáp hai lượt và dựng bằng chứng phủ định (spec mục 4.1, 4.2).

Tách khỏi app/llm/rag.py vì rag.py cố ý KHÔNG biết gì về retrieval — nó chỉ
nhận sẵn danh sách đoạn trích. Cũng tách khỏi router để router không phình ra
và để logic này test được bằng fake, không cần faiss.

`retrieve_fn(query, top_k, mode)` được inject; router truyền vào một closure
bọc app/retrieval/pipeline.py::retrieve_chunks.
"""

from dataclasses import dataclass, field
from typing import Callable, List, Optional

from app.llm.rag import AnswerResult, RetrievedChunk, answer_question

MAX_NEAR_MISSES = 3


@dataclass
class NearMiss:
    chunk_id: str
    document_id: str
    document_name: str
    position_ref: str
    text: str
    score: float


@dataclass
class SearchReport:
    passes_run: int
    searched_documents: List[dict] = field(default_factory=list)
    near_misses: List[NearMiss] = field(default_factory=list)
    # Chủ đề tài liệu THỰC SỰ có, gần với câu hỏi nhất — để lời từ chối không
    # còn là ngõ cụt. Chỉ điền khi hệ thống từ chối.
    suggested_topics: List[str] = field(default_factory=list)


@dataclass
class QAResult:
    answer: str
    is_grounded: bool
    sources: List[RetrievedChunk] = field(default_factory=list)
    abstained: bool = False
    search_report: Optional[SearchReport] = None


def _abstention_message(passes_run: int, num_documents: int) -> str:
    return (
        f"Không tìm thấy nội dung này trong tài liệu của bạn. Hệ thống đã tìm "
        f"{passes_run} lượt (một lượt theo ngữ nghĩa và một lượt theo từ khoá) "
        f"trong {num_documents} tài liệu. Bên dưới là những đoạn gần đúng nhất "
        f"để bạn tự đối chiếu."
    )


def _dedupe_key(chunk: RetrievedChunk):
    # chunk_id là định danh thật; chỉ khi nó rỗng (đoạn dựng tay trong test cũ,
    # hoặc dữ liệu index cũ) mới lùi về cặp (tài liệu, vị trí).
    return chunk.chunk_id or (chunk.document_name, chunk.position_ref)


def _to_near_misses(chunks: List[RetrievedChunk], limit: int) -> List[NearMiss]:
    # Lượt gắt và lượt mở rộng gần như luôn trả về nhiều đoạn trùng nhau — nếu
    # không khử thì người dùng thấy cùng một đoạn lặp lại trong bằng chứng phủ
    # định. Giữ lần xuất hiện có điểm cao nhất.
    best_by_key = {}
    for c in chunks:
        key = _dedupe_key(c)
        if key not in best_by_key or c.score > best_by_key[key].score:
            best_by_key[key] = c

    ranked = sorted(best_by_key.values(), key=lambda c: c.score, reverse=True)[:limit]
    return [
        NearMiss(
            chunk_id=c.chunk_id,
            document_id=c.document_id,
            document_name=c.document_name,
            position_ref=c.position_ref,
            text=c.text,
            score=c.score,
        )
        for c in ranked
    ]


def answer_with_fallback(
    question: str,
    llm_client,
    retrieve_fn: Callable[..., List[RetrievedChunk]],
    searched_documents: List[dict],
    top_k: int = 5,
    min_score: float = 0.02,
    max_near_misses: int = MAX_NEAR_MISSES,
    retrieval_query: Optional[str] = None,
    suggest_topics_fn: Optional[Callable[[str], List[str]]] = None,
    **answer_kwargs,
) -> QAResult:
    """Chạy lượt truy hồi gắt trước; chỉ khi nó trượt mới chạy lượt mở rộng.

    "Trượt" nghĩa là không truy hồi được đoạn nào HOẶC verifier bác câu trả lời
    nháp — cả hai đều là dấu hiệu lượt đầu chưa tìm đúng chỗ."""
    passes_run = 0
    seen_chunks: List[RetrievedChunk] = []

    # Truy hồi dùng truy vấn đã bổ sung ngữ cảnh hội thoại
    # (app/retrieval/query_context.py); generator vẫn nhận câu hỏi GỐC để câu
    # trả lời bám đúng điều người dùng vừa hỏi.
    search_query = retrieval_query or question

    for mode in ("strict", "wide"):
        chunks = retrieve_fn(search_query, top_k, mode)
        passes_run += 1
        seen_chunks.extend(chunks)

        if not chunks:
            continue

        result: AnswerResult = answer_question(
            question=question,
            retrieved_chunks=chunks,
            llm_client=llm_client,
            min_score=min_score,
            **answer_kwargs,
        )
        if result.is_grounded:
            return QAResult(
                answer=result.answer,
                is_grounded=True,
                sources=result.sources,
                abstained=False,
                # Giữ báo cáo cả khi thành công để biết có phải nhờ lượt hai
                # mới tìm ra — số liệu này cần cho đánh giá ở giai đoạn E.
                search_report=SearchReport(
                    passes_run=passes_run, searched_documents=searched_documents
                ),
            )

    # Chỉ gợi ý chủ đề khi đã chắc chắn từ chối — tra cứu này chạm DB nên
    # không đáng làm ở nhánh trả lời được.
    suggested_topics = suggest_topics_fn(question) if suggest_topics_fn else []

    return QAResult(
        answer=_abstention_message(passes_run, len(searched_documents)),
        is_grounded=False,
        sources=[],
        abstained=True,
        search_report=SearchReport(
            passes_run=passes_run,
            searched_documents=searched_documents,
            near_misses=_to_near_misses(seen_chunks, max_near_misses),
            suggested_topics=suggested_topics,
        ),
    )
