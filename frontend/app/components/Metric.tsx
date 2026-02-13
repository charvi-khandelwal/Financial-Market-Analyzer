export function Metric({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-xl border border-white/10 bg-black/10 p-3">
      <div className="text-xs text-white/60">{label}</div>
      <div className="text-lg font-semibold">{value}</div>
      {sub ? <div className="text-xs text-white/50 mt-1">{sub}</div> : null}
    </div>
  );
}
