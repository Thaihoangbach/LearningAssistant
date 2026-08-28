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
