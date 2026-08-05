import { Card, CardContent } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { formatTagLabel } from "@/lib/utils";
import type { IssueTagOut } from "@/lib/types";

const STATUS_ROLE: Record<string, "good" | "warning" | "critical" | "muted"> = {
  open: "critical",
  needs_review: "warning",
  contested: "warning",
  confirmed: "critical",
  dismissed: "muted",
};

const SEVERITY_ROLE: Record<string, "good" | "warning" | "critical" | "muted"> = {
  critical: "critical",
  major: "warning",
  minor: "muted",
};

export function IssueTagCard({
  tag,
  onContest,
  onReview,
}: {
  tag: IssueTagOut;
  onContest?: (tag: IssueTagOut) => void;
  onReview?: (tag: IssueTagOut, action: "confirm" | "dismiss") => void;
}) {
  const isDismissed = tag.status === "dismissed";

  return (
    <Card className={isDismissed ? "opacity-60" : undefined}>
      <CardContent className="pt-4">
        <div className="flex items-start justify-between gap-2">
          <div className="flex flex-wrap items-center gap-1.5">
            <Badge role={SEVERITY_ROLE[tag.severity] ?? "muted"}>{tag.severity}</Badge>
            <span className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
              {formatTagLabel(tag.tag_type)}
            </span>
          </div>
          <Badge role={STATUS_ROLE[tag.status] ?? "muted"}>{tag.status.replace("_", " ")}</Badge>
        </div>

        <p className="mt-2 text-sm italic" style={{ color: "var(--text-secondary)" }}>
          &ldquo;{tag.quote}&rdquo;
        </p>
        {tag.reason && (
          <p className="mt-1.5 text-xs" style={{ color: "var(--text-muted)" }}>
            {tag.reason}
          </p>
        )}

        {tag.contest_reason && (
          <div className="mt-2 rounded-lg px-2.5 py-1.5 text-xs" style={{ backgroundColor: "var(--page)", color: "var(--text-secondary)" }}>
            <span className="font-medium" style={{ color: "var(--text-primary)" }}>
              Advisor&apos;s contest:
            </span>{" "}
            {tag.contest_reason}
          </div>
        )}
        {tag.review_comment && (
          <div className="mt-2 rounded-lg px-2.5 py-1.5 text-xs" style={{ backgroundColor: "var(--page)", color: "var(--text-secondary)" }}>
            <span className="font-medium" style={{ color: "var(--text-primary)" }}>
              Team Leader:
            </span>{" "}
            {tag.review_comment}
          </div>
        )}

        <div className="mt-3 flex items-center justify-between">
          <span className="text-[11px]" style={{ color: "var(--text-muted)" }}>
            {tag.validation_score !== null ? `validation ${(tag.validation_score * 100).toFixed(0)}%` : ""}
            {tag.prompt_version ? ` · prompt v${tag.prompt_version}` : ""}
          </span>
          <div className="flex gap-3">
            {tag.status === "open" && onContest && (
              <button
                onClick={() => onContest(tag)}
                className="text-xs font-medium hover:underline"
                style={{ color: "var(--series-1)" }}
              >
                Contest this flag
              </button>
            )}
            {(tag.status === "contested" || tag.status === "needs_review") && onReview && (
              <>
                <button
                  onClick={() => onReview(tag, "confirm")}
                  className="text-xs font-medium hover:underline"
                  style={{ color: "var(--status-good)" }}
                >
                  Confirm
                </button>
                <button
                  onClick={() => onReview(tag, "dismiss")}
                  className="text-xs font-medium hover:underline"
                  style={{ color: "var(--status-critical)" }}
                >
                  Dismiss
                </button>
              </>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
