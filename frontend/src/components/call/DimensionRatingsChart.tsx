"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { formatDimensionLabel } from "@/lib/utils";
import type { DimensionRatingOut } from "@/lib/types";

export function DimensionRatingsChart({ dimensions }: { dimensions: DimensionRatingOut[] }) {
  const data = dimensions.map((d) => ({ ...d, label: formatDimensionLabel(d.dimension) }));

  return (
    <Card>
      <CardHeader className="flex-col items-start">
        <CardTitle>Dimension ratings</CardTitle>
      </CardHeader>
      <CardContent>
        <div style={{ width: "100%", height: 260 }}>
          <ResponsiveContainer>
            <BarChart data={data} margin={{ top: 8, right: 12, left: -8, bottom: 24 }}>
              <CartesianGrid vertical={false} stroke="var(--gridline)" />
              <XAxis
                dataKey="label"
                tick={{ fontSize: 11, fill: "var(--text-muted)" }}
                axisLine={{ stroke: "var(--axis)" }}
                tickLine={false}
                interval={0}
                angle={-20}
                textAnchor="end"
                height={50}
              />
              <YAxis
                domain={[0, 10]}
                tick={{ fontSize: 11, fill: "var(--text-muted)" }}
                axisLine={false}
                tickLine={false}
                width={28}
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
                formatter={(value, _name, item) => [
                  `${value}/10${item.payload.evidence ? ` — ${item.payload.evidence}` : ""}`,
                  "Score",
                ]}
              />
              <Bar dataKey="score" fill="var(--series-1)" radius={[4, 4, 0, 0]} maxBarSize={48} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}
