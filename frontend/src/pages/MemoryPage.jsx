import { useEffect, useState } from "react";
import { Brain, Trash2 } from "lucide-react";
import { deleteMemory, listMemory } from "../api";
import { Card, CardContent } from "../components/ui/Card";
import Badge from "../components/ui/Badge";
import EmptyState from "../components/ui/EmptyState";

// Khớp app/memory/scoring.py::IMPORTANCE_BY_EVENT_TYPE. Màu phản ánh ý nghĩa:
// sự kiện cho thấy chỗ hổng dùng màu cảnh báo/lỗi, sự kiện tốt dùng màu thành công.
const EVENT_LABELS = {
  quiz_wrong: { label: "Làm sai quiz", variant: "destructive" },
  quiz_right: { label: "Làm đúng quiz", variant: "success" },
  flashcard_again: { label: "Quên flashcard", variant: "warning" },
  flashcard_easy: { label: "Thấy thẻ quá dễ", variant: "success" },
  concept_confused: { label: "Chưa hiểu khái niệm", variant: "warning" },
  abstention: { label: "Hỏi điều không có trong tài liệu", variant: "muted" },
  question_asked: { label: "Đã hỏi", variant: "default" },
};

function formatDate(isoString) {
  if (!isoString) return "";
  return new Date(isoString).toLocaleString("vi-VN", { dateStyle: "short", timeStyle: "short" });
}

export default function MemoryPage() {
  const [events, setEvents] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listMemory()
      .then((res) => setEvents(res.events))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const handleDelete = async (id) => {
    try {
      await deleteMemory(id);
      // Lọc khỏi state thay vì nạp lại toàn bộ danh sách — kết quả như nhau,
      // đỡ một vòng gọi mạng.
      setEvents((list) => list.filter((e) => e.id !== id));
    } catch (e) {
      setError(e.message);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardContent className="pt-5">
          <p className="text-sm text-foreground">
            Đây là những gì hệ thống ghi nhớ về quá trình học của bạn. Các mục này được đưa vào
            câu trả lời để cá nhân hoá theo đúng chỗ bạn từng vướng.
          </p>
          <p className="mt-1.5 text-xs text-muted-foreground">
            Xoá một mục thì nó không còn ảnh hưởng tới các câu trả lời sau nữa.
          </p>
        </CardContent>
      </Card>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {!loading && events.length === 0 ? (
        <EmptyState
          icon={Brain}
          title="Chưa có ký ức nào"
          description="Hệ thống sẽ ghi nhớ khi bạn hỏi đáp, làm quiz hoặc ôn flashcard."
        />
      ) : (
        <div className="flex flex-col gap-3">
          {events.map((e) => {
            const meta = EVENT_LABELS[e.event_type] || { label: e.event_type, variant: "muted" };
            return (
              <Card key={e.id}>
                <CardContent className="flex items-start justify-between gap-4 pt-5">
                  <div className="min-w-0 flex-1">
                    <div className="mb-2 flex flex-wrap items-center gap-2">
                      <Badge variant={meta.variant}>{meta.label}</Badge>
                      {e.topic_name && <Badge variant="muted">{e.topic_name}</Badge>}
                    </div>
                    <p className="text-sm text-foreground">{e.content}</p>
                    <p className="mt-1.5 text-xs text-muted-foreground">
                      {formatDate(e.created_at)} · mức quan trọng {e.importance.toFixed(1)} · đã
                      được nhắc lại {e.access_count} lần
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleDelete(e.id)}
                    className="shrink-0 cursor-pointer rounded-md p-2 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    aria-label="Xoá ký ức này"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
