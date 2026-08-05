"use client";

import { useState } from "react";
import { X } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { formatTagLabel } from "@/lib/utils";
import type { IssueTagOut } from "@/lib/types";

export function ReviewDialog({
  tag,
  action,
  onClose,
  onSubmit,
  submitting,
  error,
}: {
  tag: IssueTagOut;
  action: "confirm" | "dismiss";
  onClose: () => void;
  onSubmit: (comment: string, reviewedBy: string) => void;
  submitting: boolean;
  error: string | null;
}) {
  const [comment, setComment] = useState("");
  const [reviewedBy, setReviewedBy] = useState("Team Leader");

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div
        className="w-full max-w-md rounded-xl border p-5 shadow-lg"
        style={{ backgroundColor: "var(--surface-1)", borderColor: "var(--border)" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between">
          <div>
            <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
              {action === "dismiss" ? "Dismiss" : "Confirm"} &ldquo;{formatTagLabel(tag.tag_type)}&rdquo;
            </h3>
            <p className="mt-0.5 text-xs" style={{ color: "var(--text-muted)" }}>
              {action === "dismiss"
                ? "The score recalculates immediately and a new version is recorded."
                : "This confirms the flag is valid — no score change, but it's logged."}
            </p>
          </div>
          <button onClick={onClose} aria-label="Close">
            <X size={16} style={{ color: "var(--text-muted)" }} />
          </button>
        </div>

        <div className="mt-3 rounded-lg px-3 py-2 text-xs italic" style={{ backgroundColor: "var(--page)", color: "var(--text-secondary)" }}>
          &ldquo;{tag.quote}&rdquo;
        </div>
        {tag.contest_reason && (
          <div className="mt-2 rounded-lg px-3 py-2 text-xs" style={{ backgroundColor: "var(--page)", color: "var(--text-secondary)" }}>
            <span className="font-medium" style={{ color: "var(--text-primary)" }}>
              Advisor&apos;s contest:
            </span>{" "}
            {tag.contest_reason}
          </div>
        )}
        {tag.status === "needs_review" && (
          <div className="mt-2">
            <Badge role="warning">low validation confidence — never contested, flagged by the validator</Badge>
          </div>
        )}

        <label className="mt-3 block text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
          Your name
        </label>
        <input
          value={reviewedBy}
          onChange={(e) => setReviewedBy(e.target.value)}
          className="mt-1 w-full rounded-lg border px-2.5 py-1.5 text-sm"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)", color: "var(--text-primary)" }}
        />

        <label className="mt-3 block text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
          Comment
        </label>
        <textarea
          autoFocus
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          placeholder={action === "dismiss" ? "Why is this flag being dismissed?" : "Why does this flag hold up?"}
          rows={3}
          className="mt-1 w-full rounded-lg border px-2.5 py-2 text-sm"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)", color: "var(--text-primary)" }}
        />

        {error && (
          <p className="mt-2 text-xs" style={{ color: "var(--status-critical)" }}>
            {error}
          </p>
        )}

        <div className="mt-3 flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose} disabled={submitting}>
            Cancel
          </Button>
          <Button
            variant={action === "dismiss" ? "destructive" : "primary"}
            onClick={() => onSubmit(comment, reviewedBy)}
            disabled={submitting || reviewedBy.trim().length === 0}
          >
            {submitting ? "Submitting…" : action === "dismiss" ? "Dismiss & recalculate" : "Confirm flag"}
          </Button>
        </div>
      </div>
    </div>
  );
}
