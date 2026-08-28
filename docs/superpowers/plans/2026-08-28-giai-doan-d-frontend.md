# Giai đoạn D — Frontend phủ toàn bộ backend: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Không còn endpoint backend nào không truy cập được từ giao diện, và
đưa citation ba lớp cùng bằng chứng phủ định ra tới người dùng.

**Architecture:** React 18 + Vite + Tailwind, react-router-dom v6, icon
lucide-react. Dùng lại nguyên bộ `components/ui` sẵn có (`Card`, `Button`,
`Input`, `Select`, `Badge`, `ProgressBar`, `EmptyState`) và helper `cn` — không
dựng hệ thống component mới. Toàn bộ nhãn tiếng Việt, màu dùng token ngữ nghĩa
(`text-foreground`, `text-muted-foreground`, `border-border`, `text-primary`,
`text-destructive`, `text-success`, `bg-card`, `bg-muted`).

**Tech Stack:** React 18.3, Vite 5.4, Tailwind 3.4, react-router-dom 6.26, lucide-react.

**Spec:** `docs/superpowers/specs/2026-08-28-edututor-completion-design.md` (mục 6)

## Global Constraints

- **Frontend KHÔNG có framework test.** Kiểm chứng mỗi task bằng `npm run build` từ `frontend/` — build phải sạch, không cảnh báo import thiếu. Đây là giới hạn có thật của repo, không phải bỏ qua kiểm chứng.
- Bám đúng phong cách `frontend/src/pages/QuizPage.jsx` — đọc file đó trước khi viết trang mới; nó là bản mẫu cho bố cục Card, xử lý `loading`/`error`, và cách gọi API.
- Mọi lời gọi API đi qua `frontend/src/api.js`, không `fetch` trực tiếp trong component.
- Không đổi `CURRENT_USER_ID` — đăng nhập thật ngoài phạm vi.
- Nhãn và thông báo lỗi bằng tiếng Việt.

---

### Task 1: Phủ toàn bộ endpoint trong api.js

**Files:**
- Modify: `frontend/src/api.js`

**Interfaces (Produces):**

```
askQuestion(question, conversationId, level)        // thêm tham số level
generateQuiz(documentId, topicName, numQuestions, difficulty)  // thêm difficulty
generateFlashcards(documentId, topicName, numCards)
listDueFlashcards(limit)
reviewFlashcard(flashcardItemId, rating)
getStudyPlan(days, courseName)
getProfile()
updateProfile({ preferredLevel, learningGoal })
listMemory(limit)
deleteMemory(eventId)
documentFileUrl(documentId, positionRef)            // dựng URL, KHÔNG fetch
```

- [ ] **Step 1: Viết các hàm mới**

Thêm `level` vào `askQuestion` và `difficulty` vào `generateQuiz` (chỉ gửi khi
có giá trị, để backend giữ nguyên hành vi suy ra từ Learning Profile khi người
dùng không chọn gì):

```javascript
export async function askQuestion(question, conversationId, level) {
  const res = await fetch(`${API_BASE}/chat/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_id: CURRENT_USER_ID,
      question,
      conversation_id: conversationId || null,
      // Không gửi level khi người dùng để "Tự động" — backend sẽ dùng
      // preference đã lưu hoặc suy từ mastery (app/learner_context.py).
      ...(level ? { level } : {}),
    }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function generateQuiz(documentId, topicName, numQuestions = 5, difficulty) {
  const res = await fetch(`${API_BASE}/quiz/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_id: CURRENT_USER_ID,
      document_id: documentId,
      topic_name: topicName || null,
      num_questions: numQuestions,
      ...(difficulty ? { difficulty } : {}),
    }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
```

Thêm mới ở cuối file:

```javascript
export async function generateFlashcards(documentId, topicName, numCards = 10) {
  const res = await fetch(`${API_BASE}/flashcard/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_id: CURRENT_USER_ID,
      document_id: documentId,
      topic_name: topicName || null,
      num_cards: numCards,
    }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function listDueFlashcards(limit = 20) {
  const res = await fetch(
    `${API_BASE}/flashcard/due?user_id=${CURRENT_USER_ID}&limit=${limit}`
  );
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function reviewFlashcard(flashcardItemId, rating) {
  const res = await fetch(`${API_BASE}/flashcard/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_id: CURRENT_USER_ID,
      flashcard_item_id: flashcardItemId,
      rating,
    }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getStudyPlan(days, courseName) {
  const params = new URLSearchParams({ user_id: CURRENT_USER_ID, days: String(days) });
  if (courseName) params.set("course_name", courseName);
  const res = await fetch(`${API_BASE}/study-plan?${params}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getProfile() {
  const res = await fetch(`${API_BASE}/profile?user_id=${CURRENT_USER_ID}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function updateProfile({ preferredLevel, learningGoal }) {
  const res = await fetch(`${API_BASE}/profile`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_id: CURRENT_USER_ID,
      preferred_level: preferredLevel ?? null,
      learning_goal: learningGoal ?? null,
    }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function listMemory(limit = 50) {
  const res = await fetch(`${API_BASE}/memory?user_id=${CURRENT_USER_ID}&limit=${limit}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function deleteMemory(eventId) {
  const res = await fetch(`${API_BASE}/memory/${eventId}?user_id=${CURRENT_USER_ID}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// Dựng URL mở tài liệu gốc. PDF nhảy đúng trang bằng fragment '#page=N' bóc từ
// position_ref dạng "Trang 5". DOCX dùng position_ref dạng "Mục n" — không có
// khái niệm trang nên KHÔNG gắn fragment, mở từ đầu file (hạn chế đã biết,
// xem spec mục 4.3).
export function documentFileUrl(documentId, positionRef) {
  const base = `${API_BASE}/documents/${documentId}/file?user_id=${CURRENT_USER_ID}`;
  const match = /Trang\s+(\d+)/i.exec(positionRef || "");
  return match ? `${base}#page=${match[1]}` : base;
}
```

- [ ] **Step 2: Kiểm chứng**

Run từ `frontend/`: `npm run build`
Expected: build thành công, không lỗi

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api.js
git commit -m "feat(fe): phu toan bo endpoint backend trong api.js"
```

---

### Task 2: Component hiển thị citation và bằng chứng phủ định

**Files:**
- Create: `frontend/src/components/AnswerWithCitations.jsx`
- Create: `frontend/src/components/CitationPanel.jsx`
- Create: `frontend/src/components/SearchReport.jsx`

**Interfaces (Produces):**
- `<AnswerWithCitations answer={string} sources={array} onOpenSource={(index) => void} />`
- `<CitationPanel source={object|null} onClose={() => void} />`
- `<SearchReport report={object|null} onOpenNearMiss={(nearMiss) => void} />`

- [ ] **Step 1: AnswerWithCitations — biến [n] thành nút bấm được**

Create `frontend/src/components/AnswerWithCitations.jsx`:

```jsx
import { Fragment } from "react";

// Backend gắn [n] sau mỗi luận điểm và đã loại bỏ marker trỏ sai phạm vi
// (app/llm/rag.py::_strip_invalid_citations), nên mọi [n] còn lại ở đây đều
// tương ứng một phần tử trong `sources`.
const MARKER_RE = /\[(\d+)\]/g;

export default function AnswerWithCitations({ answer, sources = [], onOpenSource }) {
  if (!answer) return null;

  const parts = [];
  let lastIndex = 0;
  let match;

  MARKER_RE.lastIndex = 0;
  while ((match = MARKER_RE.exec(answer)) !== null) {
    const index = Number(match[1]);
    const source = sources[index - 1];

    if (match.index > lastIndex) {
      parts.push({ type: "text", value: answer.slice(lastIndex, match.index) });
    }
    // Marker không có nguồn tương ứng thì hiện như text thường, không dựng nút
    // bấm dẫn tới hư không.
    parts.push(source ? { type: "cite", index, source } : { type: "text", value: match[0] });
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < answer.length) {
    parts.push({ type: "text", value: answer.slice(lastIndex) });
  }

  return (
    <p className="whitespace-pre-wrap text-sm leading-relaxed text-foreground">
      {parts.map((part, i) =>
        part.type === "text" ? (
          <Fragment key={i}>{part.value}</Fragment>
        ) : (
          <button
            key={i}
            type="button"
            onClick={() => onOpenSource(part.index - 1)}
            title={`${part.source.document_name} — ${part.source.position_ref}`}
            className="mx-0.5 inline-flex h-5 min-w-5 cursor-pointer items-center justify-center rounded border border-primary/40 bg-primary/10 px-1 align-baseline text-xs font-medium text-primary transition-colors hover:bg-primary/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {part.index}
          </button>
        )
      )}
    </p>
  );
}
```

- [ ] **Step 2: CitationPanel — hiện nguyên văn đoạn, tô sáng câu chống đỡ**

Create `frontend/src/components/CitationPanel.jsx`:

```jsx
import { ExternalLink, X } from "lucide-react";
import { documentFileUrl } from "../api";
import { cn } from "../lib/cn";

// Backend đã tính sẵn danh sách câu chống đỡ bằng trùng lặp từ vựng
// (app/citation.py), frontend chỉ việc tô sáng chúng trong nguyên văn đoạn.
function highlight(text, supporting) {
  if (!supporting || supporting.length === 0) return text;

  let remaining = text;
  const nodes = [];
  supporting.forEach((sentence, i) => {
    const at = remaining.indexOf(sentence);
    if (at === -1) return;
    if (at > 0) nodes.push(remaining.slice(0, at));
    nodes.push(
      <mark key={i} className="rounded bg-primary/15 px-0.5 text-foreground">
        {sentence}
      </mark>
    );
    remaining = remaining.slice(at + sentence.length);
  });
  if (remaining) nodes.push(remaining);
  return nodes;
}

export default function CitationPanel({ source, onClose }) {
  if (!source) return null;

  const isPdf = /Trang\s+\d+/i.test(source.position_ref || "");

  return (
    <>
      <div
        className="fixed inset-0 z-40 bg-foreground/30 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden="true"
      />
      <aside
        className={cn(
          "fixed inset-y-0 right-0 z-50 flex w-full max-w-md flex-col border-l border-border bg-card shadow-xl",
          "animate-in slide-in-from-right"
        )}
        role="dialog"
        aria-label="Đoạn trích nguồn"
      >
        <div className="flex items-start justify-between gap-3 border-b border-border p-4">
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-foreground">{source.document_name}</p>
            <p className="text-xs text-muted-foreground">{source.position_ref}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="shrink-0 cursor-pointer rounded-md p-1.5 text-muted-foreground hover:bg-muted"
            aria-label="Đóng"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4">
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-foreground">
            {highlight(source.text || "", source.supporting_sentences)}
          </p>
        </div>

        <div className="border-t border-border p-4">
          {source.document_id ? (
            <a
              href={documentFileUrl(source.document_id, source.position_ref)}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-2 text-sm font-medium text-primary hover:underline"
            >
              <ExternalLink className="h-4 w-4" aria-hidden="true" />
              {isPdf ? "Mở tài liệu gốc đúng trang" : "Mở tài liệu gốc"}
            </a>
          ) : null}
          {!isPdf && (
            <p className="mt-2 text-xs text-muted-foreground">
              Tài liệu DOCX không có số trang cố định nên không nhảy tới đúng vị trí được.
            </p>
          )}
        </div>
      </aside>
    </>
  );
}
```

- [ ] **Step 3: SearchReport — bằng chứng phủ định**

Create `frontend/src/components/SearchReport.jsx`:

```jsx
import { SearchX } from "lucide-react";

export default function SearchReport({ report, onOpenNearMiss }) {
  if (!report || !report.near_misses || report.near_misses.length === 0) return null;

  return (
    <div className="mt-3 rounded-lg border border-border bg-muted/40 p-3">
      <div className="flex items-center gap-2 text-sm font-medium text-foreground">
        <SearchX className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
        Hệ thống đã tìm {report.passes_run} lượt trong{" "}
        {report.searched_documents?.length ?? 0} tài liệu
      </div>
      <p className="mt-1 text-xs text-muted-foreground">
        Đây là những đoạn gần đúng nhất tìm được — bấm để tự đối chiếu xem nội dung bạn hỏi
        có thật sự nằm trong tài liệu hay không.
      </p>
      <ul className="mt-2 flex flex-col gap-1.5">
        {report.near_misses.map((n) => (
          <li key={n.chunk_id || `${n.document_name}-${n.position_ref}`}>
            <button
              type="button"
              onClick={() => onOpenNearMiss(n)}
              className="w-full cursor-pointer rounded-md border border-border bg-card px-3 py-2 text-left text-xs transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <span className="font-medium text-foreground">
                {n.document_name} — {n.position_ref}
              </span>
              <span className="ml-2 text-muted-foreground">(độ liên quan {n.score.toFixed(2)})</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
```

- [ ] **Step 4: Kiểm chứng**

Run từ `frontend/`: `npm run build`
Expected: build thành công

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/AnswerWithCitations.jsx frontend/src/components/CitationPanel.jsx frontend/src/components/SearchReport.jsx
git commit -m "feat(fe): component citation va bang chung phu dinh"
```

---

### Task 3: ChatPage dùng citation, bằng chứng phủ định, chọn trình độ

**Files:**
- Modify: `frontend/src/pages/ChatPage.jsx`

**Interfaces:**
- Consumes: `askQuestion(question, conversationId, level)`, `AnswerWithCitations`, `CitationPanel`, `SearchReport`

- [ ] **Step 1: Đọc trang hiện tại**

Đọc `frontend/src/pages/ChatPage.jsx` trước khi sửa — giữ nguyên toàn bộ phần
quản lý hội thoại và danh sách tin nhắn đã có, chỉ thay phần hiển thị câu trả
lời và thêm ô chọn trình độ.

- [ ] **Step 2: Thêm state và ô chọn trình độ**

Thêm vào phần state của component:

```jsx
  const [level, setLevel] = useState("");           // "" = tự động
  const [openSource, setOpenSource] = useState(null); // nguồn đang mở trong panel
```

Truyền `level` vào lời gọi: `askQuestion(question, conversationId, level)`.

Thêm ô chọn ngay cạnh ô nhập câu hỏi (dùng `Select` từ `components/ui/Select`):

```jsx
<Select
  aria-label="Trình độ"
  value={level}
  onChange={(e) => setLevel(e.target.value)}
  className="w-40 shrink-0"
>
  <option value="">Trình độ: tự động</option>
  <option value="beginner">Người mới bắt đầu</option>
  <option value="advanced">Nâng cao</option>
</Select>
```

- [ ] **Step 3: Thay chỗ hiển thị câu trả lời**

Với mỗi tin nhắn của trợ lý, thay đoạn hiển thị text thuần bằng:

```jsx
<AnswerWithCitations
  answer={message.content}
  sources={message.sources}
  onOpenSource={(i) => setOpenSource(message.sources[i])}
/>
{message.search_report && (
  <SearchReport
    report={message.search_report}
    onOpenNearMiss={(n) => setOpenSource({ ...n, supporting_sentences: [] })}
  />
)}
```

Bảo đảm khi nhận response từ `askQuestion`, lưu cả `sources`, `search_report`
và `abstained` vào object tin nhắn trong state, không chỉ `answer`.

Đặt `<CitationPanel source={openSource} onClose={() => setOpenSource(null)} />`
ở cuối JSX gốc của trang.

- [ ] **Step 4: Kiểm chứng**

Run từ `frontend/`: `npm run build`
Expected: build thành công

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/ChatPage.jsx
git commit -m "feat(fe): ChatPage hien citation, bang chung phu dinh, chon trinh do"
```

---

### Task 4: QuizPage chọn số lượng câu và độ khó

**Files:**
- Modify: `frontend/src/pages/QuizPage.jsx`

- [ ] **Step 1: Thêm hai ô điều khiển**

Thêm state `numQuestions` (mặc định 5) và `difficulty` (mặc định `""` = tự
động), rồi thêm vào hàng điều khiển đã có:

```jsx
<div className="w-32">
  <label htmlFor="quiz-count" className="mb-1.5 block text-sm font-medium text-foreground">
    Số câu
  </label>
  <Select id="quiz-count" value={numQuestions} onChange={(e) => setNumQuestions(Number(e.target.value))}>
    {[3, 5, 10, 15, 20].map((n) => (
      <option key={n} value={n}>{n} câu</option>
    ))}
  </Select>
</div>
<div className="w-40">
  <label htmlFor="quiz-difficulty" className="mb-1.5 block text-sm font-medium text-foreground">
    Độ khó
  </label>
  <Select id="quiz-difficulty" value={difficulty} onChange={(e) => setDifficulty(e.target.value)}>
    <option value="">Tự động</option>
    <option value="beginner">Cơ bản</option>
    <option value="intermediate">Vận dụng</option>
    <option value="advanced">Nâng cao</option>
  </Select>
</div>
```

Đổi lời gọi thành `generateQuiz(documentId, topicName, numQuestions, difficulty)`.

"Tự động" gửi `undefined` nên backend dùng trình độ đã lưu trong Learning
Profile hoặc suy từ mastery — đó là hành vi mong muốn, không phải thiếu sót.

- [ ] **Step 2: Kiểm chứng**

Run từ `frontend/`: `npm run build`

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/QuizPage.jsx
git commit -m "feat(fe): QuizPage chon so luong cau va do kho"
```

---

### Task 5: Trang Flashcards với vòng ôn tập

**Files:**
- Create: `frontend/src/pages/FlashcardsPage.jsx`

**Hành vi:** hai khối. Khối trên sinh thẻ mới từ một tài liệu (giống khối "Tạo
quiz" trong `QuizPage.jsx`). Khối dưới là vòng ôn: hiện mặt trước, bấm "Lật thẻ"
mới hiện mặt sau và bốn nút đánh giá; đánh giá xong tự chuyển thẻ kế tiếp.

- [ ] **Step 1: Viết trang**

Create `frontend/src/pages/FlashcardsPage.jsx`:

```jsx
import { useEffect, useState } from "react";
import { Layers, Sparkles } from "lucide-react";
import {
  generateFlashcards,
  listDocuments,
  listDueFlashcards,
  reviewFlashcard,
} from "../api";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/Card";
import Button from "../components/ui/Button";
import Input from "../components/ui/Input";
import Select from "../components/ui/Select";
import EmptyState from "../components/ui/EmptyState";

// Bốn mức của app/spaced_repetition.py — nhãn tiếng Việt, giữ nguyên giá trị
// gửi lên backend.
const RATINGS = [
  { value: "again", label: "Quên rồi", hint: "gặp lại ngay" },
  { value: "hard", label: "Khó", hint: "sớm gặp lại" },
  { value: "good", label: "Được", hint: "lịch bình thường" },
  { value: "easy", label: "Dễ", hint: "để lâu hơn" },
];

export default function FlashcardsPage() {
  const [documents, setDocuments] = useState([]);
  const [documentId, setDocumentId] = useState("");
  const [topicName, setTopicName] = useState("");
  const [numCards, setNumCards] = useState(10);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState(null);

  const [due, setDue] = useState([]);
  const [current, setCurrent] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [lastResult, setLastResult] = useState(null);

  const loadDue = async () => {
    const res = await listDueFlashcards();
    setDue(res.items);
    setCurrent(0);
    setFlipped(false);
  };

  useEffect(() => {
    listDocuments().then((docs) => setDocuments(docs.filter((d) => d.status === "sẵn sàng")));
    loadDue().catch((e) => setError(e.message));
  }, []);

  const handleGenerate = async () => {
    if (!documentId) return;
    setGenerating(true);
    setError(null);
    try {
      await generateFlashcards(documentId, topicName, numCards);
      await loadDue();
    } catch (e) {
      setError(e.message);
    } finally {
      setGenerating(false);
    }
  };

  const handleRate = async (rating) => {
    const card = due[current];
    if (!card) return;
    try {
      const res = await reviewFlashcard(card.id, rating);
      setLastResult({ front: card.front, ...res });
      setFlipped(false);
      // "Quên rồi" đặt hạn về 0 nên thẻ vẫn còn đến hạn — nạp lại danh sách để
      // nó quay lại cuối hàng đợi thay vì biến mất.
      if (rating === "again") {
        await loadDue();
      } else if (current + 1 >= due.length) {
        await loadDue();
      } else {
        setCurrent((c) => c + 1);
      }
    } catch (e) {
      setError(e.message);
    }
  };

  const card = due[current];

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-base font-semibold text-foreground">Tạo bộ flashcard mới</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <div className="flex-1">
              <label htmlFor="fc-doc" className="mb-1.5 block text-sm font-medium text-foreground">
                Tài liệu
              </label>
              <Select id="fc-doc" value={documentId} onChange={(e) => setDocumentId(e.target.value)}>
                <option value="">-- Chọn tài liệu --</option>
                {documents.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.course_name ? `${d.course_name} — ${d.file_name}` : d.file_name}
                  </option>
                ))}
              </Select>
            </div>
            <div className="flex-1">
              <label htmlFor="fc-topic" className="mb-1.5 block text-sm font-medium text-foreground">
                Chủ đề (tuỳ chọn)
              </label>
              <Input
                id="fc-topic"
                placeholder="VD: Hàm kích hoạt"
                value={topicName}
                onChange={(e) => setTopicName(e.target.value)}
              />
            </div>
            <div className="w-32">
              <label htmlFor="fc-count" className="mb-1.5 block text-sm font-medium text-foreground">
                Số thẻ
              </label>
              <Select id="fc-count" value={numCards} onChange={(e) => setNumCards(Number(e.target.value))}>
                {[5, 10, 15, 20].map((n) => (
                  <option key={n} value={n}>{n} thẻ</option>
                ))}
              </Select>
            </div>
            <Button onClick={handleGenerate} disabled={!documentId} loading={generating} className="shrink-0">
              <Sparkles className="h-4 w-4" aria-hidden="true" />
              {generating ? "Đang sinh thẻ..." : "Tạo thẻ"}
            </Button>
          </div>
          {error && <p className="mt-3 text-sm text-destructive">{error}</p>}
        </CardContent>
      </Card>

      {!card ? (
        <EmptyState
          icon={Layers}
          title="Không có thẻ nào đến hạn"
          description="Tạo một bộ thẻ mới ở trên, hoặc quay lại sau khi tới lịch ôn kế tiếp."
        />
      ) : (
        <Card>
          <CardHeader>
            <CardTitle className="text-base font-semibold text-foreground">
              Ôn tập — còn {due.length - current} thẻ
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <div className="rounded-lg border border-border bg-muted/40 p-6 text-center">
              <p className="text-base font-medium text-foreground">{card.front}</p>
              {flipped && (
                <>
                  <hr className="my-4 border-border" />
                  <p className="text-sm leading-relaxed text-foreground">{card.back}</p>
                  {card.source_document && (
                    <p className="mt-3 text-xs text-muted-foreground">
                      Nguồn: {card.source_document} — {card.source_position}
                    </p>
                  )}
                </>
              )}
            </div>

            {!flipped ? (
              <Button onClick={() => setFlipped(true)} className="self-center">
                Lật thẻ
              </Button>
            ) : (
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                {RATINGS.map((r) => (
                  <button
                    key={r.value}
                    type="button"
                    onClick={() => handleRate(r.value)}
                    className="flex min-h-11 cursor-pointer flex-col items-center justify-center rounded-lg border border-border px-3 py-2 text-sm transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    <span className="font-medium text-foreground">{r.label}</span>
                    <span className="text-xs text-muted-foreground">{r.hint}</span>
                  </button>
                ))}
              </div>
            )}

            {lastResult && (
              <p className="text-center text-xs text-muted-foreground">
                Thẻ trước ({lastResult.rating}): sẽ gặp lại sau {lastResult.interval_days} ngày.
              </p>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Kiểm chứng**

Run từ `frontend/`: `npm run build`

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/FlashcardsPage.jsx
git commit -m "feat(fe): trang Flashcards voi vong on tap"
```

---

### Task 6: Trang Kế hoạch ôn tập và Hồ sơ học tập

**Files:**
- Create: `frontend/src/pages/StudyPlanPage.jsx`
- Create: `frontend/src/pages/ProfilePage.jsx`

- [ ] **Step 1: StudyPlanPage**

Nhập số ngày còn lại, gọi `getStudyPlan(days)`, hiển thị mỗi ngày là một Card
với danh sách chủ đề. Response có dạng `{ days: [{ day: 1, topics: ["A","B"] }] }`.
Khi `days` rỗng thì hiện `EmptyState` với icon `CalendarDays`, nội dung nói rõ
cần có dữ liệu mastery trước (làm quiz) thì mới chia lịch được.

- [ ] **Step 2: ProfilePage**

Gọi `getProfile()` khi mở trang. Hiển thị:
- `Select` chọn `preferred_level` (rỗng / beginner / advanced)
- `Input` nhập `learning_goal`
- Hai danh sách chỉ đọc `weak_topics` và `mastered_topics`, dựng bằng `Badge`

Nút "Lưu" gọi `updateProfile({ preferredLevel, learningGoal })`. Backend trả
lỗi 400 kèm thông báo khi `learning_goal` khớp mẫu injection
(`app/routers/profile.py`) — bắt lỗi đó và hiện nguyên văn thông báo bằng
`text-destructive`, đây là phản hồi có ý nghĩa với người dùng chứ không phải
lỗi kỹ thuật cần giấu.

- [ ] **Step 3: Kiểm chứng**

Run từ `frontend/`: `npm run build`

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/StudyPlanPage.jsx frontend/src/pages/ProfilePage.jsx
git commit -m "feat(fe): trang ke hoach on tap va ho so hoc tap"
```

---

### Task 7: Trang Ký ức

**Files:**
- Create: `frontend/src/pages/MemoryPage.jsx`

**Hành vi:** liệt kê `listMemory()`, mỗi mục hiện nội dung, loại sự kiện (dưới
dạng `Badge` với nhãn tiếng Việt), chủ đề, thời điểm, số lần được gọi lại, và
một nút xoá gọi `deleteMemory(id)`.

Trang này tồn tại vì ký ức chi phối câu trả lời người dùng nhận được — họ phải
thấy được và xoá được thứ đang tác động lên mình.

- [ ] **Step 1: Viết trang**

Ánh xạ nhãn loại sự kiện (khớp `app/memory/scoring.py`):

```jsx
const EVENT_LABELS = {
  quiz_wrong: "Làm sai quiz",
  quiz_right: "Làm đúng quiz",
  flashcard_again: "Quên flashcard",
  flashcard_easy: "Thấy thẻ quá dễ",
  concept_confused: "Chưa hiểu khái niệm",
  abstention: "Hỏi điều không có trong tài liệu",
  question_asked: "Đã hỏi",
};
```

Bố cục danh sách theo đúng khuôn Card đang dùng ở các trang khác. Sau khi xoá
thành công thì lọc mục đó khỏi state, không cần nạp lại toàn bộ.

- [ ] **Step 2: Kiểm chứng**

Run từ `frontend/`: `npm run build`

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/MemoryPage.jsx
git commit -m "feat(fe): trang Ky uc xem va xoa"
```

---

### Task 8: Định tuyến và điều hướng

**Files:**
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/components/layout/Sidebar.jsx`

- [ ] **Step 1: Thêm route**

Trong `frontend/src/App.jsx`, thêm import bốn trang mới và bổ sung
`PAGE_TITLES` cùng `<Route>`:

```jsx
const PAGE_TITLES = {
  "/": "Tổng quan",
  "/documents": "Tài liệu học tập",
  "/chat": "Hỏi đáp tài liệu",
  "/quiz": "Quiz tự kiểm tra",
  "/flashcards": "Flashcard ôn tập",
  "/study-plan": "Kế hoạch ôn tập",
  "/profile": "Hồ sơ học tập",
  "/memory": "Ký ức hệ thống",
};
```

```jsx
<Route path="/flashcards" element={<FlashcardsPage />} />
<Route path="/study-plan" element={<StudyPlanPage />} />
<Route path="/profile" element={<ProfilePage />} />
<Route path="/memory" element={<MemoryPage />} />
```

- [ ] **Step 2: Thêm mục điều hướng**

Trong `frontend/src/components/layout/Sidebar.jsx`, thêm icon vào import từ
`lucide-react` và bổ sung `NAV_ITEMS`:

```jsx
import {
  Brain, CalendarDays, FileText, GraduationCap, LayoutDashboard,
  Layers, ListChecks, MessageCircle, UserCog, X,
} from "lucide-react";

const NAV_ITEMS = [
  { to: "/", label: "Tổng quan", icon: LayoutDashboard, end: true },
  { to: "/documents", label: "Tài liệu", icon: FileText },
  { to: "/chat", label: "Hỏi đáp", icon: MessageCircle },
  { to: "/quiz", label: "Quiz", icon: ListChecks },
  { to: "/flashcards", label: "Flashcard", icon: Layers },
  { to: "/study-plan", label: "Kế hoạch ôn", icon: CalendarDays },
  { to: "/profile", label: "Hồ sơ", icon: UserCog },
  { to: "/memory", label: "Ký ức", icon: Brain },
];
```

- [ ] **Step 3: Kiểm chứng**

Run từ `frontend/`: `npm run build`
Expected: build thành công

- [ ] **Step 4: Commit**

```bash
git add frontend/src/App.jsx frontend/src/components/layout/Sidebar.jsx
git commit -m "feat(fe): dinh tuyen va dieu huong cho cac trang moi"
```

---

## Kiểm chứng cuối giai đoạn D

- [ ] `npm run build` từ `frontend/` chạy sạch
- [ ] Đối chiếu từng route backend với một chỗ gọi trong `frontend/src/api.js`: `/documents` (GET, POST, DELETE, `/file`), `/chat/ask`, `/chat/conversations`, `/quiz/generate`, `/quiz/submit`, `/mastery`, `/flashcard/generate`, `/flashcard/due`, `/flashcard/review`, `/study-plan`, `/profile` (GET, PUT), `/memory` (GET, DELETE) — không route nào bị bỏ sót
- [ ] Chạy backend rồi mở giao diện, xác nhận bốn trang mới hiển thị được và sidebar dẫn tới đúng chỗ
