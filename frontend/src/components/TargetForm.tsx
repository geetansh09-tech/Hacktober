import { useState } from "react";
import { validateTarget } from "../lib/url";
import type { StartRequest } from "../types";

interface Props { busy: boolean; onStart: (r: StartRequest) => void; onCancel: () => void; onFixture: () => void; }

export default function TargetForm({ busy, onStart, onCancel, onFixture }: Props) {
  const [url, setUrl] = useState("");
  const [demo, setDemo] = useState(true);
  const [maxPages, setMaxPages] = useState(25);
  const [timeLimit, setTimeLimit] = useState(120);
  const [err, setErr] = useState<string | null>(null);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (demo) { setErr(null); return onStart({ url: "demo", demo: true, max_pages: maxPages, time_limit_s: timeLimit }); }
    const v = validateTarget(url);
    if (!v.ok) return setErr(v.reason);
    setErr(null);
    onStart({ url: v.url, demo: false, max_pages: maxPages, time_limit_s: timeLimit });
  };

  return (
    <form onSubmit={submit} className="card p-5">
      <div className="mb-3 flex items-center justify-between">
        <span className="label">Target</span>
        <label className="flex cursor-pointer items-center gap-2 text-xs text-slate-400">
          <button type="button" role="switch" aria-checked={demo} onClick={() => setDemo(!demo)} disabled={busy}
            className={`relative h-5 w-9 rounded-full border transition ${demo ? "border-signal/60 bg-signal/20" : "border-ink-600 bg-ink-800"}`}>
            <span className={`absolute top-0.5 h-3.5 w-3.5 rounded-full transition-all ${demo ? "left-[18px] bg-signal" : "left-0.5 bg-slate-500"}`} />
          </button>
          Demo mode <span className="chip border-infer/40 bg-infer/10 text-infer">SYNTHETIC APP</span>
        </label>
      </div>

      <div className="flex flex-col gap-3 sm:flex-row">
        <div className="relative flex-1">
          <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 font-mono text-xs text-slate-600">GET</span>
          <input value={demo ? "bundled synthetic app (served locally by Atlas)" : url} onChange={(e) => setUrl(e.target.value)} disabled={busy || demo}
            placeholder="https://target-app.example.com" spellCheck={false} aria-label="Target URL"
            className="w-full rounded-lg border border-ink-600 bg-ink-950 py-2.5 pl-11 pr-3 font-mono text-sm text-slate-100 placeholder:text-slate-600 focus:border-signal/60 focus:outline-none focus:ring-2 focus:ring-signal/20 disabled:text-slate-500" />
        </div>
        {busy
          ? <button type="button" onClick={onCancel} className="btn border border-rose-500/40 bg-rose-500/10 text-rose-300 hover:bg-rose-500/20">■ Stop</button>
          : <button type="submit" className="btn bg-signal text-ink-950 shadow-glow hover:brightness-110">▶ Start analysis</button>}
      </div>
      {err && <p role="alert" className="mt-2 text-xs text-rose-400">⚠ {err}</p>}

      <div className="mt-4 grid grid-cols-2 gap-3 text-xs text-slate-400">
        <label className="flex items-center justify-between gap-2 rounded-lg border border-ink-700 bg-ink-950/60 px-3 py-2">Max pages
          <input type="number" min={1} max={100} value={maxPages} disabled={busy} onChange={(e) => setMaxPages(Math.min(100, Math.max(1, +e.target.value || 1)))}
            className="w-16 rounded border border-ink-600 bg-ink-900 px-2 py-1 text-right font-mono text-slate-200 focus:border-signal/60 focus:outline-none" />
        </label>
        <label className="flex items-center justify-between gap-2 rounded-lg border border-ink-700 bg-ink-950/60 px-3 py-2">Time limit (s)
          <input type="number" min={10} max={600} value={timeLimit} disabled={busy} onChange={(e) => setTimeLimit(Math.min(600, Math.max(10, +e.target.value || 10)))}
            className="w-16 rounded border border-ink-600 bg-ink-900 px-2 py-1 text-right font-mono text-slate-200 focus:border-signal/60 focus:outline-none" />
        </label>
      </div>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-ink-700 pt-3 text-[11px] text-slate-500">
        <span>🛡 Public pages only · no auth bypass · private networks blocked</span>
        <button type="button" onClick={onFixture} disabled={busy} className="text-slate-500 underline decoration-dotted underline-offset-2 hover:text-infer">
          Preview UI with sample fixture
        </button>
      </div>
    </form>
  );
}
