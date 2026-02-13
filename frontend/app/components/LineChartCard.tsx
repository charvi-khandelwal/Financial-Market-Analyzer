"use client";

import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip } from "recharts";
import { GlassCard } from "./GlassCard";

export function LineChartCard({ title, data }: { title: string; data: Array<{ date: string; close: number | null }> }) {
  const cleaned = (data ?? []).slice().reverse().map(d => ({ ...d, close: d.close ?? undefined }));
  return (
    <GlassCard title={title} className="h-[320px]">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={cleaned}>
          <XAxis dataKey="date" hide />
          <YAxis domain={["auto", "auto"]} hide />
          <Tooltip />
          <Line type="monotone" dataKey="close" dot={false} strokeWidth={2} />
        </LineChart>
      </ResponsiveContainer>
    </GlassCard>
  );
}
