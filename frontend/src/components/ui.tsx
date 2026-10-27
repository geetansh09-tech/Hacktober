import type { ReactNode } from "react";
import type { Confidence, Provenance } from "../types";

export const ProvChip = ({ p }: { p: Provenance }) =>
  p === "observed"
    ? <span className="chip border-signal/40 bg-signal/10 text-signal">● OBSERVED</span>
    : <span className="chip border-infer/40 bg-infer/10 text-infer">◌ INFERRED</span>;

const confColor: Record<Confidence, string> = {
  high: "border-emerald-500/40 text-emerald-300 bg-emerald-500/10",
  medium: "border-sky-500/40 text-sky-300 bg-sky-500/10",
  low: "border-rose-500/40 text-rose-300 bg-rose-500/10",
};
export const ConfChip = ({ c }: { c: Confidence }) => <span className={`chip ${confColor[c]}`}>{c.toUpperCase()} CONF</span>;

export const Section = ({ title, right, children }: { title: string; right?: ReactNode; children: ReactNode }) => (
  <div>
    <div className="mb-2 flex items-center justify-between"><span className="label">{title}</span>{right}</div>
    {children}
  </div>
);

export const Empty = ({ icon, title, hint }: { icon: string; title: string; hint?: string }) => (
  <div className="flex h-full min-h-[200px] flex-col items-center justify-center gap-2 p-6 text-center">
    <div className="text-3xl opacity-60">{icon}</div>
    <div className="text-sm font-medium text-slate-300">{title}</div>
    {hint && <div className="max-w-xs text-xs text-slate-500">{hint}</div>}
  </div>
);
