"use client";

import { motion } from "framer-motion";

export function SentimentBar({ score }: { score: number | null }) {
  const v = score ?? 0;
  const pct = Math.max(0, Math.min(100, (v + 1) * 50));
  const label =
    score === null ? "n/a" :
    v > 0.15 ? "positive" :
    v < -0.15 ? "negative" : "neutral";

  return (
    <div className="rounded-xl border border-white/10 bg-black/10 p-3">
      <div className="flex items-center justify-between">
        <div className="text-xs text-white/60">Overall sentiment</div>
        <div className="text-xs text-white/60">{label} ({score === null ? "—" : v.toFixed(2)})</div>
      </div>
      <div className="mt-2 h-2 rounded-full bg-white/10 overflow-hidden">
        <motion.div
          className="h-2 bg-white/60"
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ type: "spring", stiffness: 120, damping: 20 }}
        />
      </div>
    </div>
  );
}
