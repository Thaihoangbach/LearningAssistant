import { ExternalLink, X } from "lucide-react";
import { documentFileUrl } from "../api";

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
        className="fixed inset-y-0 right-0 z-50 flex w-full max-w-md flex-col border-l border-border bg-card shadow-xl"
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
