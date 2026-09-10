import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { History, Layers, Sparkles, Target } from "lucide-react";
import {
  generateFlashcards,
  getFlashcardBoard,
  getFlashcardHistory,
  getFlashcardMistakes,
  listDocuments,
  listDueFlashcards,
  reviewFlashcard,
} from "../api";
import { DOCUMENT_STATUS, GENERATION_MODES } from "../lib/constants";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/Card";
import Button from "../components/ui/Button";
import Input from "../components/ui/Input";
import Select from "../components/ui/Select";
import EmptyState from "../components/ui/EmptyState";

// Bốn mức của app/services/spaced_repetition.py — nhãn tiếng Việt, giữ
// nguyên giá trị gửi lên backend.
const RATINGS = [
  { value: "again", label: "Quên rồi", hint: "gặp lại ngay" },
  { value: "hard", label: "Khó", hint: "sớm gặp lại" },
  { value: "good", label: "Được", hint: "lịch bình thường" },
  { value: "easy", label: "Dễ", hint: "để lâu hơn" },
];
const RATING_LABEL = Object.fromEntries(RATINGS.map((r) => [r.value, r.label]));

const BOARD_BUCKETS = [
  { key: "due", label: "Đến hạn" },
  { key: "learning", label: "Đang học" },
  { key: "mastered", label: "Đã thuộc" },
];

export default function FlashcardsPage() {
  const [searchParams] = useSearchParams();
  const [documents, setDocuments] = useState([]);
  const [documentId, setDocumentId] = useState(() => searchParams.get("document") || "");
  const [topicName, setTopicName] = useState(() => searchParams.get("topic") || "");
  // Lý do đề xuất từ Study Plan (Learning Loop Phase 1) — đọc 1 lần lúc vào
  // trang, không theo dõi thay đổi searchParams sau đó (cùng lý do QuizPage).
  const [recommendationReason] = useState(() => searchParams.get("reason") || "");
  const [numCards, setNumCards] = useState(10);
  // Learning Loop Phase 3 — cùng lý do/hành vi với QuizPage.
  const [generationMode, setGenerationMode] = useState(() => searchParams.get("mode") || "");
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState(null);
  // Phase 4 — mirror QuizPage: backend giờ báo rõ khi tạo được ít thẻ hơn yêu
  // cầu (BUG-003 mở rộng sang flashcard) thay vì để người dùng tự đếm.
  const [partialNotice, setPartialNotice] = useState(null);

  const [due, setDue] = useState([]);
  const [dueLoading, setDueLoading] = useState(true);
  const [current, setCurrent] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [lastResult, setLastResult] = useState(null);

  const [board, setBoard] = useState(null);
  const [mistakes, setMistakes] = useState([]);
  // itemId -> mảng lượt ôn đã tải (chưa tải thì không có key) — tránh gọi lại
  // API mỗi lần đóng/mở lại cùng một thẻ trong danh sách "hay quên".
  const [historyByItem, setHistoryByItem] = useState({});
  const [expandedMistakeId, setExpandedMistakeId] = useState(null);

  const loadDue = async () => {
    try {
      const res = await listDueFlashcards();
      setDue(res.items);
      setCurrent(0);
      setFlipped(false);
    } finally {
      setDueLoading(false);
    }
  };

  // Board + mistakes không chặn màn ôn chính (khác loadDue, tách riêng để một
  // lỗi ở đây không làm hỏng cả trang) — cùng lý do handleAnswer/handleRate
  // của QuizPage bắt lỗi riêng cho từng hành động phụ.
  const loadProgress = async () => {
    try {
      const [boardRes, mistakesRes] = await Promise.all([getFlashcardBoard(), getFlashcardMistakes()]);
      setBoard(boardRes);
      setMistakes(mistakesRes.mistakes);
    } catch (e) {
      setError(e.message);
    }
  };

  useEffect(() => {
    listDocuments()
      .then((docs) => setDocuments(docs.filter((d) => d.status === DOCUMENT_STATUS.READY)))
      .catch((e) => setError(e.message));
    loadDue().catch((e) => setError(e.message));
    loadProgress();
  }, []);

  const toggleHistory = async (itemId) => {
    if (expandedMistakeId === itemId) {
      setExpandedMistakeId(null);
      return;
    }
    setExpandedMistakeId(itemId);
    if (!historyByItem[itemId]) {
      try {
        const res = await getFlashcardHistory(itemId);
        setHistoryByItem((h) => ({ ...h, [itemId]: res.history }));
      } catch (e) {
        setError(e.message);
      }
    }
  };

  const handleGenerate = async () => {
    if (!documentId) return;
    setGenerating(true);
    setError(null);
    setPartialNotice(null);
    try {
      const res = await generateFlashcards(documentId, topicName, numCards, generationMode);
      if (res.partial) {
        setPartialNotice(`Chỉ tạo được ${res.generated}/${res.requested} thẻ dựa trên nội dung tài liệu.`);
      }
      await loadDue();
      await loadProgress();
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
      // "Quên rồi" đặt hạn về 0 nên thẻ VẪN còn đến hạn — nạp lại danh sách để
      // nó quay lại hàng đợi thay vì biến mất khỏi phiên ôn.
      if (rating === "again" || current + 1 >= due.length) {
        await loadDue();
      } else {
        setCurrent((c) => c + 1);
      }
      await loadProgress();
    } catch (e) {
      setError(e.message);
    }
  };

  const card = due[current];

  return (
    <div className="flex flex-col gap-6">
      {recommendationReason && (
        <p className="flex items-center gap-2 rounded-lg border border-primary/40 bg-primary/5 px-4 py-2.5 text-sm text-primary">
          <Target className="h-4 w-4 shrink-0" aria-hidden="true" />
          {recommendationReason}
        </p>
      )}
      <Card>
        <CardHeader>
          <CardTitle className="text-base font-semibold text-foreground">
            Tạo bộ flashcard mới
          </CardTitle>
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
              <Select
                id="fc-count"
                value={numCards}
                onChange={(e) => setNumCards(Number(e.target.value))}
              >
                {[5, 10, 15, 20].map((n) => (
                  <option key={n} value={n}>
                    {n} thẻ
                  </option>
                ))}
              </Select>
            </div>
            <div className="w-40">
              <label htmlFor="fc-mode" className="mb-1.5 block text-sm font-medium text-foreground">
                Mục tiêu
              </label>
              <Select
                id="fc-mode"
                value={generationMode}
                onChange={(e) => setGenerationMode(e.target.value)}
              >
                <option value="">Tự động</option>
                {GENERATION_MODES.map((m) => (
                  <option key={m.value} value={m.value}>
                    {m.label}
                  </option>
                ))}
              </Select>
            </div>
            <Button
              onClick={handleGenerate}
              disabled={!documentId}
              loading={generating}
              className="shrink-0"
            >
              <Sparkles className="h-4 w-4" aria-hidden="true" />
              {generating ? "Đang sinh thẻ..." : "Tạo thẻ"}
            </Button>
          </div>
          {error && <p className="mt-3 text-sm text-destructive">{error}</p>}
        </CardContent>
      </Card>

      {partialNotice && (
        <p className="rounded-lg border border-warning/40 bg-warning/10 px-4 py-2.5 text-sm text-warning">
          {partialNotice}
        </p>
      )}

      {board && (
        <div className="flex flex-wrap gap-3">
          {BOARD_BUCKETS.map((b) => (
            <div
              key={b.key}
              className="flex min-w-32 flex-1 flex-col items-center gap-1 rounded-lg border border-border bg-muted/30 px-4 py-3"
            >
              <span className="text-2xl font-semibold text-foreground">{board[b.key].count}</span>
              <span className="text-xs text-muted-foreground">{b.label}</span>
            </div>
          ))}
        </div>
      )}

      {dueLoading ? (
        <p className="text-sm text-muted-foreground">Đang tải thẻ đến hạn…</p>
      ) : !card ? (
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
            <div
              role="button"
              tabIndex={0}
              aria-pressed={flipped}
              aria-label="Bấm để lật thẻ"
              onClick={() => setFlipped((f) => !f)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  setFlipped((f) => !f);
                }
              }}
              className={`flip-card cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${flipped ? "flip-card--flipped" : ""}`}
            >
              <div className="flip-card__inner">
                <div className="flip-card__face">
                  <p className="text-base font-medium text-foreground">{card.front}</p>
                  <p className="mt-4 text-xs text-muted-foreground">Bấm vào thẻ để lật</p>
                </div>
                <div className="flip-card__face flip-card__face--back">
                  <p className="text-sm leading-relaxed text-foreground">{card.back}</p>
                  {card.source_document && (
                    <p className="mt-3 text-xs text-muted-foreground">
                      Nguồn: {card.source_document} — {card.source_position}
                    </p>
                  )}
                </div>
              </div>
            </div>

            {flipped && (
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
                Thẻ trước: sẽ gặp lại sau {lastResult.interval_days} ngày.
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {mistakes.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base font-semibold text-foreground">Thẻ bạn hay quên</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="flex flex-col gap-3">
              {mistakes.map((m) => (
                <li key={m.id} className="border-l-2 border-destructive/40 pl-3">
                  <p className="text-sm font-medium text-foreground">{m.front}</p>
                  <p className="mt-0.5 text-xs text-muted-foreground">{m.back}</p>
                  <button
                    type="button"
                    onClick={() => toggleHistory(m.id)}
                    className="mt-1.5 flex items-center gap-1.5 text-xs font-medium text-muted-foreground transition-colors hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    <History className="h-3.5 w-3.5" aria-hidden="true" />
                    {expandedMistakeId === m.id ? "Ẩn lịch sử ôn" : "Xem lịch sử ôn"}
                  </button>
                  {expandedMistakeId === m.id && (
                    <ul className="mt-2 flex flex-wrap gap-1.5">
                      {(historyByItem[m.id] || []).map((h, i) => (
                        <li
                          key={i}
                          className="rounded-md border border-border px-2 py-0.5 text-xs text-muted-foreground"
                        >
                          {RATING_LABEL[h.rating] || h.rating}
                        </li>
                      ))}
                    </ul>
                  )}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
