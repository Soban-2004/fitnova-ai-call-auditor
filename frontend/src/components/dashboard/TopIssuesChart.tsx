"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/Card";
import { formatTagLabel } from "@/lib/utils";
import { EmptyState } from "./ScoreTrendChart";

export function TopIssuesChart({
  data,
  title = "Top issues",
  description = "Most frequent open flags",
}: {
  data: { tag_type: string; count: number }[];
  title?: string;
  description?: string;
}) {
  const chartData = data.map((d) => ({ ...d, label: formatTagLabel(d.tag_type) }));

  return (
    <Card>
      <CardHeader className="flex-col items-start">
        <CardTitle>{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent>
        {chartData.length === 0 ? (
          <EmptyState message="No issues flagged" />
        ) : (
          <div style={{ width: "100%", height: Math.max(160, chartData.length * 36) }}>
            <ResponsiveContainer>
              <BarChart
                data={chartData}
                layout="vertical"
                margin={{ top: 0, right: 24, left: 0, bottom: 0 }}
              >
                <CartesianGrid horizontal={false} stroke="var(--gridline)" />
                <XAxis
                  type="number"
                  allowDecimals={false}
                  tick={{ fontSize: 11, fill: "var(--text-muted)" }}
                  axisLine={{ stroke: "var(--axis)" }}
                  tickLine={false}
                />
                <YAxis
                  type="category"
                  dataKey="label"
                  width={150}
                  tick={{ fontSize: 12, fill: "var(--text-secondary)" }}
                  axisLine={false}
                  tickLine={false}
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
                  formatter={(value) => [value, "Occurrences"]}
                />
                <Bar dataKey="count" fill="var(--series-1)" radius={[0, 4, 4, 0]} maxBarSize={20} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
