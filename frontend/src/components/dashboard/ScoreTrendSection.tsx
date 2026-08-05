"use client";

import { useState } from "react";
import { ScoreTrendChart } from "./ScoreTrendChart";
import { api, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { ScoreTrendPoint } from "@/lib/types";

const RANGE_OPTIONS = [4, 8, 12] as const;

/** Wraps ScoreTrendChart with a 4/8/12-week range selector. The dashboard
 * page fetches the default (8-week) window server-side same as before;
 * switching ranges re-fetches only the trend line via the lightweight
 * /api/dashboard/trend endpoint, not the whole dashboard payload. */
export function ScoreTrendSection({
  scope,
  id,
  initialData,
  initialWeeks = 8,
  title,
  description,
}: {
  scope: "org" | "team" | "advisor";
  id?: string;
  initialData: ScoreTrendPoint[];
  initialWeeks?: number;
  title?: string;
  description?: string;
}) {
  const [weeks, setWeeks] = useState(initialWeeks);
  const [data, setData] = useState(initialData);
  const [loading, setLoading] = useState(false);

  async function handleSelect(w: number) {
    if (w === weeks || loading) return;
    setLoading(true);
    try {
      const res = await api.scoreTrend(scope, id, w);
      setData(res.trend);
      setWeeks(w);
    } catch (e) {
      console.error("Failed to refetch score trend:", e instanceof ApiError ? e.message : e);
      // leave the previously-loaded range on screen rather than blanking the chart
    } finally {
      setLoading(false);
    }
  }

  return (
    <ScoreTrendChart
      data={data}
      title={title}
      description={description}
      headerRight={
        <div className="flex gap-1" style={{ opacity: loading ? 0.6 : 1 }}>
          {RANGE_OPTIONS.map((w) => (
            <button
              key={w}
              onClick={() => handleSelect(w)}
              className={cn(
                "rounded-md px-2 py-0.5 text-xs font-medium transition-colors",
                w === weeks
                  ? "text-white"
                  : "text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[color-mix(in_srgb,var(--text-secondary)_10%,transparent)]"
              )}
              style={w === weeks ? { backgroundColor: "var(--series-1)" } : undefined}
            >
              {w}w
            </button>
          ))}
        </div>
      }
    />
  );
}
