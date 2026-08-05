import { Card, CardContent } from "@/components/ui/Card";
import { cn, statusColorVar } from "@/lib/utils";
import type { ReactNode } from "react";

export function StatsCard({
  label,
  value,
  sub,
  statusRole,
  icon,
}: {
  label: string;
  value: string | number;
  sub?: string;
  statusRole?: "good" | "warning" | "critical" | "muted";
  icon?: ReactNode;
}) {
  return (
    <Card>
      <CardContent className="pt-4">
        <div className="flex items-start justify-between">
          <span className="text-xs font-medium" style={{ color: "var(--text-muted)" }}>
            {label}
          </span>
          {icon && (
            <span style={{ color: "var(--text-muted)" }}>{icon}</span>
          )}
        </div>
        <div
          className={cn("mt-1 text-3xl font-semibold")}
          style={{ color: statusRole ? statusColorVar(statusRole) : "var(--text-primary)" }}
        >
          {value}
        </div>
        {sub && (
          <div className="mt-1 text-xs" style={{ color: "var(--text-secondary)" }}>
            {sub}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
