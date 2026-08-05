import Link from "next/link";
import { AlertTriangle } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { formatTagLabel } from "@/lib/utils";
import { EmptyState } from "./ScoreTrendChart";
import type { TeamDashboard } from "@/lib/types";

export function FlaggedCallsQueue({ calls }: { calls: TeamDashboard["flagged_calls"] }) {
  return (
    <Card>
      <CardHeader className="flex-col items-start">
        <CardTitle className="flex items-center gap-1.5">
          <AlertTriangle size={14} style={{ color: "var(--status-critical)" }} />
          Flagged calls
        </CardTitle>
        <CardDescription>Calls with at least one open critical tag</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-2">
        {calls.length === 0 ? (
          <EmptyState message="Nothing flagged — clean queue" />
        ) : (
          calls.slice(0, 8).map((call) => (
            <Link
              key={call.call_id}
              href={`/call/${call.call_id}`}
              className="flex items-center justify-between rounded-lg border px-3 py-2 transition-colors hover:opacity-90"
              style={{ borderColor: "var(--border)" }}
            >
              <div className="min-w-0">
                <div className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
                  {call.advisor_name}
                </div>
                <div className="flex flex-wrap gap-1 mt-1">
                  {call.critical_tags.slice(0, 3).map((tag, i) => (
                    <Badge key={i} role="critical">
                      {formatTagLabel(tag)}
                    </Badge>
                  ))}
                </div>
              </div>
              <div className="shrink-0 text-right">
                <Badge role="critical">{call.score ?? "—"}</Badge>
              </div>
            </Link>
          ))
        )}
      </CardContent>
    </Card>
  );
}
