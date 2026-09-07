import { SearchX } from "lucide-react";

export default function SearchReport({ report, onOpenNearMiss, onAskTopic }) {
  if (!report) return null;

  const nearMisses = report.near_misses || [];
  const suggested = report.suggested_topics || [];
  if (nearMisses.length === 0 && suggested.length === 0) return null;

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
      {suggested.length > 0 && (
        <div className="mt-3">
          <p className="text-xs font-medium text-foreground">
            Tài liệu của bạn có nói về những phần này — có thể bạn muốn hỏi:
          </p>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {suggested.map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => onAskTopic(t)}
                className="cursor-pointer rounded-full border border-primary/40 bg-primary/10 px-3 py-1 text-xs font-medium text-primary transition-colors hover:bg-primary/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                {t}
              </button>
            ))}
          </div>
        </div>
      )}

      <ul className="mt-2 flex flex-col gap-1.5">
        {nearMisses.map((n) => (
          <li key={n.chunk_id || `${n.document_name}-${n.position_ref}`}>
            <button
              type="button"
              onClick={() => onOpenNearMiss(n)}
              className="w-full cursor-pointer rounded-md border border-border bg-card px-3 py-2 text-left text-xs transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <span className="font-medium text-foreground">
                {n.document_name} — {n.position_ref}
              </span>
              <span className="ml-2 text-muted-foreground">
                (độ liên quan {n.score.toFixed(2)})
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
