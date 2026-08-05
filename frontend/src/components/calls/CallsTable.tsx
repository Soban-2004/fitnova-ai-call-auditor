import Link from "next/link";
import { Card, CardContent } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/dashboard/ScoreTrendChart";
import { callStatusRole, formatDateTime, formatDuration, scoreStatus } from "@/lib/utils";
import type { CallListItem } from "@/lib/types";

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
                  className="border-b text-left text-xs uppercase"
                  style={{ borderColor: "var(--border)", color: "var(--text-muted)" }}
                >
                  <th className="pb-2 pr-3 font-medium">Called at</th>
                  <th className="pb-2 pr-3 font-medium">Advisor</th>
                  <th className="pb-2 pr-3 font-medium">Team</th>
                  <th className="pb-2 pr-3 font-medium">Status</th>
                  <th className="pb-2 pr-3 font-medium">Type</th>
                  <th className="pb-2 pr-3 font-medium">Duration</th>
                  <th className="pb-2 pr-3 font-medium">Score</th>
                  <th className="pb-2 font-medium">Issues</th>
                </tr>
              </thead>
              <tbody>
                {calls.map((call) => (
                  <tr key={call.id} className="border-b last:border-0" style={{ borderColor: "var(--gridline)" }}>
                    <td className="py-2.5 pr-3">
                      <Link
                        href={`/call/${call.id}`}
                        className="font-medium hover:underline"
                        style={{ color: "var(--text-primary)" }}
                      >
                        {formatDateTime(call.called_at)}
                      </Link>
                    </td>
                    <td className="py-2.5 pr-3" style={{ color: "var(--text-secondary)" }}>
                      {call.advisor_name}
                    </td>
                    <td className="py-2.5 pr-3" style={{ color: "var(--text-muted)" }}>
                      {call.team_name}
                    </td>
                    <td className="py-2.5 pr-3">
                      <Badge role={callStatusRole(call.status)}>{call.status}</Badge>
                    </td>
                    <td className="py-2.5 pr-3" style={{ color: "var(--text-muted)" }}>
                      {call.call_type ?? "—"}
                    </td>
                    <td className="py-2.5 pr-3" style={{ color: "var(--text-secondary)" }}>
                      {formatDuration(call.duration_secs)}
                    </td>
                    <td className="py-2.5 pr-3">
                      <Badge role={scoreStatus(call.latest_score)}>{call.latest_score ?? "—"}</Badge>
                    </td>
                    <td className="py-2.5" style={{ color: "var(--text-secondary)" }}>
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
