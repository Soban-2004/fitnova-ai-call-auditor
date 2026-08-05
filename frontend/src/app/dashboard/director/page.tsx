import { AlertTriangle, Building2, PhoneCall, TrendingUp } from "lucide-react";
import { StatsCard } from "@/components/dashboard/StatsCard";
import { ScoreTrendSection } from "@/components/dashboard/ScoreTrendSection";
import { ScoreDistribution } from "@/components/dashboard/ScoreDistribution";
import { TopIssuesChart } from "@/components/dashboard/TopIssuesChart";
import { TeamComparisonTable } from "@/components/dashboard/TeamComparisonTable";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { api, ApiError } from "@/lib/api";
import { scoreStatus } from "@/lib/utils";

export const dynamic = "force-dynamic";

export default async function DirectorDashboardPage() {
  let data;
  try {
    data = await api.directorDashboard();
  } catch (e) {
    return <ApiUnreachable error={e} />;
  }

  return (
    <div className="p-6 lg:p-8">
      <header className="mb-6">
        <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>
          {data.org_name} — Org Overview
        </h1>
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>
          Sales Director view — health of the whole organization
        </p>
      </header>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatsCard label="Total calls" value={data.summary.total_calls} icon={<PhoneCall size={16} />} />
        <StatsCard
          label="Org average score"
          value={data.summary.avg_score ?? "—"}
          statusRole={scoreStatus(data.summary.avg_score)}
          icon={<TrendingUp size={16} />}
        />
        <StatsCard label="Calls this week" value={data.summary.calls_this_week} icon={<Building2 size={16} />} />
        <StatsCard
          label="Needs attention"
          value={data.attention_needed.failed_calls + data.attention_needed.needs_review_tags}
          sub={`${data.attention_needed.failed_calls} failed · ${data.attention_needed.needs_review_tags} needs review`}
          statusRole={data.attention_needed.failed_calls + data.attention_needed.needs_review_tags > 0 ? "warning" : "good"}
          icon={<AlertTriangle size={16} />}
        />
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <ScoreTrendSection scope="org" initialData={data.summary.score_trend} description="Org-wide weekly average" />
        <ScoreDistribution data={data.score_distribution} />
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <TopIssuesChart data={data.top_issues} description="Most frequent open flags across the org" />
        <TeamComparisonTable teams={data.team_comparison} />
      </div>
    </div>
  );
}

function ApiUnreachable({ error }: { error: unknown }) {
  const message = error instanceof ApiError ? error.message : "Could not reach the FitNova API.";
  return (
    <div className="flex min-h-screen items-center justify-center p-8">
      <Card className="max-w-md">
        <CardHeader>
          <CardTitle>Backend unreachable</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            {message}
          </p>
          <p className="mt-2 text-xs" style={{ color: "var(--text-muted)" }}>
            Make sure the backend is running (uvicorn app.main:app) and NEXT_PUBLIC_API_URL points at it.
          </p>
          <div className="mt-3">
            <Badge role="critical">offline</Badge>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
