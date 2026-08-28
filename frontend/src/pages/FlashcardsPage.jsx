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
    listDocuments()
      .then((docs) => setDocuments(docs.filter((d) => d.status === "sẵn sàng")))
      .catch((e) => setError(e.message));
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
      // "Quên rồi" đặt hạn về 0 nên thẻ VẪN còn đến hạn — nạp lại danh sách để
      // nó quay lại hàng đợi thay vì biến mất khỏi phiên ôn.
      if (rating === "again" || current + 1 >= due.length) {
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
                Thẻ trước: sẽ gặp lại sau {lastResult.interval_days} ngày.
              </p>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
