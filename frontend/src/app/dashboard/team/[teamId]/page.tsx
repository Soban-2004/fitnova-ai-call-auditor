import { notFound } from "next/navigation";
import { Users2, TrendingUp } from "lucide-react";
import { StatsCard } from "@/components/dashboard/StatsCard";
import { ScoreTrendSection } from "@/components/dashboard/ScoreTrendSection";
import { AdvisorLeaderboard } from "@/components/dashboard/AdvisorLeaderboard";
import { FlaggedCallsQueue } from "@/components/dashboard/FlaggedCallsQueue";
import { ContestReviewQueue } from "@/components/dashboard/ContestReviewQueue";
import { TopIssuesChart } from "@/components/dashboard/TopIssuesChart";
import { api, ApiError } from "@/lib/api";
import { scoreStatus } from "@/lib/utils";

export const dynamic = "force-dynamic";

export default async function TeamDashboardPage({ params }: { params: Promise<{ teamId: string }> }) {
  const { teamId } = await params;
  let data;
  try {
    data = await api.teamDashboard(teamId);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }

  return (
    <div className="p-6 lg:p-8">
      <header className="mb-6">
        <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>
          {data.team_name}
        </h1>
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>
          Team Leader view — coach advisors and review contested flags
        </p>
      </header>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatsCard
          label="Team average score"
          value={data.summary.avg_score ?? "—"}
          statusRole={scoreStatus(data.summary.avg_score)}
          icon={<TrendingUp size={16} />}
        />
        <StatsCard label="Scored calls" value={data.summary.call_count} icon={<Users2 size={16} />} />
        <StatsCard
          label="Open contests"
          value={data.contest_queue.length}
          statusRole={data.contest_queue.length > 0 ? "warning" : "good"}
        />
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <ScoreTrendSection scope="team" id={teamId} initialData={data.summary.score_trend} description="Team weekly average" />
        <TopIssuesChart data={data.issue_distribution} title="Team issue heatmap" description="Where to focus coaching" />
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <FlaggedCallsQueue calls={data.flagged_calls} />
        <ContestReviewQueue items={data.contest_queue} />
      </div>

      <div className="mt-4">
        <AdvisorLeaderboard advisors={data.advisor_leaderboard} />
      </div>
    </div>
  );
}
