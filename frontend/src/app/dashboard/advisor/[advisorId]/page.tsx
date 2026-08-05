import { notFound } from "next/navigation";
import { Award, PhoneCall, TrendingDown, TrendingUp } from "lucide-react";
import { StatsCard } from "@/components/dashboard/StatsCard";
import { ScoreTrendSection } from "@/components/dashboard/ScoreTrendSection";
import { RecentCallsList } from "@/components/dashboard/RecentCallsList";
import { api, ApiError } from "@/lib/api";
import { scoreStatus } from "@/lib/utils";

export const dynamic = "force-dynamic";

export default async function AdvisorDashboardPage({ params }: { params: Promise<{ advisorId: string }> }) {
  const { advisorId } = await params;
  let data;
  try {
    data = await api.advisorDashboard(advisorId);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }

  return (
    <div className="p-6 lg:p-8">
      <header className="mb-6">
        <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>
          {data.advisor_name}
        </h1>
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>
          {data.team_name} · Your calls, scores, and where to improve
        </p>
      </header>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatsCard
          label="Average score"
          value={data.summary.avg_score ?? "—"}
          statusRole={scoreStatus(data.summary.avg_score)}
          icon={<TrendingUp size={16} />}
        />
        <StatsCard label="Calls scored" value={data.summary.call_count} icon={<PhoneCall size={16} />} />
        <StatsCard label="Personal best" value={data.summary.best_score ?? "—"} statusRole="good" icon={<Award size={16} />} />
        <StatsCard label="Toughest call" value={data.summary.worst_score ?? "—"} statusRole="critical" icon={<TrendingDown size={16} />} />
      </div>

      <div className="mt-4">
        <ScoreTrendSection scope="advisor" id={advisorId} initialData={data.summary.score_trend} description="Your weekly average score" />
      </div>

      <div className="mt-4">
        <RecentCallsList calls={data.recent_calls} />
      </div>
    </div>
  );
}
