import { cn, statusColorVar, type StatusRole } from "@/lib/utils";
import type { HTMLAttributes } from "react";

export function Badge({
  role = "muted",
  dot = false,
  className,
  style,
  children,
  ...props
}: HTMLAttributes<HTMLSpanElement> & { role?: StatusRole; dot?: boolean }) {
  const color = statusColorVar(role);
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium",
        className
      )}
      style={{
        color,
        backgroundColor: `color-mix(in srgb, ${color} 14%, transparent)`,
        ...style,
      }}
      {...props}
    >
      {dot && <span className="h-1.5 w-1.5 shrink-0 rounded-full" style={{ backgroundColor: color }} />}
      {children}
    </span>
  );
}
