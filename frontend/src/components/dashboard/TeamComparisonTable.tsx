import Link from "next/link";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { formatTagLabel, scoreStatus } from "@/lib/utils";
import { EmptyState } from "./ScoreTrendChart";
import type { DirectorDashboard } from "@/lib/types";

export function TeamComparisonTable({ teams }: { teams: DirectorDashboard["team_comparison"] }) {
  return (
    <Card>
      <CardHeader className="flex-col items-start">
        <CardTitle>Team comparison</CardTitle>
        <CardDescription>Average score and call volume by team</CardDescription>
      </CardHeader>
      <CardContent>
        {teams.length === 0 ? (
          <EmptyState />
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-xs uppercase" style={{ borderColor: "var(--border)", color: "var(--text-muted)" }}>
                <th className="pb-2 font-medium">Team</th>
                <th className="pb-2 font-medium">Avg score</th>
                <th className="pb-2 font-medium">Calls</th>
                <th className="pb-2 font-medium">Top issue</th>
              </tr>
            </thead>
            <tbody>
              {teams.map((team) => (
                <tr key={team.team_id} className="border-b last:border-0" style={{ borderColor: "var(--gridline)" }}>
                  <td className="py-2.5">
                    <Link href={`/dashboard/team/${team.team_id}`} className="font-medium hover:underline" style={{ color: "var(--text-primary)" }}>
                      {team.team_name}
                    </Link>
                  </td>
                  <td className="py-2.5">
                    <Badge role={scoreStatus(team.avg_score)}>{team.avg_score ?? "—"}</Badge>
                  </td>
                  <td className="py-2.5" style={{ color: "var(--text-secondary)" }}>
                    {team.call_count}
                  </td>
                  <td className="py-2.5" style={{ color: "var(--text-secondary)" }}>
                    {team.top_issue ? formatTagLabel(team.top_issue) : "—"}
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
