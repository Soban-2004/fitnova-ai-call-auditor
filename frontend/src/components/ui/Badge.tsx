import { cn } from "@/lib/utils";
import type { HTMLAttributes } from "react";

type StatusRole = "good" | "warning" | "critical" | "muted";

const ROLE_VAR: Record<StatusRole, string> = {
  good: "var(--status-good)",
  warning: "var(--status-warning)",
  critical: "var(--status-critical)",
  muted: "var(--text-muted)",
};

export function Badge({
  role = "muted",
  className,
  style,
  ...props
}: HTMLAttributes<HTMLSpanElement> & { role?: StatusRole }) {
  const color = ROLE_VAR[role];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium",
        className
      )}
      style={{
        color,
        backgroundColor: `color-mix(in srgb, ${color} 14%, transparent)`,
        ...style,
      }}
      {...props}
    />
  );
}
