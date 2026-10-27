import { useCallback, useEffect, useRef, useState } from "react";
import { cancelAnalysis, getAnalysis, getConfig, startAnalysis } from "./api";
import { fixtureAnalysis } from "./lib/fixture";
import type { Analysis, AppConfig, StartRequest } from "./types";
import TargetForm from "./components/TargetForm";
import Progress from "./components/Progress";
import GraphView from "./components/GraphView";
import EvidencePanel from "./components/EvidencePanel";
import Insights from "./components/Insights";

type Sel = { kind: "node" | "edge"; id: string } | null;

const Logo = () => (
  <svg width="28" height="28" viewBox="0 0 32 32" aria-hidden><rect width="32" height="32" rx="8" fill="#0e121a" stroke="#263044" />
    <path d="M9 9h9l5 5v9H9z" fill="none" stroke="#22d3ee" strokeWidth="1.8" /><circle cx="16" cy="17" r="2.4" fill="#fbbf24" /></svg>
);

export default function App() {
  const [a, setA] = useState<Analysis | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [sel, setSel] = useState<Sel>(null);
  const [starting, setStarting] = useState(false);
  const [cfg, setCfg] = useState<AppConfig | null>(null);
  useEffect(() => { getConfig().then(setCfg).catch(() => setCfg(null)); }, []);
  const timer = useRef<number | null>(null);
  const busy = starting || a?.status === "running" || a?.status === "queued";

  const stop = () => { if (timer.current) window.clearInterval(timer.current); timer.current = null; };
  useEffect(() => stop, []);

  const poll = useCallback((id: string) => {
    stop();
    let fails = 0;
    timer.current = window.setInterval(async () => {
      try {
        const next = await getAnalysis(id); fails = 0; setA(next);
        if (next.status === "completed" || next.status === "failed") stop();
      } catch (e) {
        if (++fails >= 3) { stop(); setErr(`Lost connection to the backend: ${(e as Error).message}`); }
      }
    }, 900);
  }, []);

  const start = async (req: StartRequest) => {
    setErr(null); setSel(null); setA(null); setStarting(true);
    try { const { id } = await startAnalysis(req); poll(id); }
    catch (e) {
      const m = (e as Error).message;
      setErr(/failed to fetch|networkerror|econnrefused|proxy/i.test(m) || m === "Bad Gateway"
        ? "Cannot reach the Atlas backend at /api (expected at http://127.0.0.1:8000). The backend isn't running yet — use “Preview UI with sample fixture” to explore the dashboard."
        : m);
    } finally { setStarting(false); }
  };
  const cancel = async () => { if (a) { try { await cancelAnalysis(a.id); } catch { /* ignore */ } } };
  const fixture = () => { stop(); setErr(null); setSel(null); setA(fixtureAnalysis()); };

  return (
    <div className="mx-auto max-w-[1500px] px-4 py-5 sm:px-6">
      <header className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3"><Logo />
          <div><h1 className="text-lg font-semibold tracking-tight text-slate-100">BlackBox <span className="text-signal">Atlas</span></h1>
            <p className="text-xs text-slate-500">Evidence-backed behavioral reverse-engineering</p></div></div>
        <div className="flex items-center gap-2 text-[11px] text-slate-500">
          <span className={`chip ${cfg?.embeddings.enabled ? "border-signal/40 bg-signal/10 text-signal" : "border-ink-600 text-slate-500"}`} title={cfg ? "NVIDIA embeddings" : "Backend not reachable"}>
            {cfg ? (cfg.embeddings.enabled ? `● NVIDIA embeddings: ${cfg.embeddings.model}` : "○ NVIDIA embeddings off") : "○ backend offline"}</span>
          <span className="chip border-ink-600 text-slate-400">observe → graph → hypothesize → blueprint</span>
        </div>
      </header>

      {a?.fixture && <div role="status" className="mb-4 rounded-lg border border-infer/40 bg-infer/10 px-4 py-2 text-sm text-infer">⚠ <b>UI PREVIEW FIXTURE</b> — hand-written sample data to preview the interface. This is <u>not</u> a real browser observation.</div>}
      {a && a.demo && !a.fixture && <div role="status" className="mb-4 rounded-lg border border-infer/40 bg-infer/10 px-4 py-2 text-sm text-infer">🧪 <b>DEMO MODE</b> — observations come from the bundled synthetic app, not a third-party site.</div>}
      {err && <div role="alert" className="mb-4 rounded-lg border border-rose-500/40 bg-rose-500/10 px-4 py-2 text-sm text-rose-300">✖ {err}</div>}

      <div className="mb-4 grid gap-4 lg:grid-cols-2"><TargetForm busy={!!busy} onStart={start} onCancel={cancel} onFixture={fixture} /><Progress a={a} busy={!!busy} /></div>

      <div className="mb-4 grid gap-4 lg:grid-cols-[minmax(0,1fr)_380px]">
        <GraphView a={a} selected={sel} onSelect={setSel} />
        <EvidencePanel a={a} selected={sel} />
      </div>
      <Insights a={a} cfg={cfg} onPick={(id) => setSel({ kind: "node", id })} />
      <footer className="mt-6 text-center text-[11px] text-slate-600">BlackBox Atlas · hypotheses are labelled observed/inferred · no private APIs or internals are ever asserted without evidence</footer>
    </div>
  );
}
