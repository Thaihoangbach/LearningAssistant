# Giai đoạn C — Truy hồi hai lượt, bằng chứng phủ định, citation ba lớp: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Làm cho lời từ chối của hệ thống kiểm chứng được, và làm cho mỗi luận
điểm trong câu trả lời truy được về đúng đoạn tài liệu sinh ra nó.

**Architecture:** Khi lượt truy hồi đầu trượt, một lượt thứ hai mở rộng theo từ
khoá chạy trước khi kết luận "không có". Từ chối kèm bằng chứng phủ định (đã
tìm ở đâu, những đoạn gần đúng nhất). Generator gắn `[n]` theo từng luận điểm,
hậu kiểm loại marker trỏ sai. Việc điều phối hai lượt nằm ở module riêng
`app/qa_pipeline.py` chứ không nhét vào router hay vào `rag.py` — `rag.py` cố ý
không biết gì về retrieval.

**Tech Stack:** Python 3.12, FastAPI 0.115, SQLAlchemy 2.0.35, unittest.

**Spec:** `docs/superpowers/specs/2026-08-28-edututor-completion-design.md` (mục 4)

## Global Constraints

- Test chạy bằng `python -m unittest discover -s tests` từ `backend/`, dùng interpreter `venv/Scripts/python.exe`. Không dùng pytest.
- Mọi file test bắt đầu bằng `sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))`.
- Comment và docstring tiếng Việt.
- Module thuần không được import faiss/sentence-transformers/FastAPI; dependency nặng chỉ import lười trong hàm.
- Lượt truy hồi thứ hai CHỈ chạy khi lượt một trượt — không được chạy vô điều kiện (giới hạn chi phí, spec mục 4.1).
- Việc tô sáng câu chống đỡ tính bằng trùng lặp từ vựng, KHÔNG gọi LLM (spec mục 4.3, lớp 2).
- `REQUIRE_INLINE_CITATION` phải bật/tắt được để chạy ablation ở giai đoạn E.

---

### Task 1: RetrievedChunk mang được định danh đoạn

**Files:**
- Modify: `backend/app/llm/rag.py` (dataclass `RetrievedChunk`)
- Modify: `backend/app/retrieval/pipeline.py` (hai chỗ dựng `RetrievedChunk`)
- Modify: `backend/app/routers/quiz.py` (một chỗ dựng `RetrievedChunk`)
- Test: `backend/tests/test_rag.py`

**Interfaces:**
- Produces: `RetrievedChunk(text, document_name, position_ref, score, chunk_id: str = "", document_id: str = "")`

Hai trường mới có giá trị mặc định `""` nên mọi lời gọi hiện có (kể cả trong
test cũ) vẫn chạy — bắt buộc, vì `RetrievedChunk` đang được dựng ở nhiều nơi.

- [ ] **Step 1: Write the failing test**

Thêm vào `backend/tests/test_rag.py`, trong `class TestAnswerQuestion`:

```python
    def test_sources_carry_chunk_and_document_ids(self):
        llm = FakeLLMClient(scripted_responses=["Câu trả lời. [1]", "CÓ"])
        chunk = RetrievedChunk(
            text="Nội dung nguồn.",
            document_name="slide1.pdf",
            position_ref="Trang 1",
            score=0.8,
            chunk_id="chunk-abc",
            document_id="doc-xyz",
        )
        result = answer_question(question="Hỏi gì đó?", retrieved_chunks=[chunk], llm_client=llm)
        self.assertEqual(result.sources[0].chunk_id, "chunk-abc")
        self.assertEqual(result.sources[0].document_id, "doc-xyz")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../venv/Scripts/python.exe -m unittest tests.test_rag -v`
Expected: FAIL — `TypeError: RetrievedChunk.__init__() got an unexpected keyword argument 'chunk_id'`

- [ ] **Step 3: Write minimal implementation**

Trong `backend/app/llm/rag.py`, sửa dataclass:

```python
@dataclass
class RetrievedChunk:
    text: str
    document_name: str
    position_ref: str
    score: float
    # Định danh để frontend mở được đúng đoạn trong tài liệu (spec mục 4.3,
    # lớp 2). Có mặc định vì RetrievedChunk được dựng ở nhiều nơi — thêm
    # trường bắt buộc sẽ phá mọi lời gọi hiện có.
    chunk_id: str = ""
    document_id: str = ""
```

Trong `backend/app/retrieval/pipeline.py`, cả HAI chỗ `return [...]` đổi thành:

```python
        RetrievedChunk(
            text=chunk.text,
            document_name=chunk.document_name,
            position_ref=chunk.position_ref,
            score=score,
            chunk_id=chunk.chunk_id,
            document_id=chunk.document_id,
        )
```

(nhánh `dense_only` lặp qua `for chunk, score in results`, nhánh hybrid lặp qua
`for chunk, score in reranked` — cùng một dạng sửa.)

Trong `backend/app/routers/quiz.py`, chỗ dựng `RetrievedChunk` từ kết quả
`store.search`:

```python
            RetrievedChunk(
                text=c.text,
                document_name=c.document_name,
                position_ref=c.position_ref,
                score=score,
                chunk_id=c.chunk_id,
                document_id=c.document_id,
            )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `../venv/Scripts/python.exe -m unittest discover -s tests`
Expected: toàn bộ PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/llm/rag.py backend/app/retrieval/pipeline.py backend/app/routers/quiz.py backend/tests/test_rag.py
git commit -m "feat: RetrievedChunk mang chunk_id va document_id"
```

---

### Task 2: Citation theo từng luận điểm

**Files:**
- Modify: `backend/app/llm/rag.py`
- Test: `backend/tests/test_rag.py`

**Interfaces:**
- Produces:
  - `REQUIRE_INLINE_CITATION: bool` (đọc từ biến môi trường `EDUTUTOR_REQUIRE_INLINE_CITATION`, mặc định bật)
  - `_strip_invalid_citations(answer: str, num_chunks: int) -> tuple[str, List[int]]` — trả về (câu trả lời đã gỡ marker sai, danh sách chỉ số 1-based hợp lệ theo thứ tự xuất hiện, không trùng)
  - `answer_question(..., require_inline_citation: Optional[bool] = None)`
  - `_build_context` đổi sang đánh số `[n] Nguồn: ...`

- [ ] **Step 1: Write the failing test**

Thêm class mới vào cuối `backend/tests/test_rag.py`, trước `if __name__`:

```python
class TestInlineCitation(unittest.TestCase):
    def make_chunk(self, text="Nội dung nguồn.", doc="slide1.pdf", pos="Trang 1", score=0.8):
        return RetrievedChunk(text=text, document_name=doc, position_ref=pos, score=score)

    def test_context_numbers_each_chunk(self):
        llm = FakeLLMClient(scripted_responses=["Trả lời. [1]", "CÓ"])
        answer_question(
            question="Hỏi?",
            retrieved_chunks=[self.make_chunk(doc="a.pdf"), self.make_chunk(doc="b.pdf")],
            llm_client=llm,
        )
        generator_prompt, _ = llm.prompts_received
        self.assertIn("[1]", generator_prompt)
        self.assertIn("[2]", generator_prompt)

    def test_valid_marker_is_kept_and_answer_is_grounded(self):
        llm = FakeLLMClient(scripted_responses=["Gradient Descent là thuật toán tối ưu. [1]", "CÓ"])
        result = answer_question(
            question="Hỏi?", retrieved_chunks=[self.make_chunk()], llm_client=llm
        )
        self.assertTrue(result.is_grounded)
        self.assertIn("[1]", result.answer)

    def test_out_of_range_marker_is_stripped(self):
        answer, valid = _strip_invalid_citations("Câu A [1]. Câu B [7].", num_chunks=2)
        self.assertNotIn("[7]", answer)
        self.assertIn("[1]", answer)
        self.assertEqual(valid, [1])

    def test_answer_without_any_valid_marker_is_refused(self):
        llm = FakeLLMClient(scripted_responses=["Một câu trả lời không có nguồn nào.", "CÓ"])
        result = answer_question(
            question="Hỏi?",
            retrieved_chunks=[self.make_chunk()],
            llm_client=llm,
            require_inline_citation=True,
        )
        self.assertFalse(result.is_grounded)
        self.assertEqual(result.answer, NOT_GROUNDED_MESSAGE)

    def test_flag_off_restores_previous_behaviour(self):
        llm = FakeLLMClient(scripted_responses=["Một câu trả lời không có nguồn nào.", "CÓ"])
        result = answer_question(
            question="Hỏi?",
            retrieved_chunks=[self.make_chunk()],
            llm_client=llm,
            require_inline_citation=False,
        )
        self.assertTrue(result.is_grounded)

    def test_sources_contain_only_cited_chunks(self):
        llm = FakeLLMClient(scripted_responses=["Chỉ dùng nguồn hai. [2]", "CÓ"])
        result = answer_question(
            question="Hỏi?",
            retrieved_chunks=[
                self.make_chunk(doc="a.pdf", pos="Trang 1"),
                self.make_chunk(doc="b.pdf", pos="Trang 2"),
            ],
            llm_client=llm,
            require_inline_citation=True,
        )
        self.assertEqual([s.document_name for s in result.sources], ["b.pdf"])
```

Thêm `_strip_invalid_citations` vào khối import ở đầu file.

- [ ] **Step 2: Run test to verify it fails**

Run: `../venv/Scripts/python.exe -m unittest tests.test_rag`
Expected: FAIL — `ImportError: cannot import name '_strip_invalid_citations'`

- [ ] **Step 3: Write minimal implementation**

Trong `backend/app/llm/rag.py`, thêm `import os` ở đầu file (cạnh `import re`), rồi:

```python
# Bật/tắt được để chạy ablation ở giai đoạn đánh giá — quy tắc này siết chặt
# hơn hành vi cũ (câu trả lời không gắn được nguồn nào sẽ bị từ chối), nên cần
# đo cả hai chiều: nó cải thiện Citation Accuracy bao nhiêu và làm tăng từ chối
# nhầm bao nhiêu.
REQUIRE_INLINE_CITATION = os.environ.get("EDUTUTOR_REQUIRE_INLINE_CITATION", "1") != "0"

_CITATION_MARKER_RE = re.compile(r"\[(\d+)\]")


def _strip_invalid_citations(answer: str, num_chunks: int) -> tuple:
    """Gỡ mọi marker [n] trỏ ra ngoài khoảng đoạn trích thật.

    Đây là lớp chặn citation bịa: LLM có thể tự nghĩ ra [5] khi chỉ có 2 đoạn
    trích. Trả về (câu trả lời đã làm sạch, danh sách chỉ số hợp lệ 1-based
    theo thứ tự xuất hiện, không trùng)."""
    valid_order = []

    def _replace(match):
        index = int(match.group(1))
        if 1 <= index <= num_chunks:
            if index not in valid_order:
                valid_order.append(index)
            return match.group(0)
        return ""

    cleaned = _CITATION_MARKER_RE.sub(_replace, answer)
    # gỡ marker xong có thể để lại khoảng trắng thừa trước dấu câu
    cleaned = re.sub(r"\s+([.,;:])", r"\1", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned).strip()
    return cleaned, valid_order
```

Sửa `_build_context` sang đánh số 1-based:

```python
def _build_context(chunks: List[RetrievedChunk]) -> str:
    parts = []
    for i, c in enumerate(chunks, start=1):
        # Đánh số để generator gắn được [n] theo từng luận điểm (spec mục 4.3).
        parts.append(f"[{i}] Nguồn: {c.document_name}, {c.position_ref}\n{c.text}")
    return "\n\n".join(parts)
```

Thêm chỉ dẫn citation vào `_build_generator_prompt`, ngay sau dòng "Trả lời bằng
đúng ngôn ngữ của câu hỏi...":

```python
        "Mỗi câu kết luận PHẢI kết thúc bằng số hiệu đoạn trích đã dùng làm căn "
        "cứ, đặt trong ngoặc vuông, ví dụ: [1]. Chỉ được dùng những số có trong "
        "danh sách đoạn trích bên dưới; TUYỆT ĐỐI không bịa số không tồn tại.\n"
```

Trong `answer_question`, thêm tham số `require_inline_citation: Optional[bool] = None`
vào cuối, rồi thay khối cuối cùng (sau khi verifier đồng ý):

```python
    if not is_grounded:
        return AnswerResult(answer=NOT_GROUNDED_MESSAGE, is_grounded=False, sources=[])

    require_citation = (
        REQUIRE_INLINE_CITATION if require_inline_citation is None else require_inline_citation
    )
    if not require_citation:
        return AnswerResult(answer=draft_answer, is_grounded=True, sources=_dedupe_sources(relevant))

    cleaned_answer, cited_indices = _strip_invalid_citations(draft_answer, len(relevant))
    if not cited_indices:
        # Có nội dung thực chất nhưng không gắn được vào đoạn trích nào — theo
        # điều kiện chặn ở PRD §7, thà từ chối còn hơn đưa ra kết luận không
        # truy được nguồn.
        return AnswerResult(answer=NOT_GROUNDED_MESSAGE, is_grounded=False, sources=[])

    cited_chunks = [relevant[i - 1] for i in cited_indices]
    return AnswerResult(answer=cleaned_answer, is_grounded=True, sources=_dedupe_sources(cited_chunks))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `../venv/Scripts/python.exe -m unittest discover -s tests`
Expected: toàn bộ PASS. Nếu có test cũ vỡ vì câu trả lời giả lập không có
marker, sửa test CŨ bằng cách thêm `[1]` vào `scripted_responses` của nó —
đó là hành vi mới đúng, không phải hồi quy.

- [ ] **Step 5: Commit**

```bash
git add backend/app/llm/rag.py backend/tests/test_rag.py
git commit -m "feat: citation theo tung luan diem, chan marker bia"
```

---

### Task 3: Tô sáng câu chống đỡ trong đoạn trích

**Files:**
- Create: `backend/app/citation.py`
- Test: `backend/tests/test_citation.py`

**Interfaces:**
- Produces: `supporting_sentences(answer: str, chunk_text: str, min_overlap: int = 2) -> List[str]`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_citation.py`:

```python
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.citation import supporting_sentences


class TestSupportingSentences(unittest.TestCase):
    def test_returns_sentence_sharing_content_words(self):
        chunk = "Gradient Descent là thuật toán tối ưu lặp. Cây quyết định chia dữ liệu theo thuộc tính."
        answer = "Gradient Descent là một thuật toán tối ưu."
        result = supporting_sentences(answer, chunk)
        self.assertEqual(len(result), 1)
        self.assertIn("thuật toán tối ưu lặp", result[0])

    def test_returns_empty_when_nothing_overlaps(self):
        chunk = "Cây quyết định chia dữ liệu theo thuộc tính."
        answer = "Mạng nơ-ron tích chập dùng bộ lọc."
        self.assertEqual(supporting_sentences(answer, chunk), [])

    def test_ignores_stopwords_only_overlap(self):
        # chỉ trùng các từ chức năng ("là", "một", "của") thì KHÔNG tính là chống đỡ
        chunk = "Đây là một ví dụ của việc dùng từ nối."
        answer = "Đó là một phần của câu."
        self.assertEqual(supporting_sentences(answer, chunk), [])

    def test_empty_inputs_are_safe(self):
        self.assertEqual(supporting_sentences("", "abc"), [])
        self.assertEqual(supporting_sentences("abc", ""), [])

    def test_multiple_supporting_sentences_are_all_returned(self):
        chunk = "Convolution dùng bộ lọc trượt. Pooling giảm kích thước bản đồ đặc trưng."
        answer = "Convolution dùng bộ lọc trượt và pooling giảm kích thước bản đồ đặc trưng."
        self.assertEqual(len(supporting_sentences(answer, chunk)), 2)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../venv/Scripts/python.exe -m unittest tests.test_citation`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.citation'`

- [ ] **Step 3: Write minimal implementation**

Create `backend/app/citation.py`:

```python
"""Tìm những câu trong đoạn trích thực sự chống đỡ câu trả lời, để giao diện tô
sáng đúng chỗ khi người dùng bấm vào một marker citation.

Tính bằng trùng lặp từ vựng, KHÔNG gọi LLM — đây là một tính năng hiển thị,
không đáng tốn một lượt gọi mô hình cho mỗi lần người dùng mở panel (spec mục
4.3, lớp 2).

Hạn chế đã biết: cách này bỏ sót trường hợp câu trả lời diễn đạt lại hoàn toàn
bằng từ đồng nghĩa. Chấp nhận được vì hậu quả chỉ là không tô sáng được câu
nào — người dùng vẫn đọc được nguyên văn đoạn trích.
"""

import re
from typing import List

# Từ chức năng tiếng Việt và tiếng Anh — trùng nhau ở những từ này không nói
# lên điều gì về nội dung.
_STOPWORDS = {
    "là", "và", "của", "có", "được", "một", "các", "những", "cho", "trong",
    "với", "để", "khi", "này", "đó", "không", "thì", "mà", "ở", "về", "như",
    "đây", "việc", "phần", "câu", "the", "a", "an", "is", "are", "of", "and",
    "to", "in", "for", "on", "that", "this", "it", "with", "as", "be",
}

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_WORD_RE = re.compile(r"\w+", re.UNICODE)


def _content_words(text: str) -> set:
    return {w for w in (m.group(0).lower() for m in _WORD_RE.finditer(text)) if w not in _STOPWORDS}


def supporting_sentences(answer: str, chunk_text: str, min_overlap: int = 2) -> List[str]:
    """Trả về các câu trong `chunk_text` chia sẻ ít nhất `min_overlap` từ nội
    dung với `answer`."""
    if not answer.strip() or not chunk_text.strip():
        return []

    answer_words = _content_words(answer)
    if not answer_words:
        return []

    supporting = []
    for sentence in _SENTENCE_SPLIT_RE.split(chunk_text.strip()):
        if not sentence.strip():
            continue
        if len(_content_words(sentence) & answer_words) >= min_overlap:
            supporting.append(sentence.strip())
    return supporting
```

- [ ] **Step 4: Run test to verify it passes**

Run: `../venv/Scripts/python.exe -m unittest tests.test_citation -v`
Expected: PASS, 5 test

- [ ] **Step 5: Commit**

```bash
git add backend/app/citation.py backend/tests/test_citation.py
git commit -m "feat: tim cau chong do trong doan trich bang trung lap tu vung"
```

---

### Task 4: Bóc từ khoá và chế độ truy hồi mở rộng

**Files:**
- Create: `backend/app/retrieval/keywords.py`
- Modify: `backend/app/retrieval/pipeline.py`
- Test: `backend/tests/test_keywords.py`

**Interfaces:**
- Produces:
  - `extract_keywords(query: str) -> str` — bỏ từ chức năng, giữ thuật ngữ
  - `retrieve_chunks(..., mode: str = "strict")` — `"wide"` nhân ba `top_k`, dùng từ khoá làm truy vấn BM25

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_keywords.py`:

```python
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.retrieval.keywords import extract_keywords


class TestExtractKeywords(unittest.TestCase):
    def test_drops_function_words(self):
        result = extract_keywords("Cho tôi biết về vanishing gradient là gì trong mạng nơ-ron")
        self.assertIn("vanishing", result)
        self.assertIn("gradient", result)
        self.assertNotIn(" là ", f" {result} ")

    def test_keeps_technical_terms_verbatim(self):
        result = extract_keywords("BM25 và RRF khác nhau thế nào?")
        self.assertIn("BM25", result)
        self.assertIn("RRF", result)

    def test_empty_query_returns_empty(self):
        self.assertEqual(extract_keywords(""), "")

    def test_query_of_only_stopwords_falls_back_to_original(self):
        # nếu bỏ hết thì còn chuỗi rỗng, truy hồi sẽ vô nghĩa — phải giữ nguyên
        original = "là gì của các"
        self.assertEqual(extract_keywords(original), original)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../venv/Scripts/python.exe -m unittest tests.test_keywords`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.retrieval.keywords'`

- [ ] **Step 3: Write minimal implementation**

Create `backend/app/retrieval/keywords.py`:

```python
"""Bóc từ khoá nội dung khỏi câu hỏi, phục vụ lượt truy hồi MỞ RỘNG.

Lượt truy hồi thứ hai ngả về BM25 theo từ khoá thay vì ngữ nghĩa, vì điểm mù
cố hữu của truy hồi ngữ nghĩa là thuật ngữ chính xác xuất hiện đúng một lần ở
sâu trong tài liệu — dạng "thông tin bị chôn" mà lượt một hay bỏ sót.

Module thuần, không import gì nặng, để test được độc lập.
"""

import re
from typing import List

_STOPWORDS = {
    "là", "gì", "và", "của", "có", "được", "một", "các", "những", "cho",
    "trong", "với", "để", "khi", "này", "đó", "không", "thì", "mà", "ở",
    "về", "như", "thế", "nào", "sao", "tôi", "bạn", "hãy", "biết", "cho",
    "what", "is", "are", "the", "a", "an", "of", "and", "to", "in", "for",
    "how", "does", "do", "me", "tell", "about", "explain",
}

_WORD_RE = re.compile(r"[\w\-]+", re.UNICODE)


def extract_keywords(query: str) -> str:
    """Giữ nguyên chữ hoa/thường của từ gốc — thuật ngữ như BM25, RRF, CNN mất
    ý nghĩa nếu bị hạ về chữ thường trước khi đưa cho BM25."""
    if not query.strip():
        return ""

    kept: List[str] = [
        m.group(0) for m in _WORD_RE.finditer(query) if m.group(0).lower() not in _STOPWORDS
    ]
    if not kept:
        # Bỏ hết thì truy vấn thành rỗng và lượt mở rộng sẽ vô dụng — thà dùng
        # lại nguyên câu hỏi.
        return query
    return " ".join(kept)
```

Trong `backend/app/retrieval/pipeline.py`, thêm import và tham số `mode`:

```python
from app.retrieval.keywords import extract_keywords

# Lượt truy hồi MỞ RỘNG (spec mục 4.1) — chỉ chạy khi lượt gắt đã trượt.
WIDE_TOP_K_MULTIPLIER = 3
```

Sửa chữ ký:

```python
def retrieve_chunks(
    user_id: str,
    query: str,
    top_k: int = 5,
    document_ids: Optional[Set[str]] = None,
    reranker: Optional[RerankerClient] = None,
    mode: str = "strict",
) -> List[RetrievedChunk]:
```

Ngay sau `store = UserVectorStore(user_id=user_id)`, thêm:

```python
    # Chế độ mở rộng: lấy nhiều ứng viên hơn và tra BM25 bằng từ khoá đã bóc,
    # để bắt trường hợp thuật ngữ nằm sâu mà truy hồi ngữ nghĩa bỏ sót.
    if mode == "wide":
        top_k = top_k * WIDE_TOP_K_MULTIPLIER
        lexical_query = extract_keywords(query)
    else:
        lexical_query = query
```

Đổi `query_embedding = embed_query(query)` giữ nguyên (vector vẫn dùng câu hỏi
gốc — bóc từ khoá chỉ phục vụ nhánh BM25), và đổi lời gọi `hybrid_search`:

```python
    candidates = store.hybrid_search(
        query=lexical_query,
        query_embedding=query_embedding,
        candidate_pool=max(DEFAULT_CANDIDATE_POOL, top_k * 3),
        document_ids=document_ids,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `../venv/Scripts/python.exe -m unittest discover -s tests`
Expected: toàn bộ PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/retrieval/keywords.py backend/app/retrieval/pipeline.py backend/tests/test_keywords.py
git commit -m "feat: boc tu khoa va che do truy hoi mo rong"
```

---

### Task 5: Điều phối hai lượt và dựng bằng chứng phủ định

**Files:**
- Create: `backend/app/qa_pipeline.py`
- Test: `backend/tests/test_qa_pipeline.py`

**Interfaces:**
- Consumes: `app.llm.rag.AnswerResult`, `RetrievedChunk`, `answer_question`, `NO_CONTEXT_MESSAGE`, `NOT_GROUNDED_MESSAGE`
- Produces:
  - `@dataclass NearMiss(chunk_id, document_id, document_name, position_ref, text, score)`
  - `@dataclass SearchReport(passes_run: int, searched_documents: List[dict], near_misses: List[NearMiss])`
  - `@dataclass QAResult(answer, is_grounded, sources, abstained, search_report)`
  - `answer_with_fallback(question, llm_client, retrieve_fn, searched_documents, top_k=5, min_score=0.02, max_near_misses=3, **answer_kwargs) -> QAResult`

`retrieve_fn(query: str, top_k: int, mode: str) -> List[RetrievedChunk]` được
inject nên module này test được không cần faiss.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_qa_pipeline.py`:

```python
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.llm.rag import NOT_GROUNDED_MESSAGE, RetrievedChunk
from app.qa_pipeline import answer_with_fallback


class FakeLLMClient:
    def __init__(self, scripted_responses):
        self.scripted_responses = list(scripted_responses)
        self.prompts_received = []

    def complete(self, prompt):
        self.prompts_received.append(prompt)
        return self.scripted_responses.pop(0)


def _chunk(text="Nội dung.", doc="a.pdf", pos="Trang 1", score=0.8, cid="c1", did="d1"):
    return RetrievedChunk(
        text=text, document_name=doc, position_ref=pos, score=score, chunk_id=cid, document_id=did
    )


DOCS = [{"id": "d1", "file_name": "a.pdf"}]


class TestAnswerWithFallback(unittest.TestCase):
    def test_first_pass_success_does_not_trigger_second_pass(self):
        calls = []

        def retrieve(query, top_k, mode):
            calls.append(mode)
            return [_chunk()]

        llm = FakeLLMClient(["Trả lời tốt. [1]", "CÓ"])
        result = answer_with_fallback(
            question="Hỏi?", llm_client=llm, retrieve_fn=retrieve, searched_documents=DOCS
        )
        self.assertTrue(result.is_grounded)
        self.assertFalse(result.abstained)
        self.assertEqual(calls, ["strict"])

    def test_second_pass_runs_when_first_pass_not_grounded(self):
        calls = []

        def retrieve(query, top_k, mode):
            calls.append(mode)
            return [_chunk()]

        # lượt 1: verifier bác; lượt 2: verifier chấp nhận
        llm = FakeLLMClient(["Nháp sai. [1]", "KHÔNG", "Nháp đúng. [1]", "CÓ"])
        result = answer_with_fallback(
            question="Hỏi?", llm_client=llm, retrieve_fn=retrieve, searched_documents=DOCS
        )
        self.assertTrue(result.is_grounded)
        self.assertEqual(calls, ["strict", "wide"])
        self.assertEqual(result.search_report.passes_run, 2)

    def test_abstains_with_negative_evidence_when_both_passes_fail(self):
        def retrieve(query, top_k, mode):
            return [_chunk(text="Nội dung không liên quan.", score=0.11)]

        llm = FakeLLMClient(["Nháp 1. [1]", "KHÔNG", "Nháp 2. [1]", "KHÔNG"])
        result = answer_with_fallback(
            question="Hỏi?", llm_client=llm, retrieve_fn=retrieve, searched_documents=DOCS
        )
        self.assertTrue(result.abstained)
        self.assertFalse(result.is_grounded)
        self.assertEqual(result.search_report.passes_run, 2)
        self.assertEqual(result.search_report.searched_documents, DOCS)
        self.assertEqual(len(result.search_report.near_misses), 1)
        self.assertEqual(result.search_report.near_misses[0].position_ref, "Trang 1")

    def test_near_misses_are_capped_and_sorted_by_score(self):
        def retrieve(query, top_k, mode):
            return [
                _chunk(pos="Trang 1", score=0.05),
                _chunk(pos="Trang 2", score=0.30),
                _chunk(pos="Trang 3", score=0.20),
                _chunk(pos="Trang 4", score=0.01),
            ]

        llm = FakeLLMClient(["Nháp 1. [1]", "KHÔNG", "Nháp 2. [1]", "KHÔNG"])
        result = answer_with_fallback(
            question="Hỏi?",
            llm_client=llm,
            retrieve_fn=retrieve,
            searched_documents=DOCS,
            max_near_misses=2,
        )
        refs = [n.position_ref for n in result.search_report.near_misses]
        self.assertEqual(refs, ["Trang 2", "Trang 3"])

    def test_abstention_message_mentions_two_passes(self):
        def retrieve(query, top_k, mode):
            return []

        llm = FakeLLMClient([])
        result = answer_with_fallback(
            question="Hỏi?", llm_client=llm, retrieve_fn=retrieve, searched_documents=DOCS
        )
        self.assertTrue(result.abstained)
        self.assertIn("2 lượt", result.answer)

    def test_no_chunks_at_all_skips_llm_entirely(self):
        def retrieve(query, top_k, mode):
            return []

        llm = FakeLLMClient([])
        answer_with_fallback(
            question="Hỏi?", llm_client=llm, retrieve_fn=retrieve, searched_documents=DOCS
        )
        self.assertEqual(llm.prompts_received, [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../venv/Scripts/python.exe -m unittest tests.test_qa_pipeline`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.qa_pipeline'`

- [ ] **Step 3: Write minimal implementation**

Create `backend/app/qa_pipeline.py`:

```python
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


def _to_near_misses(chunks: List[RetrievedChunk], limit: int) -> List[NearMiss]:
    ranked = sorted(chunks, key=lambda c: c.score, reverse=True)[:limit]
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
    **answer_kwargs,
) -> QAResult:
    """Chạy lượt truy hồi gắt trước; chỉ khi nó trượt mới chạy lượt mở rộng.

    "Trượt" nghĩa là không truy hồi được đoạn nào HOẶC verifier bác câu trả lời
    nháp — cả hai đều là dấu hiệu lượt đầu chưa tìm đúng chỗ."""
    passes_run = 0
    seen_chunks: List[RetrievedChunk] = []

    for mode in ("strict", "wide"):
        chunks = retrieve_fn(question, top_k, mode)
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

    return QAResult(
        answer=_abstention_message(passes_run, len(searched_documents)),
        is_grounded=False,
        sources=[],
        abstained=True,
        search_report=SearchReport(
            passes_run=passes_run,
            searched_documents=searched_documents,
            near_misses=_to_near_misses(seen_chunks, max_near_misses),
        ),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `../venv/Scripts/python.exe -m unittest tests.test_qa_pipeline -v`
Expected: PASS, 6 test

- [ ] **Step 5: Commit**

```bash
git add backend/app/qa_pipeline.py backend/tests/test_qa_pipeline.py
git commit -m "feat: dieu phoi hoi dap hai luot va bang chung phu dinh"
```

---

### Task 6: Nối hai lượt vào router và mở rộng response

**Files:**
- Modify: `backend/app/routers/chat.py`

**Interfaces:**
- Response của `POST /chat/ask` thêm: `abstained: bool`, `search_report: dict | None`; mỗi phần tử `sources` thêm `chunk_id`, `document_id`, `text`, `supporting_sentences`.

- [ ] **Step 1: Thay lời gọi answer_question bằng answer_with_fallback**

Trong `backend/app/routers/chat.py`, thêm import:

```python
from app.citation import supporting_sentences
from app.qa_pipeline import answer_with_fallback
```

Thay khối `retrieved_chunks = ...` + `result = answer_question(...)` trong nhánh
`else` bằng:

```python
            effective_top_k = req.top_k + LEVEL_TOP_K_BOOST if learner.effective_level else req.top_k

            def _retrieve(query: str, top_k: int, mode: str):
                return retrieve_chunks(
                    user_id=req.user_id,
                    query=query,
                    top_k=top_k,
                    document_ids=document_ids,
                    mode=mode,
                )

            qa_result = answer_with_fallback(
                question=req.question,
                llm_client=llm_client,
                retrieve_fn=_retrieve,
                searched_documents=[{"id": d.id, "file_name": d.file_name} for d in ready_docs],
                top_k=effective_top_k,
                min_score=req.min_score,
                conversation_history=history,
                level=learner.effective_level,
                learning_goal=learner.learning_goal,
                recalled_events=learner.recalled_events,
            )
            result = AnswerResult(
                answer=qa_result.answer,
                is_grounded=qa_result.is_grounded,
                sources=qa_result.sources,
            )
```

Khởi tạo `qa_result = None` ngay cạnh `guardrail_result = None` ở đầu `ask()`,
để nhánh recommendation và nhánh bị guardrail chặn vẫn trả về response đúng
hình dạng.

- [ ] **Step 2: Mở rộng response trả về**

Thay khối `return {...}` cuối hàm `ask()` bằng:

```python
    return {
        "conversation_id": conversation_id,
        "answer": result.answer,
        "is_grounded": result.is_grounded,
        "abstained": qa_result.abstained if qa_result else False,
        "sources": [
            {
                "document_name": s.document_name,
                "position_ref": s.position_ref,
                "chunk_id": s.chunk_id,
                "document_id": s.document_id,
                "text": s.text,
                # Câu nào trong đoạn trích thực sự chống đỡ câu trả lời — dùng
                # để tô sáng trong panel, tính bằng trùng lặp từ vựng, không
                # tốn lượt gọi LLM (app/citation.py).
                "supporting_sentences": supporting_sentences(result.answer, s.text),
            }
            for s in result.sources
        ],
        "search_report": (
            {
                "passes_run": qa_result.search_report.passes_run,
                "searched_documents": qa_result.search_report.searched_documents,
                "near_misses": [
                    {
                        "chunk_id": n.chunk_id,
                        "document_id": n.document_id,
                        "document_name": n.document_name,
                        "position_ref": n.position_ref,
                        "text": n.text,
                        "score": n.score,
                    }
                    for n in qa_result.search_report.near_misses
                ],
            }
            if qa_result and qa_result.search_report
            else None
        ),
    }
```

- [ ] **Step 3: Chạy toàn bộ test và kiểm tra import**

Run: `../venv/Scripts/python.exe -m unittest discover -s tests`
Expected: toàn bộ PASS

Run: `../venv/Scripts/python.exe -c "from app.main import app; print('ok')"`
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add backend/app/routers/chat.py
git commit -m "feat: noi truy hoi hai luot va bang chung phu dinh vao API hoi dap"
```

---

### Task 7: Phục vụ file tài liệu gốc

**Files:**
- Modify: `backend/app/routers/documents.py`

**Interfaces:**
- Produces: `GET /documents/{document_id}/file?user_id=...` → trả file gốc với `media_type` đúng, kèm header `Content-Disposition: inline` để trình duyệt mở tại chỗ thay vì tải xuống.

- [ ] **Step 1: Thêm endpoint**

Trong `backend/app/routers/documents.py`, thêm import:

```python
from fastapi.responses import FileResponse
```

Thêm endpoint TRƯỚC `delete_document` (route tĩnh phải đứng trước route có tham
số đường dẫn cùng tiền tố để không bị nuốt nhầm):

```python
MEDIA_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


@router.get("/{document_id}/file")
def get_document_file(document_id: str, user_id: str, db: Session = Depends(get_db)):
    """Trả file gốc để người dùng mở đúng trang từ một citation (spec mục 4.3,
    lớp 3). Với PDF, frontend gắn thêm '#page=N' bóc từ position_ref.

    Kiểm tra quyền sở hữu bằng user_id trước khi trả file — nếu không, bất kỳ
    ai biết document_id đều tải được tài liệu của người khác."""
    doc = db.query(Document).filter(Document.id == document_id, Document.user_id == user_id).first()
    if not doc:
        raise HTTPException(404, "Không tìm thấy tài liệu.")

    matches = glob.glob(os.path.join(UPLOAD_DIR, f"{document_id}.*"))
    if not matches:
        raise HTTPException(404, "File gốc của tài liệu này không còn trên đĩa.")

    path = matches[0]
    ext = os.path.splitext(path)[1].lower()
    return FileResponse(
        path,
        media_type=MEDIA_TYPES.get(ext, "application/octet-stream"),
        filename=doc.file_name,
        content_disposition_type="inline",
    )
```

- [ ] **Step 2: Kiểm tra route đăng ký đúng**

Run: `../venv/Scripts/python.exe -c "from app.main import app; print([r.path for r in app.routes if 'documents' in r.path])"`
Expected: danh sách có `/documents/{document_id}/file`

- [ ] **Step 3: Chạy toàn bộ test**

Run: `../venv/Scripts/python.exe -m unittest discover -s tests`
Expected: toàn bộ PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/routers/documents.py
git commit -m "feat: phuc vu file tai lieu goc de mo dung trang tu citation"
```

---

## Kiểm chứng cuối giai đoạn C

- [ ] Chạy lại toàn bộ test: `../venv/Scripts/python.exe -m unittest discover -s tests` — tất cả PASS
- [ ] Viết một script kiểm chứng trong scratchpad dựng `answer_with_fallback` với `retrieve_fn` giả lập tài liệu có thuật ngữ "bị chôn": lượt `strict` trả về đoạn không liên quan, lượt `wide` trả về đúng đoạn — xác nhận hệ thống tìm ra ở lượt hai thay vì từ chối
- [ ] Xác nhận `GET /documents/{id}/file` với `user_id` SAI trả về 404, không trả file
