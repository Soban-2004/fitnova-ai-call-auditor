import Link from "next/link";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { formatTagLabel, scoreStatus } from "@/lib/utils";
import { EmptyState } from "./ScoreTrendChart";
import type { TeamDashboard } from "@/lib/types";

const TREND_ICON = { up: TrendingUp, down: TrendingDown, flat: Minus };
const TREND_COLOR = { up: "var(--delta-good)", down: "var(--status-critical)", flat: "var(--text-muted)" };

export function AdvisorLeaderboard({ advisors }: { advisors: TeamDashboard["advisor_leaderboard"] }) {
  return (
    <Card>
      <CardHeader className="flex-col items-start">
        <CardTitle>Advisor leaderboard</CardTitle>
        <CardDescription>Ranked by average score this period</CardDescription>
      </CardHeader>
      <CardContent>
        {advisors.length === 0 ? (
          <EmptyState message="No scored calls yet" />
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-xs uppercase" style={{ borderColor: "var(--border)", color: "var(--text-muted)" }}>
                <th className="pb-2 font-medium">#</th>
                <th className="pb-2 font-medium">Advisor</th>
                <th className="pb-2 font-medium">Avg score</th>
                <th className="pb-2 font-medium">Calls</th>
                <th className="pb-2 font-medium">Trend</th>
                <th className="pb-2 font-medium">Top issue</th>
              </tr>
            </thead>
            <tbody>
              {advisors.map((advisor, i) => {
                const TrendIcon = TREND_ICON[advisor.trend];
                return (
                  <tr key={advisor.advisor_id} className="border-b last:border-0" style={{ borderColor: "var(--gridline)" }}>
                    <td className="py-2.5" style={{ color: "var(--text-muted)" }}>
                      {i + 1}
                    </td>
                    <td className="py-2.5">
                      <Link
                        href={`/dashboard/advisor/${advisor.advisor_id}`}
                        className="font-medium hover:underline"
                        style={{ color: "var(--text-primary)" }}
                      >
                        {advisor.advisor_name}
                      </Link>
                    </td>
                    <td className="py-2.5">
                      <Badge role={scoreStatus(advisor.avg_score)}>{advisor.avg_score ?? "—"}</Badge>
                    </td>
                    <td className="py-2.5" style={{ color: "var(--text-secondary)" }}>
                      {advisor.call_count}
                    </td>
                    <td className="py-2.5">
                      <TrendIcon size={16} style={{ color: TREND_COLOR[advisor.trend] }} />
                    </td>
                    <td className="py-2.5" style={{ color: "var(--text-secondary)" }}>
                      {advisor.top_issue ? formatTagLabel(advisor.top_issue) : "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </CardContent>
    </Card>
  );
}
