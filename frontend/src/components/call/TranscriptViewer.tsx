"use client";

import { useMemo, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { formatTagLabel, severityColorVar } from "@/lib/utils";
import type { IssueTagOut, TranscriptSegmentOut } from "@/lib/types";

function fmtTs(secs: number): string {
  const m = Math.floor(secs / 60);
  const s = Math.floor(secs % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function tagsForSegment(seg: TranscriptSegmentOut, tags: IssueTagOut[]): IssueTagOut[] {
  return tags.filter(
    (t) => t.start_ts !== null && t.end_ts !== null && t.start_ts < seg.end_ts && t.end_ts > seg.start_ts
  );
}

const SEVERITY_RANK: Record<string, number> = { critical: 3, major: 2, minor: 1 };

export function TranscriptViewer({
  segments,
  tags,
  highlightedTagId,
  playheadSecs,
  onSeek,
}: {
  segments: TranscriptSegmentOut[];
  tags: IssueTagOut[];
  highlightedTagId?: string | null;
  /** Current audio playback position, if a synced player is mounted above this viewer. */
  playheadSecs?: number;
  /** Seeks the audio player to a timestamp — omit to render plain (non-clickable) timestamps. */
  onSeek?: (secs: number) => void;
}) {
  const [activeTagId, setActiveTagId] = useState<string | null>(highlightedTagId ?? null);
  const [hiddenTypes, setHiddenTypes] = useState<Set<string>>(new Set());

  const distinctTagTypes = useMemo(() => Array.from(new Set(tags.map((t) => t.tag_type))), [tags]);
  const visibleTags = useMemo(() => tags.filter((t) => !hiddenTypes.has(t.tag_type)), [tags, hiddenTypes]);

  function toggleType(type: string) {
    setHiddenTypes((prev) => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  }

  if (segments.length === 0) {
    return (
      <Card>
        <CardContent className="pt-4 text-sm" style={{ color: "var(--text-muted)" }}>
          No transcript available yet — this call may still be processing.
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="flex-col items-start gap-2">
        <CardTitle>Transcript</CardTitle>
        {distinctTagTypes.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {distinctTagTypes.map((type) => {
              const hidden = hiddenTypes.has(type);
              return (
                <button
                  key={type}
                  onClick={() => toggleType(type)}
                  className="rounded-full border px-2 py-0.5 text-[11px] font-medium transition-opacity"
                  style={{
                    borderColor: "var(--border)",
                    color: hidden ? "var(--text-muted)" : "var(--text-secondary)",
                    opacity: hidden ? 0.5 : 1,
                  }}
                  title={hidden ? "Click to show" : "Click to hide"}
                >
                  {formatTagLabel(type)}
                </button>
              );
            })}
          </div>
        )}
      </CardHeader>
      <CardContent className="flex flex-col gap-2 max-h-[560px] overflow-y-auto">
        {segments.map((seg) => {
          const segTags = tagsForSegment(seg, visibleTags);
          const worst = segTags.reduce<string | null>((acc, t) => {
            if (!acc) return t.severity;
            return SEVERITY_RANK[t.severity] > SEVERITY_RANK[acc] ? t.severity : acc;
          }, null);
          const isAdvisor = seg.speaker_role === "advisor";
          const isActive = segTags.some((t) => t.id === activeTagId);
          const isPlaying =
            playheadSecs !== undefined && playheadSecs >= seg.start_ts && playheadSecs < seg.end_ts;

          return (
            <div
              key={seg.id}
              id={`segment-${seg.id}`}
              className="flex gap-3 rounded-lg px-3 py-2 transition-colors"
              style={{
                borderLeft: worst ? `3px solid ${severityColorVar(worst)}` : "3px solid transparent",
                backgroundColor: isPlaying
                  ? "color-mix(in srgb, var(--series-1) 16%, transparent)"
                  : isActive
                    ? "color-mix(in srgb, var(--series-1) 10%, transparent)"
                    : "transparent",
              }}
            >
              {onSeek ? (
                <button
                  onClick={() => onSeek(seg.start_ts)}
                  className="w-14 shrink-0 pt-0.5 text-left text-xs tabular-nums hover:underline"
                  style={{ color: isPlaying ? "var(--series-1)" : "var(--text-muted)" }}
                  title="Jump to this moment"
                >
                  {fmtTs(seg.start_ts)}
                </button>
              ) : (
                <div className="w-14 shrink-0 pt-0.5 text-xs tabular-nums" style={{ color: "var(--text-muted)" }}>
                  {fmtTs(seg.start_ts)}
                </div>
              )}
              <div className="min-w-0 flex-1">
                <div
                  className="text-xs font-semibold uppercase tracking-wide"
                  style={{ color: isAdvisor ? "var(--series-1)" : "var(--text-secondary)" }}
                >
                  {seg.speaker_role ?? seg.speaker_label ?? "Unknown"}
                </div>
                <p className="text-sm leading-relaxed" style={{ color: "var(--text-primary)" }}>
                  {seg.text}
                </p>
                {segTags.length > 0 && (
                  <div className="mt-1 flex flex-wrap gap-1.5">
                    {segTags.map((t) => (
                      <button
                        key={t.id}
                        onClick={() => setActiveTagId(t.id === activeTagId ? null : t.id)}
                        className="rounded-full px-2 py-0.5 text-[11px] font-medium"
                        style={{
                          color: severityColorVar(t.severity),
                          backgroundColor: `color-mix(in srgb, ${severityColorVar(t.severity)} 14%, transparent)`,
                        }}
                      >
                        {formatTagLabel(t.tag_type)}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
