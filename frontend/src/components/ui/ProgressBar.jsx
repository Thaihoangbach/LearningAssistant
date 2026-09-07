import { cn } from "../../lib/cn";
import { MASTERY_LEVEL } from "../../lib/constants";

const LEVEL_COLOR = {
  [MASTERY_LEVEL.GOOD]: "bg-success",
  [MASTERY_LEVEL.MEDIUM]: "bg-warning",
  [MASTERY_LEVEL.WEAK]: "bg-destructive",
};

export default function ProgressBar({ value, level, className }) {
  const pct = Math.round(Math.max(0, Math.min(1, value)) * 100);
  return (
    <div
      className={cn("h-2 w-full overflow-hidden rounded-full bg-muted", className)}
      role="progressbar"
      aria-valuenow={pct}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <div
        className={cn(
          "h-full rounded-full transition-[width] duration-300 ease-out",
          LEVEL_COLOR[level] || "bg-primary"
        )}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}
