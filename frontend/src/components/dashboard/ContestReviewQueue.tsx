import Link from "next/link";
import { Gavel } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { formatTagLabel, severityColorVar } from "@/lib/utils";
import { EmptyState } from "./ScoreTrendChart";
import type { TeamDashboard } from "@/lib/types";

/** Read-only list for now — Confirm/Dismiss actions + score recalculation
 * are wired in the contest workflow (call detail page), which is where a
 * Team Leader actually resolves each item. This card is the queue view. */
export function ContestReviewQueue({ items }: { items: TeamDashboard["contest_queue"] }) {
  return (
    <Card>
      <CardHeader className="flex-col items-start">
        <CardTitle className="flex items-center gap-1.5">
          <Gavel size={14} />
          Contest review queue
        </CardTitle>
        <CardDescription>Tags an advisor has disputed, awaiting your decision</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-2">
        {items.length === 0 ? (
          <EmptyState message="No open contests" />
        ) : (
          items.map((item) => (
            <Link
              key={item.tag_id}
              href={`/call/${item.call_id}`}
              className="block rounded-lg border px-3 py-2.5 hover:opacity-90"
              style={{ borderColor: "var(--border)" }}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Badge style={{ color: severityColorVar(item.severity) }}>{formatTagLabel(item.tag_type)}</Badge>
                  <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                    {item.advisor_name}
                  </span>
                </div>
              </div>
              <p className="mt-1.5 text-xs italic" style={{ color: "var(--text-secondary)" }}>
                &ldquo;{item.quote}&rdquo;
              </p>
              {item.contest_reason && (
                <p className="mt-1 text-xs" style={{ color: "var(--text-primary)" }}>
                  Advisor: {item.contest_reason}
                </p>
              )}
            </Link>
          ))
        )}
      </CardContent>
    </Card>
  );
}
