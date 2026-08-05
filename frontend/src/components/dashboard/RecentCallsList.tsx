import Link from "next/link";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { formatDate, formatDuration, scoreStatus } from "@/lib/utils";
import { EmptyState } from "./ScoreTrendChart";
import type { AdvisorDashboard } from "@/lib/types";

export function RecentCallsList({ calls }: { calls: AdvisorDashboard["recent_calls"] }) {
  return (
    <Card>
      <CardHeader className="flex-col items-start">
        <CardTitle>Recent calls</CardTitle>
        <CardDescription>Click a call to see the full transcript and breakdown</CardDescription>
      </CardHeader>
      <CardContent>
        {calls.length === 0 ? (
          <EmptyState message="No calls yet" />
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-xs uppercase" style={{ borderColor: "var(--border)", color: "var(--text-muted)" }}>
                <th className="pb-2 font-medium">Date</th>
                <th className="pb-2 font-medium">Duration</th>
                <th className="pb-2 font-medium">Score</th>
                <th className="pb-2 font-medium">Issues</th>
                <th className="pb-2 font-medium">Type</th>
              </tr>
            </thead>
            <tbody>
              {calls.map((call) => (
                <tr key={call.call_id} className="border-b last:border-0" style={{ borderColor: "var(--gridline)" }}>
                  <td className="py-2.5">
                    <Link href={`/call/${call.call_id}`} className="font-medium hover:underline" style={{ color: "var(--text-primary)" }}>
                      {formatDate(call.called_at)}
                    </Link>
                  </td>
                  <td className="py-2.5" style={{ color: "var(--text-secondary)" }}>
                    {formatDuration(call.duration_secs)}
                  </td>
                  <td className="py-2.5">
                    <Badge role={scoreStatus(call.score)}>{call.score ?? "—"}</Badge>
                  </td>
                  <td className="py-2.5" style={{ color: "var(--text-secondary)" }}>
                    {call.issue_count}
                  </td>
                  <td className="py-2.5" style={{ color: "var(--text-muted)" }}>
                    {call.call_type ?? "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </CardContent>
    </Card>
  );
}
