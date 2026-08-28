import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  CheckCircle2,
  FileText,
  Layers,
  ListChecks,
  MessageCircle,
  Minus,
  Target,
  TrendingDown,
  TrendingUp,
  Upload,
} from "lucide-react";
import { getMastery, getMistakes, listDocuments } from "../api";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/Card";
import Badge from "../components/ui/Badge";
import ProgressBar from "../components/ui/ProgressBar";
import EmptyState from "../components/ui/EmptyState";
import StatusBadge from "../components/StatusBadge";

const LEVEL_VARIANT = { "tốt": "success", "trung bình": "warning", "yếu": "destructive" };

function KpiCard({ icon: Icon, label, value, hint }) {
  return (
    <Card>
      <CardContent className="flex items-start justify-between gap-3 p-5">
        <div>
          <p className="text-sm font-medium text-muted-foreground">{label}</p>
          <p className="mt-1 text-3xl font-bold tracking-tight text-foreground">{value}</p>
          {hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
        </div>
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
          <Icon className="h-5 w-5" aria-hidden="true" />
        </div>
      </CardContent>
    </Card>
  );
}

function TrendLine({ summary }) {
  const { accuracy_recent: recent, accuracy_previous: previous, trend_window_days: days } = summary;

  if (recent == null) {
    return (
      <p className="text-sm text-muted-foreground">
        Chưa có lượt làm bài nào trong {days} ngày qua, nên chưa so sánh được tiến bộ.
      </p>
    );
  }
  if (previous == null) {
    return (
      <p className="text-sm text-foreground">
        {days} ngày qua bạn đúng {Math.round(recent * 100)}%. Cần thêm một tuần dữ liệu nữa mới
        so sánh được với trước đó.
      </p>
    );
  }

  const delta = recent - previous;
  const Icon = delta > 0.02 ? TrendingUp : delta < -0.02 ? TrendingDown : Minus;
  const tone =
    delta > 0.02 ? "text-success" : delta < -0.02 ? "text-destructive" : "text-muted-foreground";
  const verdict =
    delta > 0.02 ? "khá hơn tuần trước" : delta < -0.02 ? "kém hơn tuần trước" : "ngang tuần trước";

  return (
    <div className={`flex items-center gap-2 text-sm ${tone}`}>
      <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
      <span>
        {days} ngày qua đúng {Math.round(recent * 100)}%, {days} ngày trước đó{" "}
        {Math.round(previous * 100)}% — {verdict}.
      </span>
    </div>
  );
}

const QUICK_ACTIONS = [
  { to: "/documents", label: "Tải tài liệu", description: "Thêm slide, giáo trình mới", icon: Upload },
  { to: "/chat", label: "Hỏi đáp", description: "Hỏi về nội dung đã tải lên", icon: MessageCircle },
  { to: "/quiz", label: "Làm quiz", description: "Tự kiểm tra và cập nhật mastery", icon: ListChecks },
];

export default function DashboardPage() {
  const [mastery, setMastery] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [mistakes, setMistakes] = useState([]);

  useEffect(() => {
    Promise.all([getMastery(), listDocuments(), getMistakes(5)])
      .then(([masteryRes, docsRes, mistakesRes]) => {
        setMastery(masteryRes);
        setDocuments(docsRes);
        setMistakes(mistakesRes.mistakes);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <p className="text-sm text-muted-foreground">Đang tải tổng quan...</p>;
  }

  if (error) {
    return <p className="text-sm text-destructive">Lỗi tải dữ liệu: {error}</p>;
  }

  const { topics, summary } = mastery;
  const recentDocuments = [...documents]
    .sort((a, b) => new Date(b.uploaded_at) - new Date(a.uploaded_at))
    .slice(0, 5);
  const accuracyHint =
    summary.attempts_total > 0
      ? `${summary.attempts_correct}/${summary.attempts_total} câu đúng`
      : "Chưa có lượt làm bài";

  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard icon={FileText} label="Tài liệu sẵn sàng" value={summary.documents_ready} hint={`${summary.documents_processing} đang xử lý`} />
        <KpiCard
          icon={Target}
          label="Mastery trung bình"
          value={summary.avg_mastery == null ? "—" : `${Math.round(summary.avg_mastery * 100)}%`}
          hint={summary.avg_mastery == null ? "Chưa có dữ liệu" : `${topics.length} chủ đề`}
        />
        <KpiCard
          icon={Layers}
          label="Thẻ đến hạn ôn"
          value={summary.flashcards_due ?? 0}
          hint={summary.flashcards_due > 0 ? "Ôn đúng hạn để nhớ lâu" : "Đang theo kịp lịch"}
        />
        <KpiCard icon={CheckCircle2} label="Lượt làm bài" value={summary.attempts_total} hint={accuracyHint} />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Bạn có tiến bộ không?</CardTitle>
        </CardHeader>
        <CardContent>
          <TrendLine summary={summary} />
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {QUICK_ACTIONS.map(({ to, label, description, icon: Icon }) => (
          <Link
            key={to}
            to={to}
            className="group flex items-center gap-3 rounded-xl border border-border bg-card p-4 shadow-card transition-colors duration-150 hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <Icon className="h-5 w-5" aria-hidden="true" />
            </div>
            <div>
              <p className="font-semibold text-foreground">{label}</p>
              <p className="text-sm text-muted-foreground">{description}</p>
            </div>
          </Link>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-5">
        <Card className="lg:col-span-3">
          <CardHeader>
            <CardTitle>Mức độ thành thạo theo chủ đề</CardTitle>
          </CardHeader>
          <CardContent>
            {topics.length === 0 ? (
              <EmptyState
                icon={Target}
                title="Chưa có dữ liệu mastery"
                description="Làm quiz theo chủ đề để bắt đầu theo dõi tiến độ học tập."
                action={
                  <Link to="/quiz">
                    <span className="inline-flex h-11 items-center rounded-lg bg-primary px-4 text-sm font-semibold text-primary-foreground hover:bg-primary/90">
                      Làm quiz đầu tiên
                    </span>
                  </Link>
                }
              />
            ) : (
              <ul className="flex flex-col gap-4">
                {topics.map((t) => (
                  <li key={t.topic_id} className="flex flex-col gap-1.5">
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate text-sm font-medium text-foreground">
                        {t.topic_name}
                        {t.course_name && (
                          <span className="ml-2 text-xs font-normal text-muted-foreground">{t.course_name}</span>
                        )}
                      </span>
                      <div className="flex shrink-0 items-center gap-2">
                        <span className="text-sm font-semibold text-foreground">{Math.round(t.score * 100)}%</span>
                        <Badge variant={LEVEL_VARIANT[t.level]}>{t.level}</Badge>
                      </div>
                    </div>
                    <ProgressBar value={t.score} level={t.level} />
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Câu bạn từng làm sai</CardTitle>
          </CardHeader>
          <CardContent>
            {mistakes.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                {summary.attempts_total === 0
                  ? "Chưa làm quiz nào. Những câu trả lời sai sẽ được giữ lại ở đây để ôn lại."
                  : "Chưa có câu nào sai. Giữ phong độ nhé."}
              </p>
            ) : (
              <ul className="flex flex-col gap-3">
                {mistakes.map((m) => (
                  <li key={m.quiz_item_id} className="border-l-2 border-destructive/40 pl-3">
                    <p className="text-sm font-medium text-foreground">{m.question}</p>
                    <p className="mt-0.5 text-xs text-success">Đáp án đúng: {m.correct_answer}</p>
                    {m.source_document && (
                      <p className="mt-0.5 text-xs text-muted-foreground">
                        Nguồn: {m.source_document} — {m.source_position}
                      </p>
                    )}
                  </li>
                ))}
              </ul>
            )}
            {summary.mistakes_total > mistakes.length && (
              <p className="mt-3 text-xs text-muted-foreground">
                Còn {summary.mistakes_total - mistakes.length} câu sai khác.
              </p>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-4">
        <Card>
          <CardHeader>
            <CardTitle>Tài liệu gần đây</CardTitle>
          </CardHeader>
          <CardContent>
            {recentDocuments.length === 0 ? (
              <EmptyState
                icon={FileText}
                title="Chưa có tài liệu"
                description="Tải lên tài liệu PDF/DOCX đầu tiên để bắt đầu."
                action={
                  <Link to="/documents">
                    <span className="inline-flex h-11 items-center rounded-lg bg-primary px-4 text-sm font-semibold text-primary-foreground hover:bg-primary/90">
                      Tải tài liệu
                    </span>
                  </Link>
                }
              />
            ) : (
              <ul className="flex flex-col gap-3">
                {recentDocuments.map((d) => (
                  <li key={d.id} className="flex items-center justify-between gap-2">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-foreground">{d.course_name || d.file_name}</p>
                      {d.course_name && (
                        <p className="truncate text-xs text-muted-foreground">{d.file_name}</p>
                      )}
                    </div>
                    <StatusBadge status={d.status} reason={d.error_reason} />
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
