"use client";

import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/Card";
import { scoreStatus, statusColorVar } from "@/lib/utils";
import { EmptyState } from "./ScoreTrendChart";

/** Band color follows the range's midpoint ("81-100" -> ~90) through the
 * same red/amber/green thresholds as a score badge -- these buckets are
 * ordered worse-to-better, so a semantic gradient reads correctly where an
 * arbitrary identity color wouldn't. */
function bandColorVar(range: string): string {
  const [lo, hi] = range.split("-").map(Number);
  return statusColorVar(scoreStatus((lo + hi) / 2));
}

export function ScoreDistribution({ data }: { data: { range: string; count: number }[] }) {
  const hasData = data.some((d) => d.count > 0);
  return (
    <Card>
      <CardHeader className="flex-col items-start">
        <CardTitle>Score distribution</CardTitle>
        <CardDescription>How advisors are spread across score bands</CardDescription>
      </CardHeader>
      <CardContent>
        {!hasData ? (
          <EmptyState />
        ) : (
          <div style={{ width: "100%", height: 220 }}>
            <ResponsiveContainer>
              <BarChart data={data} margin={{ top: 8, right: 12, left: -16, bottom: 0 }}>
                <CartesianGrid vertical={false} stroke="var(--gridline)" />
                <XAxis
                  dataKey="range"
                  tick={{ fontSize: 11, fill: "var(--text-muted)" }}
                  axisLine={{ stroke: "var(--axis)" }}
                  tickLine={false}
                />
                <YAxis
                  allowDecimals={false}
                  tick={{ fontSize: 11, fill: "var(--text-muted)" }}
                  axisLine={false}
                  tickLine={false}
                  width={32}
                />
                <Tooltip
                  cursor={{ fill: "var(--gridline)" }}
                  contentStyle={{
                    backgroundColor: "var(--surface-2)",
                    border: "1px solid var(--border)",
                    borderRadius: 8,
                    fontSize: 12,
                    color: "var(--text-primary)",
                  }}
                  formatter={(value) => [value, "Calls"]}
                />
                <Bar dataKey="count" radius={[4, 4, 0, 0]} maxBarSize={48}>
                  {data.map((d) => (
                    <Cell key={d.range} fill={bandColorVar(d.range)} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
