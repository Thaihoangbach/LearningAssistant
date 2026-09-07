import { CheckCircle2, Loader2, XCircle } from "lucide-react";
import Badge from "./ui/Badge";
import { DOCUMENT_STATUS } from "../lib/constants";

const CONFIG = {
  [DOCUMENT_STATUS.READY]: { variant: "success", icon: CheckCircle2 },
  [DOCUMENT_STATUS.ERROR]: { variant: "destructive", icon: XCircle },
  [DOCUMENT_STATUS.PROCESSING]: { variant: "warning", icon: Loader2 },
};

export default function StatusBadge({ status, reason }) {
  const { variant, icon: Icon } = CONFIG[status] || CONFIG[DOCUMENT_STATUS.PROCESSING];
  return (
    <Badge variant={variant}>
      <Icon className={`h-3.5 w-3.5 ${status === DOCUMENT_STATUS.PROCESSING ? "animate-spin" : ""}`} aria-hidden="true" />
      {status}
      {status === DOCUMENT_STATUS.ERROR && reason ? ` — ${reason}` : ""}
    </Badge>
  );
}
