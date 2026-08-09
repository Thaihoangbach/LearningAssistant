import { CheckCircle2, Loader2, XCircle } from "lucide-react";
import Badge from "./ui/Badge";

const CONFIG = {
  "sẵn sàng": { variant: "success", icon: CheckCircle2 },
  "lỗi": { variant: "destructive", icon: XCircle },
  "đang xử lý": { variant: "warning", icon: Loader2 },
};

export default function StatusBadge({ status, reason }) {
  const { variant, icon: Icon } = CONFIG[status] || CONFIG["đang xử lý"];
  return (
    <Badge variant={variant}>
      <Icon className={`h-3.5 w-3.5 ${status === "đang xử lý" ? "animate-spin" : ""}`} aria-hidden="true" />
      {status}
      {status === "lỗi" && reason ? ` — ${reason}` : ""}
    </Badge>
  );
}
