"""Vận dụng một khái niệm vào ví dụ/bài tập cụ thể — dùng CHÍNH retrieval ngữ
nghĩa top-k như hỏi đáp thường (không cần phủ hết một chương như Tóm tắt, và
không cần tách hai vế như So sánh); phần khác biệt duy nhất với hỏi đáp thường
là OUTPUT CONTRACT — ép sinh đúng 3 phần (nhắc khái niệm, ví dụ áp dụng, giải
thích) thay vì để generator tự do (xem app/llm/rag.py::_APPLY_OUTPUT_INSTRUCTION).

Verifier hiện có ĐÃ cho phép "ví dụ minh hoạ hợp lý" cho một khái niệm có căn
cứ trong đoạn trích (app/llm/rag.py::_build_claim_verifier_prompt), nên không
cần sửa gì ở bước xác thực — chỉ cần thêm output_style="apply" là đủ.

Đây là một trong ba intent có output contract riêng đã thống nhất khi thảo
luận thiết kế (Compare/Summarize/Apply) — bảy intent còn lại tiếp tục dùng
đường RAG chung ở app/routers/chat.py, không qua module này.

`is_apply_request` dùng regex thuần, KHÔNG gọi LLM — cùng nguyên tắc rẻ-trước-
đắt-sau đã áp dụng cho app/services/summarize.py và app/services/compare.py."""

import re
from typing import Optional, Set

from sqlalchemy.orm import Session

from app.llm.rag import AnswerResult, LLMClient, answer_question
from app.retrieval.pipeline import retrieve_chunks

_APPLY_INTENT_RE = re.compile(
    r"áp dụng|vận dụng|cho (một |1 )?ví dụ (áp dụng|vận dụng)|"
    r"bài tập (áp dụng|vận dụng)|apply .+ to|worked example|practice problem",
    re.IGNORECASE,
)

# Retrieval y hệt hỏi đáp thường — không cần phủ hết một chương (khác Tóm tắt)
# và không cần tách hai vế (khác So sánh).
TOP_K = 5


def is_apply_request(question: str) -> bool:
    return bool(_APPLY_INTENT_RE.search(question))


def build_apply_result(
    db: Session,
    user_id: str,
    document_ids: Optional[Set[str]],
    question: str,
    llm_client: LLMClient,
) -> AnswerResult:
    chunks = retrieve_chunks(db=db, user_id=user_id, query=question, top_k=TOP_K, document_ids=document_ids)
    return answer_question(
        question=question,
        retrieved_chunks=chunks,
        llm_client=llm_client,
        output_style="apply",
    )
