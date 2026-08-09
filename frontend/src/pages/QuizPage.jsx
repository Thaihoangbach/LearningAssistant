import { useEffect, useState } from "react";
import { Check, ListChecks, Sparkles, X } from "lucide-react";
import { listDocuments, generateQuiz, submitAttempt } from "../api";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/Card";
import Button from "../components/ui/Button";
import Input from "../components/ui/Input";
import Select from "../components/ui/Select";
import EmptyState from "../components/ui/EmptyState";
import { cn } from "../lib/cn";

export default function QuizPage() {
  const [documents, setDocuments] = useState([]);
  const [documentId, setDocumentId] = useState("");
  const [topicName, setTopicName] = useState("");
  const [quizItems, setQuizItems] = useState([]);
  const [results, setResults] = useState({}); // quiz_item_id -> {is_correct, correct_answer, explanation}
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    listDocuments().then((docs) => setDocuments(docs.filter((d) => d.status === "sẵn sàng")));
  }, []);

  const handleGenerate = async () => {
    if (!documentId) return;
    setLoading(true);
    setError(null);
    setResults({});
    try {
      const res = await generateQuiz(documentId, topicName, 5);
      setQuizItems(res.items);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const handleAnswer = async (quizItemId, option) => {
    if (results[quizItemId]) return; // đã trả lời rồi, không cho đổi
    try {
      const res = await submitAttempt(quizItemId, option);
      setResults((r) => ({ ...r, [quizItemId]: { ...res, selected: option } }));
    } catch (e) {
      setError(e.message);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-base font-semibold text-foreground">Tạo quiz mới</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <div className="flex-1">
              <label htmlFor="quiz-doc" className="mb-1.5 block text-sm font-medium text-foreground">
                Tài liệu
              </label>
              <Select id="quiz-doc" value={documentId} onChange={(e) => setDocumentId(e.target.value)}>
                <option value="">-- Chọn tài liệu --</option>
                {documents.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.course_name ? `${d.course_name} — ${d.file_name}` : d.file_name}
                  </option>
                ))}
              </Select>
            </div>
            <div className="flex-1">
              <label htmlFor="quiz-topic" className="mb-1.5 block text-sm font-medium text-foreground">
                Chủ đề (tuỳ chọn, để theo dõi tiến độ)
              </label>
              <Input
                id="quiz-topic"
                placeholder="VD: Chuẩn hoá dữ liệu"
                value={topicName}
                onChange={(e) => setTopicName(e.target.value)}
              />
            </div>
            <Button onClick={handleGenerate} disabled={!documentId} loading={loading} className="shrink-0">
              <Sparkles className="h-4 w-4" aria-hidden="true" />
              {loading ? "Đang sinh câu hỏi..." : "Tạo quiz"}
            </Button>
          </div>
          {error && <p className="mt-3 text-sm text-destructive">{error}</p>}
        </CardContent>
      </Card>

      {quizItems.length === 0 ? (
        <EmptyState
          icon={ListChecks}
          title="Chưa có quiz nào"
          description="Chọn tài liệu đã sẵn sàng ở trên và bấm Tạo quiz để bắt đầu tự kiểm tra."
        />
      ) : (
        <div className="flex flex-col gap-4">
          {quizItems.map((item, i) => {
            const result = results[item.id];
            return (
              <Card key={item.id}>
                <CardContent className="flex flex-col gap-3 pt-5">
                  <p className="font-semibold text-foreground">
                    Câu {i + 1}: {item.question}
                  </p>
                  <div className="flex flex-col gap-2">
                    {item.options.map((opt) => {
                      const isCorrectOption = result && opt === result.correct_answer;
                      const isWrongSelected = result && opt === result.selected && !result.is_correct;
                      return (
                        <button
                          key={opt}
                          type="button"
                          onClick={() => handleAnswer(item.id, opt)}
                          disabled={!!result}
                          className={cn(
                            "flex min-h-11 items-center justify-between gap-2 rounded-lg border px-4 py-2.5 text-left text-sm transition-colors duration-150",
                            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                            !result && "cursor-pointer border-border hover:bg-muted",
                            result && !isCorrectOption && !isWrongSelected && "cursor-default border-border opacity-60",
                            isCorrectOption && "cursor-default border-success bg-success/10 text-success",
                            isWrongSelected && "cursor-default border-destructive bg-destructive/10 text-destructive"
                          )}
                        >
                          {opt}
                          {isCorrectOption && <Check className="h-4 w-4 shrink-0" aria-hidden="true" />}
                          {isWrongSelected && <X className="h-4 w-4 shrink-0" aria-hidden="true" />}
                        </button>
                      );
                    })}
                  </div>
                  {result && (
                    <p className={cn("text-sm", result.is_correct ? "text-success" : "text-destructive")}>
                      {result.is_correct ? "Đúng!" : `Sai — đáp án đúng: ${result.correct_answer}`} — {result.explanation}
                    </p>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
