import Link from "next/link";
import { Card, CardContent } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { MiniBar } from "@/components/ui/MiniBar";
import { EmptyState } from "@/components/dashboard/ScoreTrendChart";
import { callStatusRole, categoryColorVar, cn, formatDateTime, formatDuration, initials, scoreStatus } from "@/lib/utils";
import type { CallListItem } from "@/lib/types";

const rowHoverClass = "transition-colors hover:bg-[color-mix(in_srgb,var(--series-1)_5%,transparent)]";

export function CallsTable({ calls }: { calls: CallListItem[] }) {
  return (
    <Card>
      <CardContent className="pt-4">
        {calls.length === 0 ? (
          <EmptyState message="No calls match these filters" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr
                  className="sticky top-0 z-10 border-b text-left text-xs uppercase"
                  style={{ borderColor: "var(--border)", color: "var(--text-muted)", backgroundColor: "var(--surface-1)" }}
                >
                  <th className="pb-2 pr-3 font-medium">Called at</th>
                  <th className="pb-2 pr-3 font-medium">Advisor</th>
                  <th className="pb-2 pr-3 font-medium">Team</th>
                  <th className="pb-2 pr-3 font-medium">Status</th>
                  <th className="pb-2 pr-3 font-medium">Type</th>
                  <th className="pb-2 pr-3 text-right font-medium">Duration</th>
                  <th className="pb-2 pr-3 text-right font-medium">Score</th>
                  <th className="pb-2 text-right font-medium">Issues</th>
                </tr>
              </thead>
              <tbody>
                {calls.map((call) => (
                  <tr
                    key={call.id}
                    className={cn("border-b last:border-0", rowHoverClass)}
                    style={{ borderColor: "var(--gridline)" }}
                  >
                    <td className="py-2.5 pr-3">
                      <Link
                        href={`/call/${call.id}`}
                        className="font-medium hover:underline"
                        style={{ color: "var(--text-primary)" }}
                      >
                        {formatDateTime(call.called_at)}
                      </Link>
                    </td>
                    <td className="py-2.5 pr-3">
                      <div className="flex items-center gap-2">
                        <span
                          className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[10px] font-semibold"
                          style={{
                            backgroundColor: `color-mix(in srgb, ${categoryColorVar(call.advisor_id)} 18%, transparent)`,
                            color: categoryColorVar(call.advisor_id),
                          }}
                        >
                          {initials(call.advisor_name)}
                        </span>
                        <span style={{ color: "var(--text-secondary)" }}>{call.advisor_name}</span>
                      </div>
                    </td>
                    <td className="py-2.5 pr-3">
                      <span className="flex items-center gap-1.5" style={{ color: "var(--text-muted)" }}>
                        <span
                          className="h-1.5 w-1.5 shrink-0 rounded-full"
                          style={{ backgroundColor: categoryColorVar(call.team_name) }}
                        />
                        {call.team_name}
                      </span>
                    </td>
                    <td className="py-2.5 pr-3">
                      <Badge role={callStatusRole(call.status)} dot>
                        {call.status}
                      </Badge>
                    </td>
                    <td className="py-2.5 pr-3" style={{ color: "var(--text-muted)" }}>
                      {call.call_type ?? "—"}
                    </td>
                    <td className="py-2.5 pr-3 text-right tabular-nums" style={{ color: "var(--text-secondary)" }}>
                      {formatDuration(call.duration_secs)}
                    </td>
                    <td className="py-2.5 pr-3">
                      <div className="flex items-center justify-end gap-2">
                        {call.latest_score !== null && <MiniBar value={call.latest_score} role={scoreStatus(call.latest_score)} />}
                        <Badge role={scoreStatus(call.latest_score)} className="tabular-nums">
                          {call.latest_score ?? "—"}
                        </Badge>
                      </div>
                    </td>
                    <td className="py-2.5 text-right tabular-nums" style={{ color: call.issue_count > 0 ? "var(--status-warning)" : "var(--text-muted)" }}>
                      {call.issue_count}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
