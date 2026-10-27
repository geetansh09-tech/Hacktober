import type { Analysis } from "../types";

const Stat = ({ k, v, sub }: { k: string; v: string | number; sub?: string }) => (
  <div className="rounded-lg border border-ink-700 bg-ink-950/60 px-3 py-2.5">
    <div className="label">{k}</div>
    <div className="mt-1 font-mono text-2xl font-semibold text-slate-100">{v}<span className="ml-1 text-xs font-normal text-slate-500">{sub}</span></div>
  </div>
);

export default function Progress({ a, busy }: { a: Analysis | null; busy: boolean }) {
  const pct = a ? Math.min(100, Math.round((a.progress.pages_visited / Math.max(1, a.limits.max_pages)) * 100)) : 0;
  const state = !a ? "idle" : a.status;
  const color = { idle: "text-slate-500", queued: "text-infer", running: "text-signal", completed: "text-emerald-400", failed: "text-rose-400" }[state];
  return (
    <div className="card p-5">
      <div className="mb-3 flex items-center justify-between">
        <span className="label">Live progress</span>
        <span className={`flex items-center gap-1.5 font-mono text-xs uppercase ${color}`}>
          <span className={`h-1.5 w-1.5 rounded-full bg-current ${busy ? "animate-pulse" : ""}`} />{state}
        </span>
      </div>
      <div className="relative h-1.5 overflow-hidden rounded-full bg-ink-700">
        <div className="h-full rounded-full bg-gradient-to-r from-signal-dim to-signal transition-all duration-500" style={{ width: `${a?.status === "completed" ? 100 : pct}%` }} />
        {busy && <div className="scanbar absolute inset-y-0 left-0 w-1/4 bg-gradient-to-r from-transparent via-white/30 to-transparent" />}
      </div>
      <p className="mt-2 min-h-[1.25rem] truncate font-mono text-xs text-slate-400">{a?.error ? `✖ ${a.error}` : a?.progress.message ?? "Waiting for a target…"}</p>
      <div className="mt-3 grid grid-cols-3 gap-2">
        <Stat k="Discovered" v={a?.progress.pages_discovered ?? 0} />
        <Stat k="Visited" v={a?.progress.pages_visited ?? 0} sub={a ? `/${a.limits.max_pages}` : ""} />
        <Stat k="Elapsed" v={a ? a.elapsed_s.toFixed(1) : "0.0"} sub="s" />
      </div>
    </div>
  );
}
