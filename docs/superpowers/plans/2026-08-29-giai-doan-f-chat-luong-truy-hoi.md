# Giai đoạn F — Chất lượng truy hồi: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Nâng trần chất lượng truy hồi — thứ đang giới hạn mọi tầng phía trên —
bằng cách sửa hai lỗ hổng đã xác định và bổ sung chỉ số chẩn đoán để lần sau
biết lỗi nằm ở truy hồi hay ở sinh nội dung.

**Architecture:** Hai thay đổi lõi đều là module thuần, không gọi LLM. Việc
viết lại truy vấn chỉ **bổ sung từ khoá ngữ cảnh** vào truy vấn truy hồi chứ
không sinh lại câu hỏi bằng mô hình — truy hồi cần từ nội dung chứ không cần
câu văn trôi chảy, nên không đáng tốn một lượt gọi cho mỗi lượt hỏi. Câu hỏi
GỐC vẫn là thứ đưa cho generator, để câu trả lời bám đúng điều người dùng hỏi.

**Tech Stack:** Python 3.12, unittest (không dùng pytest).

**Spec:** phần "Cải thiện, xếp theo đòn bẩy" đã thống nhất trong hội thoại —
mục 1 (viết lại truy vấn), mục 3 (chia chunk), cộng chỉ số recall@k.

## Global Constraints

- Test chạy bằng `../venv/Scripts/python.exe -m unittest discover -s tests` từ `backend/`.
- Mọi file test bắt đầu bằng `sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))`.
- Comment và docstring tiếng Việt.
- Không được gọi LLM ở bất kỳ task nào trong giai đoạn này.
- Việc bổ sung ngữ cảnh CHỈ tác động tới truy vấn truy hồi. Câu hỏi gốc phải được giữ nguyên khi đưa vào prompt generator và verifier.
- `position_ref` phải luôn phản ánh trung thực vị trí thật của văn bản. Chunk bắc cầu qua hai section phải ghi rõ cả hai vị trí, không được gán bừa vào một bên.

---

### Task 1: Bổ sung ngữ cảnh hội thoại vào truy vấn truy hồi

**Files:**
- Create: `backend/app/retrieval/query_context.py`
- Test: `backend/tests/test_query_context.py`

**Interfaces:**
- Consumes: `app.retrieval.keywords.extract_keywords`
- Produces:
  - `ANAPHORA_RE: re.Pattern`
  - `MIN_SELF_CONTAINED_WORDS: int = 5`
  - `MAX_CONTEXT_TERMS: int = 8`
  - `needs_context(question: str) -> bool`
  - `build_retrieval_query(question: str, history: Optional[List], max_context_terms: int = MAX_CONTEXT_TERMS) -> str`

`history` là danh sách object có thuộc tính `.question` và `.answer` — đúng
hình dạng `app.llm.rag.ConversationTurn`, nhưng module này KHÔNG import lớp đó
để giữ độc lập và test được bằng object giả.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_query_context.py`:

```python
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.retrieval.query_context import build_retrieval_query, needs_context


class Turn:
    """Giả lập app.llm.rag.ConversationTurn mà không import nó."""

    def __init__(self, question, answer):
        self.question = question
        self.answer = answer


HISTORY = [Turn("Mạng CNN dùng convolution để làm gì?", "CNN dùng bộ lọc trượt để trích đặc trưng.")]


class TestNeedsContext(unittest.TestCase):
    def test_question_with_pronoun_needs_context(self):
        self.assertTrue(needs_context("tại sao nó lại tốt hơn?"))

    def test_very_short_question_needs_context(self):
        self.assertTrue(needs_context("còn cái kia?"))

    def test_self_contained_question_does_not(self):
        self.assertFalse(needs_context("Gradient Descent hoạt động như thế nào trong mạng nơ-ron?"))

    def test_english_pronoun_is_detected(self):
        self.assertTrue(needs_context("why is it better than that?"))


class TestBuildRetrievalQuery(unittest.TestCase):
    def test_without_history_returns_question_unchanged(self):
        q = "tại sao nó lại tốt hơn?"
        self.assertEqual(build_retrieval_query(q, None), q)
        self.assertEqual(build_retrieval_query(q, []), q)

    def test_self_contained_question_is_left_alone(self):
        q = "Gradient Descent hoạt động như thế nào trong mạng nơ-ron?"
        self.assertEqual(build_retrieval_query(q, HISTORY), q)

    def test_follow_up_gains_terms_from_previous_turn(self):
        result = build_retrieval_query("tại sao nó lại tốt hơn?", HISTORY)
        self.assertIn("tại sao nó lại tốt hơn?", result)
        self.assertIn("CNN", result)

    def test_does_not_duplicate_terms_already_in_question(self):
        result = build_retrieval_query("CNN có nhược điểm gì?", [Turn("CNN là gì?", "CNN là mạng tích chập.")])
        # câu này tự chứa nội dung nên không được đụng vào
        self.assertEqual(result, "CNN có nhược điểm gì?")

    def test_context_terms_are_capped(self):
        long_turn = [Turn(" ".join(f"thuatngu{i}" for i in range(50)), "trả lời dài")]
        result = build_retrieval_query("nó là gì?", long_turn, max_context_terms=3)
        added = [t for t in result.split() if t.startswith("thuatngu")]
        self.assertEqual(len(added), 3)

    def test_uses_most_recent_turn_first(self):
        history = [
            Turn("Decision Tree là gì?", "Cây quyết định chia dữ liệu."),
            Turn("Còn Random Forest?", "Random Forest là tập hợp nhiều cây."),
        ]
        result = build_retrieval_query("nó khác gì?", history, max_context_terms=4)
        self.assertIn("Random", result)

    def test_empty_question_is_safe(self):
        self.assertEqual(build_retrieval_query("", HISTORY), "")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../venv/Scripts/python.exe -m unittest tests.test_query_context`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.retrieval.query_context'`

- [ ] **Step 3: Write minimal implementation**

Create `backend/app/retrieval/query_context.py`:

```python
"""Bổ sung ngữ cảnh hội thoại vào truy vấn TRUY HỒI.

Vấn đề đang sửa: lịch sử hội thoại được đưa vào prompt của generator
(app/llm/rag.py) nhưng truy hồi lại dùng nguyên văn câu hỏi thô. Khi người
dùng hỏi tiếp "tại sao nó lại tốt hơn?", cả dense retrieval lẫn BM25 đều đi
tìm bằng một chuỗi gần như không có từ nội dung nào, nên lấy về đoạn không
liên quan. Generator có lịch sử nhưng không có đoạn trích đúng — hoặc từ chối
oan, hoặc bịa.

Cố ý KHÔNG gọi LLM để viết lại câu hỏi cho trôi chảy: truy hồi cần TỪ NỘI
DUNG chứ không cần câu văn đúng ngữ pháp, nên chỉ cần ghép thêm từ khoá của
lượt trước là đủ. Đây cũng đúng nguyên tắc chi phí ở PRD §6.

Module thuần, không import gì nặng.
"""

import re
from typing import List, Optional

from app.retrieval.keywords import extract_keywords

# Đại từ và từ chỉ định — dấu hiệu câu hỏi đang trỏ ngược về lượt trước.
ANAPHORA_RE = re.compile(
    r"(^|\s)("
    r"nó|chúng|họ|vậy|thế|đấy|"
    r"cái\s+(đó|này|kia|ấy)|điều\s+(đó|này)|phần\s+(đó|này)|"
    r"nó|it|its|they|them|their|this|that|these|those"
    r")(\s|$|\?|,|\.)",
    re.IGNORECASE,
)

# Câu quá ngắn gần như luôn phụ thuộc ngữ cảnh ("còn cái kia?", "vì sao?").
MIN_SELF_CONTAINED_WORDS = 5

MAX_CONTEXT_TERMS = 8


def needs_context(question: str) -> bool:
    """Câu hỏi có vẻ trỏ ngược về lượt trước hay không.

    Cố ý nới rộng một chút: bổ sung thêm vài từ khoá vào truy vấn truy hồi khi
    không cần thiết chỉ làm nhiễu nhẹ, còn bỏ sót một câu hỏi tiếp nối thì mất
    hẳn đoạn trích đúng."""
    stripped = question.strip()
    if not stripped:
        return False
    if len(stripped.split()) < MIN_SELF_CONTAINED_WORDS:
        return True
    return bool(ANAPHORA_RE.search(stripped))


def build_retrieval_query(
    question: str,
    history: Optional[List] = None,
    max_context_terms: int = MAX_CONTEXT_TERMS,
) -> str:
    """Truy vấn dùng cho bước TRUY HỒI. Câu hỏi gốc KHÔNG bị thay đổi và vẫn là
    thứ được đưa vào prompt generator — hàm này chỉ tạo thêm một chuỗi giàu từ
    nội dung hơn để tìm kiếm."""
    stripped = question.strip()
    if not stripped or not history or not needs_context(stripped):
        return question

    already_present = {w.lower() for w in re.findall(r"[\w\-]+", stripped)}

    context_terms: List[str] = []
    # Duyệt từ lượt GẦN NHẤT trở về trước — ngữ cảnh của câu hỏi tiếp nối gần
    # như luôn nằm ở lượt liền trước.
    for turn in reversed(history):
        for source in (getattr(turn, "question", ""), getattr(turn, "answer", "")):
            for term in extract_keywords(source or "").split():
                key = term.lower()
                if key in already_present:
                    continue
                already_present.add(key)
                context_terms.append(term)
                if len(context_terms) >= max_context_terms:
                    return f"{question} {' '.join(context_terms)}"

    if not context_terms:
        return question
    return f"{question} {' '.join(context_terms)}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `../venv/Scripts/python.exe -m unittest tests.test_query_context -v`
Expected: PASS, 11 test

- [ ] **Step 5: Commit**

```bash
git add backend/app/retrieval/query_context.py backend/tests/test_query_context.py
git commit -m "feat: bo sung ngu canh hoi thoai vao truy van truy hoi"
```

---

### Task 2: Nối vào pipeline hỏi đáp

**Files:**
- Modify: `backend/app/qa_pipeline.py`
- Modify: `backend/app/routers/chat.py`
- Test: `backend/tests/test_qa_pipeline.py`

**Interfaces:**
- Produces: `answer_with_fallback(..., retrieval_query: Optional[str] = None)` — truy vấn dùng để truy hồi; bỏ trống thì dùng chính `question`.

- [ ] **Step 1: Write the failing test**

Thêm vào `backend/tests/test_qa_pipeline.py`, trong `class TestAnswerWithFallback`:

```python
    def test_retrieval_uses_augmented_query_but_generator_sees_original(self):
        seen_queries = []

        def retrieve(query, top_k, mode):
            seen_queries.append(query)
            return [_chunk()]

        llm = FakeLLMClient(["Trả lời. [1]", "CÓ"])
        answer_with_fallback(
            question="tại sao nó tốt hơn?",
            llm_client=llm,
            retrieve_fn=retrieve,
            searched_documents=DOCS,
            retrieval_query="tại sao nó tốt hơn? CNN convolution",
        )
        # truy hồi dùng truy vấn đã bổ sung ngữ cảnh
        self.assertEqual(seen_queries, ["tại sao nó tốt hơn? CNN convolution"])
        # nhưng generator vẫn thấy đúng câu hỏi gốc
        generator_prompt = llm.prompts_received[0]
        self.assertIn("tại sao nó tốt hơn?", generator_prompt)
        self.assertNotIn("CNN convolution", generator_prompt)

    def test_retrieval_query_defaults_to_question(self):
        seen_queries = []

        def retrieve(query, top_k, mode):
            seen_queries.append(query)
            return [_chunk()]

        llm = FakeLLMClient(["Trả lời. [1]", "CÓ"])
        answer_with_fallback(
            question="Hỏi gì đó?", llm_client=llm, retrieve_fn=retrieve, searched_documents=DOCS
        )
        self.assertEqual(seen_queries, ["Hỏi gì đó?"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../venv/Scripts/python.exe -m unittest tests.test_qa_pipeline`
Expected: FAIL — `answer_with_fallback() got an unexpected keyword argument 'retrieval_query'`

- [ ] **Step 3: Write minimal implementation**

Trong `backend/app/qa_pipeline.py`, thêm tham số vào chữ ký (đặt sau
`max_near_misses`, trước `**answer_kwargs`):

```python
    retrieval_query: Optional[str] = None,
```

Và trong thân hàm, ngay trước vòng `for mode in ("strict", "wide"):`:

```python
    # Truy hồi dùng truy vấn đã bổ sung ngữ cảnh hội thoại
    # (app/retrieval/query_context.py); generator vẫn nhận câu hỏi GỐC để câu
    # trả lời bám đúng điều người dùng vừa hỏi.
    search_query = retrieval_query or question
```

Đổi lời gọi truy hồi thành `chunks = retrieve_fn(search_query, top_k, mode)`.
Lời gọi `answer_question(question=question, ...)` giữ NGUYÊN.

- [ ] **Step 4: Nối vào router**

Trong `backend/app/routers/chat.py`, thêm import:

```python
from app.retrieval.query_context import build_retrieval_query
```

Trong nhánh `else` của `ask()`, ngay sau khi có `learner`, thêm:

```python
            # Câu hỏi tiếp nối ("tại sao nó tốt hơn?") không có đủ từ nội dung
            # để truy hồi; bổ sung từ khoá của các lượt trước vào truy vấn.
            retrieval_query = build_retrieval_query(req.question, history)
```

và truyền `retrieval_query=retrieval_query` vào `answer_with_fallback(...)`.

- [ ] **Step 5: Run test to verify it passes**

Run: `../venv/Scripts/python.exe -m unittest discover -s tests`
Expected: toàn bộ PASS

Run: `../venv/Scripts/python.exe -c "from app.main import app; print('ok')"`
Expected: `ok`

- [ ] **Step 6: Commit**

```bash
git add backend/app/qa_pipeline.py backend/app/routers/chat.py backend/tests/test_qa_pipeline.py
git commit -m "feat: truy hoi dung truy van co ngu canh, generator giu cau hoi goc"
```

---

### Task 3: Chia chunk theo ranh giới câu và bắc cầu qua ranh giới section

**Files:**
- Modify: `backend/app/ingestion/chunker.py`
- Test: `backend/tests/test_chunker.py`

**Interfaces:**
- Produces: `chunk_sections(sections, max_chars=800, overlap_chars=100, bridge_sections=True)`

Hai khiếm khuyết đang sửa. Thứ nhất, hiện tại cắt thẳng theo ký tự
(`stripped[start:start + max_chars]`) nên cắt giữa câu, thậm chí giữa từ —
embedding của một mẩu cụt kém hẳn và panel citation hiện ra đoạn dở dang. Thứ
hai, chồng lấn chỉ áp dụng TRONG một section; với PDF mỗi trang là một section
nên một khái niệm vắt từ cuối trang 3 sang đầu trang 4 bị cắt đôi mà không có
chunk nào bắc cầu.

- [ ] **Step 1: Write the failing test**

Thêm hai class vào `backend/tests/test_chunker.py`, trước `if __name__`:

```python
class TestSentenceBoundaries(unittest.TestCase):
    def test_chunks_do_not_cut_mid_sentence(self):
        text = " ".join(f"Đây là câu số {i} trong đoạn văn thử nghiệm." for i in range(30))
        chunks = chunk_sections([("Trang 1", text)], max_chars=200, overlap_chars=50)
        self.assertGreater(len(chunks), 1)
        for c in chunks:
            # mỗi chunk phải kết thúc bằng dấu câu, không cụt giữa chừng
            self.assertTrue(c.text.rstrip().endswith("."), f"chunk cụt: {c.text!r}")

    def test_single_sentence_longer_than_max_is_hard_split(self):
        text = "A" * 250
        chunks = chunk_sections([("Trang 1", text)], max_chars=100, overlap_chars=20)
        self.assertGreater(len(chunks), 1)
        for c in chunks:
            self.assertLessEqual(len(c.text), 100)


class TestSectionBridging(unittest.TestCase):
    def _long(self, marker):
        return " ".join(f"Câu {marker}{i} có nội dung đủ dài để vượt ngưỡng." for i in range(12))

    def test_bridge_chunk_spans_two_sections(self):
        sections = [("Trang 1", self._long("A")), ("Trang 2", self._long("B"))]
        chunks = chunk_sections(sections, max_chars=300, overlap_chars=100)
        bridges = [c for c in chunks if "–" in c.position_ref]
        self.assertEqual(len(bridges), 1)
        # chunk bắc cầu phải chứa nội dung của CẢ HAI trang
        self.assertIn("A", bridges[0].text)
        self.assertIn("B", bridges[0].text)

    def test_bridge_position_ref_names_both_sections(self):
        sections = [("Trang 1", self._long("A")), ("Trang 2", self._long("B"))]
        chunks = chunk_sections(sections, max_chars=300, overlap_chars=100)
        bridge = next(c for c in chunks if "–" in c.position_ref)
        self.assertEqual(bridge.position_ref, "Trang 1–Trang 2")

    def test_short_sections_are_not_bridged(self):
        # section ngắn hơn cửa sổ chồng lấn thì đã nằm trọn trong chunk của
        # chính nó, bắc cầu chỉ tạo nhiễu
        sections = [("Trang 1", "Ngắn."), ("Trang 2", "Cũng ngắn.")]
        chunks = chunk_sections(sections, max_chars=800, overlap_chars=100)
        self.assertEqual([c.position_ref for c in chunks], ["Trang 1", "Trang 2"])

    def test_bridging_can_be_disabled(self):
        sections = [("Trang 1", self._long("A")), ("Trang 2", self._long("B"))]
        chunks = chunk_sections(sections, max_chars=300, overlap_chars=100, bridge_sections=False)
        self.assertEqual([c for c in chunks if "–" in c.position_ref], [])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../venv/Scripts/python.exe -m unittest tests.test_chunker`
Expected: FAIL — chunk cụt giữa câu, và không có chunk bắc cầu nào

- [ ] **Step 3: Write minimal implementation**

Viết lại `backend/app/ingestion/chunker.py`, GIỮ NGUYÊN dataclass `Chunk` và
chữ ký cũ (chỉ thêm tham số có mặc định):

```python
"""Chunking logic cho pipeline nạp tài liệu (F1).

Nhận đầu vào là danh sách "section" đã được parser.py trích xuất — mỗi section
là tuple (position_ref, text), ví dụ ("Trang 3", "...") với PDF hoặc
("Mục 2", "...") với DOCX.

Hai nguyên tắc:

1. Cắt theo RANH GIỚI CÂU, không cắt theo ký tự. Một chunk cụt giữa câu vừa
   cho embedding kém hơn, vừa hiện ra đoạn dở dang trong panel trích dẫn. Chỉ
   khi một câu đơn lẻ dài hơn max_chars mới buộc phải cắt cứng.

2. BẮC CẦU qua ranh giới section. Chồng lấn trong cùng một section không cứu
   được trường hợp nội dung vắt từ cuối trang này sang đầu trang sau — với PDF
   mỗi trang là một section nên đây là ranh giới cứng. Chunk bắc cầu ghi rõ cả
   hai vị trí trong position_ref để trích dẫn vẫn trung thực.
"""

import re
from dataclasses import dataclass
from typing import List, Tuple

# Ranh giới câu: sau dấu kết câu và khoảng trắng, hoặc xuống dòng.
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")


@dataclass
class Chunk:
    text: str
    position_ref: str
    chunk_index: int


def _hard_split(text: str, max_chars: int, overlap_chars: int) -> List[str]:
    """Cắt cứng theo ký tự — chỉ dùng cho câu đơn lẻ dài hơn max_chars."""
    step = max_chars - overlap_chars
    pieces = []
    start = 0
    while start < len(text):
        pieces.append(text[start : start + max_chars])
        if start + max_chars >= len(text):
            break
        start += step
    return pieces


def _split_text(text: str, max_chars: int, overlap_chars: int) -> List[str]:
    sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()]
    if not sentences:
        return []

    pieces: List[str] = []
    current: List[str] = []
    current_len = 0

    def flush():
        nonlocal current, current_len
        if current:
            pieces.append(" ".join(current))
        # Giữ lại các câu cuối làm phần chồng lấn cho chunk kế tiếp.
        carried: List[str] = []
        carried_len = 0
        for s in reversed(current):
            if carried_len + len(s) > overlap_chars:
                break
            carried.insert(0, s)
            carried_len += len(s) + 1
        current = carried
        current_len = carried_len

    for sentence in sentences:
        if len(sentence) > max_chars:
            # Câu quá dài: xả phần đang gom rồi cắt cứng riêng câu này.
            if current:
                pieces.append(" ".join(current))
                current, current_len = [], 0
            pieces.extend(_hard_split(sentence, max_chars, overlap_chars))
            continue

        if current_len + len(sentence) + 1 > max_chars and current:
            flush()

        current.append(sentence)
        current_len += len(sentence) + 1

    if current:
        pieces.append(" ".join(current))

    # Bỏ chunk trùng lặp hoàn toàn do phần chồng lấn sinh ra ở cuối.
    deduped = []
    for p in pieces:
        if not deduped or p != deduped[-1]:
            deduped.append(p)
    return deduped


def chunk_sections(
    sections: List[Tuple[str, str]],
    max_chars: int = 800,
    overlap_chars: int = 100,
    bridge_sections: bool = True,
) -> List[Chunk]:
    if overlap_chars >= max_chars:
        raise ValueError("overlap_chars phải nhỏ hơn max_chars")

    chunks: List[Chunk] = []
    prev_ref = None
    prev_text = None

    for position_ref, text in sections:
        stripped = text.strip()
        if not stripped:
            continue

        # Chunk bắc cầu — chỉ tạo khi CẢ HAI section đủ dài. Section ngắn hơn
        # cửa sổ chồng lấn đã nằm trọn trong chunk của chính nó rồi.
        if (
            bridge_sections
            and prev_text is not None
            and len(prev_text) >= overlap_chars
            and len(stripped) >= overlap_chars
        ):
            bridge = f"{prev_text[-overlap_chars:].strip()} {stripped[:overlap_chars].strip()}"
            chunks.append(
                Chunk(
                    text=bridge,
                    position_ref=f"{prev_ref}–{position_ref}",
                    chunk_index=len(chunks),
                )
            )

        for piece in _split_text(stripped, max_chars, overlap_chars):
            chunks.append(Chunk(text=piece, position_ref=position_ref, chunk_index=len(chunks)))

        prev_ref = position_ref
        prev_text = stripped

    return chunks
```

- [ ] **Step 4: Run test to verify it passes**

Run: `../venv/Scripts/python.exe -m unittest tests.test_chunker -v`

Test cũ `test_long_section_splits_into_multiple_chunks_with_overlap` dùng chuỗi
"AAA...BBB...CCC" không có dấu kết câu nào, nên đi vào nhánh cắt cứng và giữ
nguyên hành vi chồng lấn theo ký tự — nó phải VẪN PASS. Nếu nó vỡ thì nhánh
`_hard_split` sai, sửa nhánh đó chứ không sửa test.

Run: `../venv/Scripts/python.exe -m unittest discover -s tests`
Expected: toàn bộ PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/ingestion/chunker.py backend/tests/test_chunker.py
git commit -m "feat: chia chunk theo ranh gioi cau va bac cau qua ranh gioi section"
```

---

### Task 4: Chỉ số truy hồi độc lập

**Files:**
- Create: `eval/retrieval_metrics.py`

**Interfaces:**
- Produces: script chạy độc lập, in `recall@k` và `MRR` theo từng case và tổng hợp.

Vì sao cần: hiện mọi thứ đo qua LLM judge trên câu trả lời cuối, nên khi một
case trượt thì không biết truy hồi lấy sai đoạn hay generator viết sai — hai
nguyên nhân đòi hai cách sửa khác nhau. Chỉ số này **không tốn lượt gọi LLM
nào** và chạy trong vài giây.

- [ ] **Step 1: Viết script**

Create `eval/retrieval_metrics.py`:

```python
"""Đo CHẤT LƯỢNG TRUY HỒI tách rời khỏi chất lượng sinh nội dung.

Chạy: python eval/retrieval_metrics.py [--top-k 5] [--mode strict]

Không gọi LLM lần nào — chỉ nạp corpus, chạy truy hồi cho từng case có
`expected_evidence`, rồi đối chiếu tài liệu/vị trí trả về với tài liệu/mục kỳ
vọng. Nhờ vậy chạy được thường xuyên mà không tốn quota, và khi một case
hỏng thì biết ngay lỗi nằm ở truy hồi hay ở sinh nội dung.

Quy ước tính đúng: một đoạn được coi là trúng nếu tên tài liệu khớp với
`expected_evidence[].document`. Không đòi khớp cả `section` vì `position_ref`
của hệ thống là "Trang n"/"Mục n" chứ không phải tên tiêu đề.
"""

import argparse
import json
import os
import shutil
import sys
import tempfile
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

cli = argparse.ArgumentParser()
cli.add_argument("--top-k", type=int, default=5)
cli.add_argument("--mode", choices=["strict", "wide"], default="strict")
cli.add_argument("--golden", default="golden_set.jsonl")
ARGS = cli.parse_args()

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(EVAL_DIR)
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
DOCS_DIR = os.path.join(EVAL_DIR, "documents")

RUN_DIR = tempfile.mkdtemp(prefix="retrieval_metrics_")
os.environ["DB_PATH"] = os.path.join(RUN_DIR, "eval.db")
os.chdir(RUN_DIR)
sys.path.insert(0, BACKEND_DIR)

from fastapi.testclient import TestClient  # noqa: E402

from app.database import init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.retrieval.pipeline import retrieve_chunks  # noqa: E402

USER_ID = "retrieval-metrics-user"

init_db()
client = TestClient(app)


def upload_corpus():
    ids = {}
    for filename in sorted(os.listdir(DOCS_DIR)):
        if not filename.lower().endswith((".pdf", ".docx")):
            continue
        with open(os.path.join(DOCS_DIR, filename), "rb") as f:
            resp = client.post(
                "/documents", params={"user_id": USER_ID}, files={"file": (filename, f)}
            )
        resp.raise_for_status()
        ids[filename] = resp.json()["document_id"]
    return ids


def wait_all_ready(timeout=600):
    start = time.time()
    while time.time() - start < timeout:
        docs = client.get("/documents", params={"user_id": USER_ID}).json()
        statuses = {d["status"] for d in docs}
        if statuses == {"sẵn sàng"}:
            return
        if "lỗi" in statuses:
            broken = [d["file_name"] for d in docs if d["status"] == "lỗi"]
            raise RuntimeError(f"Tài liệu lỗi: {broken}")
        time.sleep(1)
    raise TimeoutError("Corpus chưa sẵn sàng")


def main():
    print("== Nạp corpus ==")
    upload_corpus()
    wait_all_ready()
    print("   xong")

    cases = []
    with open(os.path.join(EVAL_DIR, ARGS.golden), encoding="utf-8") as f:
        for line in f:
            if line.strip():
                case = json.loads(line)
                if case.get("expected_evidence") and case.get("input", {}).get("query"):
                    cases.append(case)

    print(f"\n== Đo trên {len(cases)} case có expected_evidence (top_k={ARGS.top_k}, mode={ARGS.mode}) ==")

    hits = 0
    reciprocal_ranks = []
    misses = []

    for case in cases:
        expected_docs = {e["document"] for e in case["expected_evidence"]}
        chunks = retrieve_chunks(
            user_id=USER_ID,
            query=case["input"]["query"],
            top_k=ARGS.top_k,
            mode=ARGS.mode,
        )
        retrieved_docs = [c.document_name for c in chunks]

        rank = next((i + 1 for i, d in enumerate(retrieved_docs) if d in expected_docs), None)
        if rank:
            hits += 1
            reciprocal_ranks.append(1.0 / rank)
        else:
            reciprocal_ranks.append(0.0)
            misses.append((case["id"], case["input"]["query"], sorted(expected_docs), retrieved_docs))

    total = len(cases) or 1
    print(f"\nrecall@{ARGS.top_k} = {hits / total:.3f}  ({hits}/{len(cases)})")
    print(f"MRR         = {sum(reciprocal_ranks) / total:.3f}")

    if misses:
        print(f"\n== {len(misses)} case truy hồi TRƯỢT ==")
        for cid, query, expected, got in misses[:20]:
            print(f"  {cid}: {query[:60]}")
            print(f"     kỳ vọng: {expected}")
            print(f"     lấy về : {got}")

    shutil.rmtree(RUN_DIR, ignore_errors=True)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Chạy thử trên Golden Set hiện có**

Run từ gốc repo: `venv/Scripts/python.exe eval/retrieval_metrics.py --top-k 5`
Expected: in ra recall@5 và MRR, kèm danh sách case trượt. Con số này là mốc
tham chiếu (baseline) để so sánh sau khi đổi chunking.

- [ ] **Step 3: Commit**

```bash
git add eval/retrieval_metrics.py
git commit -m "feat(eval): chi so truy hoi doc lap, khong ton luot goi LLM"
```

---

## Kiểm chứng cuối giai đoạn F

- [ ] Toàn bộ test backend PASS
- [ ] Chạy `eval/retrieval_metrics.py` TRƯỚC và SAU khi đổi chunking, ghi lại hai con số recall@5 để biết thay đổi có thực sự cải thiện hay không — nếu không cải thiện thì phải nói thẳng chứ không giữ thay đổi chỉ vì nó "đúng về lý thuyết"
- [ ] Kiểm chứng thủ công câu hỏi tiếp nối: hỏi "CNN dùng convolution để làm gì?" rồi hỏi tiếp "tại sao nó tốt hơn?", xác nhận truy vấn truy hồi lượt hai có chứa từ khoá của lượt một
