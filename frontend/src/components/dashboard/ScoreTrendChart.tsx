"use client";

import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { TooltipContentProps } from "recharts";
import type { NameType, ValueType } from "recharts/types/component/DefaultTooltipContent";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/Card";
import type { ScoreTrendPoint } from "@/lib/types";

/** Value-callout bubble instead of a plain tooltip box — a small pill that
 * floats above the hovered point with a pointer tail, the way Ghost's
 * dashboard surfaces a chart value on hover rather than a bare box. */
function ScoreCallout({ active, payload }: TooltipContentProps<ValueType, NameType>) {
  if (!active || !payload?.length) return null;
  const point = payload[0].payload as ScoreTrendPoint;
  return (
    <div className="flex flex-col items-center">
      <div
        className="whitespace-nowrap rounded-full px-2.5 py-1 text-xs font-semibold text-white shadow-lg"
        style={{ backgroundColor: "var(--series-1)" }}
      >
        {point.avg_score.toFixed(1)}
        <span className="ml-1.5 font-normal opacity-80">
          {point.call_count} call{point.call_count === 1 ? "" : "s"}
        </span>
      </div>
      <div
        className="h-1.5 w-1.5 rotate-45"
        style={{ backgroundColor: "var(--series-1)", marginTop: -3 }}
      />
    </div>
  );
}

/** Glowing active dot -- a soft halo behind the point on hover, echoing the
 * "live" glow treatment used elsewhere instead of a plain filled circle. */
function GlowDot({ cx, cy }: { cx?: number; cy?: number }) {
  if (cx === undefined || cy === undefined) return null;
  return (
    <g>
      <circle cx={cx} cy={cy} r={8} fill="var(--series-1)" opacity={0.18} />
      <circle cx={cx} cy={cy} r={4} fill="var(--series-1)" stroke="var(--surface-1)" strokeWidth={2} />
    </g>
  );
}

export function ScoreTrendChart({
  title = "Score trend",
  description = "Weekly average final score",
  data,
  headerRight,
}: {
  title?: string;
  description?: string;
  data: ScoreTrendPoint[];
  headerRight?: React.ReactNode;
}) {
  if (data.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{title}</CardTitle>
          {headerRight}
        </CardHeader>
        <CardContent>
          <EmptyState />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-col items-start">
          <CardTitle>{title}</CardTitle>
          <CardDescription>{description}</CardDescription>
        </div>
        {headerRight}
      </CardHeader>
      <CardContent>
        <div style={{ width: "100%", height: 220 }}>
          <ResponsiveContainer>
            <LineChart data={data} margin={{ top: 8, right: 12, left: -16, bottom: 0 }}>
              <CartesianGrid vertical={false} stroke="var(--gridline)" />
              <XAxis
                dataKey="week"
                tick={{ fontSize: 11, fill: "var(--text-muted)" }}
                axisLine={{ stroke: "var(--axis)" }}
                tickLine={false}
              />
              <YAxis
                domain={[0, 100]}
                tick={{ fontSize: 11, fill: "var(--text-muted)" }}
                axisLine={false}
                tickLine={false}
                width={40}
              />
              <Tooltip cursor={{ stroke: "var(--axis)", strokeWidth: 1 }} content={(props) => <ScoreCallout {...props} />} />
              <Line
                type="monotone"
                dataKey="avg_score"
                stroke="var(--series-1)"
                strokeWidth={2}
                dot={{ r: 3, fill: "var(--series-1)", strokeWidth: 0 }}
                activeDot={<GlowDot />}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}

export function EmptyState({ message = "Not enough data yet" }: { message?: string }) {
  return (
    <div
      className="flex h-32 items-center justify-center rounded-lg text-sm"
      style={{ color: "var(--text-muted)", backgroundColor: "var(--page)" }}
    >
      {message}
    </div>
  );
}
