"use client";

import { useRef, useState } from "react";
import { TranscriptViewer } from "./TranscriptViewer";
import { AudioPlayer } from "./AudioPlayer";
import { IssueTagCard } from "./IssueTagCard";
import { DimensionRatingsChart } from "./DimensionRatingsChart";
import { ScoreBreakdown } from "./ScoreBreakdown";
import { ScoreHistory } from "./ScoreHistory";
import { ContestDialog } from "./ContestDialog";
import { ReviewDialog } from "./ReviewDialog";
import { Toast } from "@/components/ui/Toast";
import { api, ApiError } from "@/lib/api";
import type { CallDetail, IssueTagOut } from "@/lib/types";

export function CallDetailClient({ callId, initialCall }: { callId: string; initialCall: CallDetail }) {
  const [call, setCall] = useState(initialCall);
  const [contestingTag, setContestingTag] = useState<IssueTagOut | null>(null);
  const [reviewing, setReviewing] = useState<{ tag: IssueTagOut; action: "confirm" | "dismiss" } | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [dialogError, setDialogError] = useState<string | null>(null);
  const [toast, setToast] = useState<{ message: string; tone: "success" | "error" } | null>(null);

  const audioRef = useRef<HTMLAudioElement>(null);
  const [playheadSecs, setPlayheadSecs] = useState<number | undefined>(undefined);

  function seekTo(secs: number) {
    if (!audioRef.current) return;
    audioRef.current.currentTime = secs;
    audioRef.current.play().catch(() => {
      /* autoplay can be blocked before any user gesture — the click that got us
       here counts as one, so this is just a defensive no-op */
    });
  }

  function showToast(message: string, tone: "success" | "error" = "success") {
    setToast({ message, tone });
    setTimeout(() => setToast(null), 3500);
  }

  async function refresh() {
    const fresh = await api.callDetail(callId);
    setCall(fresh);
  }

  async function handleContestSubmit(reason: string) {
    if (!contestingTag) return;
    setSubmitting(true);
    setDialogError(null);
    try {
      await api.contestTag(contestingTag.id, reason);
      await refresh();
      setContestingTag(null);
      showToast("Contest submitted — awaiting team leader review");
    } catch (e) {
      setDialogError(e instanceof ApiError ? e.message : "Failed to submit contest");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleReviewSubmit(comment: string, reviewedBy: string) {
    if (!reviewing) return;
    setSubmitting(true);
    setDialogError(null);
    try {
      const result = await api.reviewTag(reviewing.tag.id, reviewing.action, comment, reviewedBy);
      await refresh();
      setReviewing(null);
      const verb = reviewing.action === "confirm" ? "confirmed" : "dismissed";
      const scoreNote =
        result.score_updated && result.old_score !== undefined && result.new_score !== undefined
          ? ` — score updated ${result.old_score} → ${result.new_score}`
          : "";
      showToast(`Tag ${verb}${scoreNote}`);
    } catch (e) {
      setDialogError(e instanceof ApiError ? e.message : "Failed to submit review");
    } finally {
      setSubmitting(false);
    }
  }

  const latestScore = call.score_history[0] ?? null;
  const openTags = call.issue_tags.filter((t) => t.status !== "dismissed");
  const dismissedTags = call.issue_tags.filter((t) => t.status === "dismissed");

  return (
    <>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_380px]">
        <div className="flex flex-col gap-4">
          <AudioPlayer ref={audioRef} src={api.audioUrl(callId)} onTimeUpdate={setPlayheadSecs} />
          <TranscriptViewer
            segments={call.transcript}
            tags={call.issue_tags}
            playheadSecs={playheadSecs}
            onSeek={seekTo}
          />
        </div>

        <div className="flex flex-col gap-4">
          <ScoreBreakdown latest={latestScore} />
          {call.dimension_ratings.length > 0 && <DimensionRatingsChart dimensions={call.dimension_ratings} />}
          <ScoreHistory history={call.score_history} />

          {openTags.length > 0 && (
            <div className="flex flex-col gap-2">
              <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                Flagged issues ({openTags.length})
              </h2>
              {openTags.map((tag) => (
                <IssueTagCard
                  key={tag.id}
                  tag={tag}
                  onContest={(t) => {
                    setDialogError(null);
                    setContestingTag(t);
                  }}
                  onReview={(t, action) => {
                    setDialogError(null);
                    setReviewing({ tag: t, action });
                  }}
                />
              ))}
            </div>
          )}

          {dismissedTags.length > 0 && (
            <div className="flex flex-col gap-2">
              <h2 className="text-sm font-semibold" style={{ color: "var(--text-muted)" }}>
                Dismissed ({dismissedTags.length})
              </h2>
              {dismissedTags.map((tag) => (
                <IssueTagCard key={tag.id} tag={tag} />
              ))}
            </div>
          )}

          {call.issue_tags.length === 0 && call.status === "COMPLETED" && (
            <div className="rounded-lg border px-4 py-3 text-center text-sm" style={{ borderColor: "var(--border)", color: "var(--text-muted)" }}>
              No issues flagged on this call.
            </div>
          )}
        </div>
      </div>

      {contestingTag && (
        <ContestDialog
          tag={contestingTag}
          onClose={() => setContestingTag(null)}
          onSubmit={handleContestSubmit}
          submitting={submitting}
          error={dialogError}
        />
      )}
      {reviewing && (
        <ReviewDialog
          tag={reviewing.tag}
          action={reviewing.action}
          onClose={() => setReviewing(null)}
          onSubmit={handleReviewSubmit}
          submitting={submitting}
          error={dialogError}
        />
      )}

      {toast && <Toast message={toast.message} tone={toast.tone} />}
    </>
  );
}
