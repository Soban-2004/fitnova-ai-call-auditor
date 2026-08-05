"use client";

import { useState } from "react";
import { X } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { formatTagLabel } from "@/lib/utils";
import type { IssueTagOut } from "@/lib/types";

export function ContestDialog({
  tag,
  onClose,
  onSubmit,
  submitting,
  error,
}: {
  tag: IssueTagOut;
  onClose: () => void;
  onSubmit: (reason: string) => void;
  submitting: boolean;
  error: string | null;
}) {
  const [reason, setReason] = useState("");

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
              Contest &ldquo;{formatTagLabel(tag.tag_type)}&rdquo;
            </h3>
            <p className="mt-0.5 text-xs" style={{ color: "var(--text-muted)" }}>
              Your team leader will review this and confirm or dismiss it.
            </p>
          </div>
          <button onClick={onClose} aria-label="Close">
            <X size={16} style={{ color: "var(--text-muted)" }} />
          </button>
        </div>

        <div className="mt-3 rounded-lg px-3 py-2 text-xs italic" style={{ backgroundColor: "var(--page)", color: "var(--text-secondary)" }}>
          &ldquo;{tag.quote}&rdquo;
        </div>

        <textarea
          autoFocus
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Explain why this flag is unfair or inaccurate…"
          rows={4}
          className="mt-3 w-full rounded-lg border px-2.5 py-2 text-sm"
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
          <Button variant="primary" onClick={() => onSubmit(reason)} disabled={submitting || reason.trim().length === 0}>
            {submitting ? "Submitting…" : "Submit contest"}
          </Button>
        </div>
      </div>
    </div>
  );
}
