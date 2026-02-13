import { ReactNode } from "react";
import clsx from "clsx";

export function GlassCard({ title, children, className }: { title?: string; children: ReactNode; className?: string }) {
  return (
    <div className={clsx(
      "rounded-2xl border border-white/10 bg-white/5 shadow-[0_10px_30px_rgba(0,0,0,0.35)] backdrop-blur-xl",
      "p-4 md:p-5",
      className
    )}>
      {title ? <div className="text-sm tracking-wide text-white/70 mb-3">{title}</div> : null}
      {children}
    </div>
  );
}
