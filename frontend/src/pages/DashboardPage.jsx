import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  CheckCircle2,
  FileText,
  ListChecks,
  MessageCircle,
  Target,
  Upload,
} from "lucide-react";
import { getMastery, listDocuments } from "../api";
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

  useEffect(() => {
    Promise.all([getMastery(), listDocuments()])
      .then(([masteryRes, docsRes]) => {
        setMastery(masteryRes);
        setDocuments(docsRes);
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
        <KpiCard icon={ListChecks} label="Quiz đã tạo" value={summary.quizzes_taken} />
        <KpiCard icon={CheckCircle2} label="Lượt làm bài" value={summary.attempts_total} hint={accuracyHint} />
      </div>

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
                      <p className="truncate text-sm font-medium text-foreground">{d.file_name}</p>
                      <p className="truncate text-xs text-muted-foreground">{d.course_name || "Chưa gán môn"}</p>
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
