import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { formatDateTime, scoreStatus } from "@/lib/utils";
import type { ScoreHistoryEntry } from "@/lib/types";

export function ScoreHistory({ history }: { history: ScoreHistoryEntry[] }) {
  if (history.length <= 1) return null; // nothing to show until a dismiss creates version 2+

  // history arrives newest-first from the API; show oldest-first as a timeline
  const chronological = [...history].reverse();

  return (
    <Card>
      <CardHeader>
        <CardTitle>Score history</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {chronological.map((entry, i) => (
          <div key={entry.version} className="flex items-center gap-3">
            <div className="flex flex-col items-center">
              <div
                className="h-2.5 w-2.5 rounded-full"
                style={{ backgroundColor: i === chronological.length - 1 ? "var(--series-1)" : "var(--text-muted)" }}
              />
              {i < chronological.length - 1 && <div className="mt-0.5 h-8 w-px" style={{ backgroundColor: "var(--gridline)" }} />}
            </div>
            <div className="flex-1 pb-1">
              <div className="flex items-center gap-2">
                <span className="text-xs font-medium" style={{ color: "var(--text-primary)" }}>
                  v{entry.version}
                </span>
                <Badge role={scoreStatus(entry.final_score)}>{entry.final_score}</Badge>
                <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                  {entry.trigger}
                </span>
              </div>
              <div className="text-[11px]" style={{ color: "var(--text-muted)" }}>
                {formatDateTime(entry.computed_at)}
                {entry.changed_by && ` · ${entry.changed_by}`}
              </div>
              {entry.reason && (
                <div className="mt-0.5 text-xs italic" style={{ color: "var(--text-secondary)" }}>
                  &ldquo;{entry.reason}&rdquo;
                </div>
              )}
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
