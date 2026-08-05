"use client";

import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/Card";
import type { ScoreTrendPoint } from "@/lib/types";

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
              <Tooltip
                cursor={{ stroke: "var(--axis)", strokeWidth: 1 }}
                contentStyle={{
                  backgroundColor: "var(--surface-2)",
                  border: "1px solid var(--border)",
                  borderRadius: 8,
                  fontSize: 12,
                  color: "var(--text-primary)",
                }}
                formatter={(value, name) => [
                  name === "avg_score" ? Number(value).toFixed(1) : value,
                  name === "avg_score" ? "Avg score" : "Calls",
                ]}
              />
              <Line
                type="monotone"
                dataKey="avg_score"
                stroke="var(--series-1)"
                strokeWidth={2}
                dot={{ r: 3, fill: "var(--series-1)", strokeWidth: 0 }}
                activeDot={{ r: 5 }}
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
