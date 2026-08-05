import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { formatDateTime, scoreStatus } from "@/lib/utils";
import type { ScoreHistoryEntry } from "@/lib/types";

export function ScoreBreakdown({ latest }: { latest: ScoreHistoryEntry | null }) {
  if (!latest) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Score breakdown</CardTitle>
        </CardHeader>
        <CardContent className="text-sm" style={{ color: "var(--text-muted)" }}>
          Not scored yet.
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Score breakdown</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-center gap-3">
          <div className="text-4xl font-semibold" style={{ color: "var(--text-primary)" }}>
            {latest.base_score.toFixed(1)}
          </div>
          <span style={{ color: "var(--text-muted)" }}>−</span>
          <div className="text-4xl font-semibold" style={{ color: "var(--status-critical)" }}>
            {latest.deductions_total.toFixed(0)}
          </div>
          <span style={{ color: "var(--text-muted)" }}>=</span>
          <Badge role={scoreStatus(latest.final_score)} className="!text-2xl !px-3 !py-1 font-semibold">
            {latest.final_score}
          </Badge>
        </div>
        <div className="mt-2 flex justify-between text-xs" style={{ color: "var(--text-muted)" }}>
          <span>base score (weighted dimensions)</span>
          <span>deductions</span>
          <span>final</span>
        </div>
        <div className="mt-3 text-xs" style={{ color: "var(--text-muted)" }}>
          version {latest.version} · trigger: {latest.trigger} · computed {formatDateTime(latest.computed_at)}
        </div>
      </CardContent>
    </Card>
  );
}
