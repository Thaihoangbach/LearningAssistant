import { cn } from "../../lib/cn";

export default function Select({ className, children, ...props }) {
  return (
    <select
      className={cn(
        "h-11 w-full rounded-lg border border-border bg-card px-3 text-sm text-foreground",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        className
      )}
      {...props}
    >
      {children}
    </select>
  );
}
