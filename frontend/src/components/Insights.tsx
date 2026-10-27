import { useState } from "react";
import type { Analysis, AppConfig, Hypothesis } from "../types";
import { toJson, toMarkdown, download } from "../lib/report";
import { buildClone } from "../api";
import { ConfChip, Empty, ProvChip } from "./ui";
import SemanticSearch from "./SemanticSearch";
import AskAI from "./AskAI";

const TABS = ["Architecture", "Workflows", "Gaps & next steps", "Ask AI", "Semantic search", "Report"] as const;
type Tab = (typeof TABS)[number];

function HypCard({ h }: { h: Hypothesis }) {
  return (
    <div className="rounded-lg border border-ink-700 bg-ink-950/60 p-3.5">
      <div className="flex flex-wrap items-center gap-2"><ProvChip p={h.provenance} /><ConfChip c={h.confidence} /></div>
      <h4 className="mt-2 text-sm font-semibold text-slate-100">{h.title}</h4>
      <p className="mt-1 text-sm leading-relaxed text-slate-400">{h.description}</p>
      <details className="mt-2 group"><summary className="cursor-pointer text-xs text-slate-500 hover:text-slate-300">Evidence ({h.evidence.length})</summary>
        <ul className="mt-1.5 space-y-1 border-l border-ink-600 pl-3 font-mono text-[11px] text-slate-400">{h.evidence.map((e, i) => <li key={i}>{e}</li>)}</ul></details>
    </div>
  );
}

export default function Insights({ a, cfg, onPick }: { a: Analysis | null; cfg: AppConfig | null; onPick: (pageId: string) => void }) {
  const [tab, setTab] = useState<Tab>("Architecture");
  const [cloning, setCloning] = useState(false);
  const [cloneError, setCloneError] = useState<string | null>(null);
  const [cloneOut, setCloneOut] = useState<{ html: string; filename: string; mode: string; note: string } | null>(null);
  const done = a && a.hypotheses.length > 0;
  const group = (cats: Hypothesis["category"][]) => a?.hypotheses.filter((h) => cats.includes(h.category)) ?? [];
  const md = a ? toMarkdown(a) : "";

  async function handleBuildClone() {
    if (!a) return;
    setCloning(true);
    setCloneError(null); setCloneOut(null);
    try {
      const out = await buildClone(a.id);
      setCloneOut(out);
      download(out.filename, out.html, "text/html");
    } catch (e: unknown) {
      setCloneError(e instanceof Error ? e.message : String(e));
    } finally {
      setCloning(false);
    }
  }

  const downloadZip = () => {
    if (!a) return;
    window.location.href = `/api/analyses/${a.id}/clone/zip`;
  };

  const preview = () => {
    if (!cloneOut) return;
    const url = URL.createObjectURL(new Blob([cloneOut.html], { type: "text/html" }));
    window.open(url, "_blank", "noopener");
    window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
  };

  const content = () => {
    if (!a) return <Empty icon="🧩" title="No analysis yet" hint="Architecture hypotheses, workflows and the exportable report appear after an analysis." />;
    if (!done) return <Empty icon="⏳" title="Collecting evidence…" hint="Hypotheses are generated once enough pages have been observed." />;
    if (tab === "Ask AI") return <AskAI a={a} cfg={cfg} onPick={onPick} />;
    if (tab === "Semantic search") return <SemanticSearch a={a} cfg={cfg} onPick={onPick} />;
    if (tab === "Architecture") return <div className="grid gap-3 md:grid-cols-2">{group(["module", "architecture"]).map((h) => <HypCard key={h.id} h={h} />)}</div>;
    if (tab === "Workflows") return group(["workflow"]).length ? <div className="grid gap-3 md:grid-cols-2">{group(["workflow"]).map((h) => <HypCard key={h.id} h={h} />)}</div> : <Empty icon="↝" title="No workflows inferred" hint="More pages or interactions are needed." />;
    if (tab === "Gaps & next steps") return (
      <div className="grid gap-4 md:grid-cols-2">
        <div><div className="label mb-2">Missing information</div><ul className="space-y-2 text-sm text-slate-300">{a.missing_info.map((m, i) => <li key={i} className="flex gap-2"><span className="text-rose-400">✕</span>{m}</li>)}</ul></div>
        <div><div className="label mb-2">Suggested next experiments</div><ul className="space-y-2 text-sm text-slate-300">{a.next_experiments.map((m, i) => <li key={i} className="flex gap-2"><span className="text-signal">▸</span>{m}</li>)}</ul></div>
      </div>
    );
    return <pre className="max-h-[360px] overflow-auto whitespace-pre-wrap rounded-lg border border-ink-700 bg-ink-950 p-4 font-mono text-xs leading-relaxed text-slate-300">{md}</pre>;
  };

  const safe = a?.target_url.replace(/[^a-z0-9]+/gi, "-").replace(/^-|-$/g, "").slice(0, 40) || "report";
  return (
    <section className="card">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-ink-700 px-4 py-2.5">
        <div role="tablist" className="flex gap-1">
          {TABS.map((t) => (
            <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)}
              className={`rounded-md px-3 py-1.5 text-xs font-medium transition ${tab === t ? "bg-signal/10 text-signal" : "text-slate-400 hover:bg-ink-800 hover:text-slate-200"}`}>{t}</button>
          ))}
        </div>
        <div className="flex gap-2">
          {a && (
            <button
              disabled={cloning}
              onClick={handleBuildClone}
              className="btn !px-3 !py-1.5 border border-purple-500/60 bg-purple-500/10 text-xs text-purple-300 hover:bg-purple-500/20 hover:border-purple-400 disabled:opacity-50 disabled:cursor-not-allowed shadow-glow"
              title="Generate a self-contained, working clone with interactive frontend and mock REST backend"
            >
              {cloning ? (
                <span className="flex items-center gap-1.5">
                  <svg className="animate-spin h-3 w-3" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                  </svg>
                  Building Clone…
                </span>
              ) : "⚡ Build Clone App"}
            </button>
          )}
          <button disabled={!done} onClick={() => a && download(`atlas-${safe}.md`, md, "text/markdown")} className="btn !px-3 !py-1.5 border border-ink-600 text-xs text-slate-300 hover:border-signal/50 hover:text-signal">⬇ Markdown</button>
          <button disabled={!done} onClick={() => a && download(`atlas-${safe}.json`, toJson(a), "application/json")} className="btn !px-3 !py-1.5 border border-ink-600 text-xs text-slate-300 hover:border-signal/50 hover:text-signal">⬇ JSON</button>
        </div>
      </div>
      {cloneOut && (
        <div className="mx-4 mt-3 flex flex-wrap items-center justify-between gap-2 rounded-md border border-emerald-700/50 bg-emerald-950/30 px-3 py-2 text-xs text-emerald-300">
          <span><span className="font-semibold">✓ Clone Ready</span> ({cloneOut.filename}) — {cloneOut.note}</span>
          <div className="flex items-center gap-2">
            <button onClick={preview} className="btn !px-2.5 !py-1 border border-emerald-600/50 text-xs text-emerald-200 hover:bg-emerald-900/40">Open preview ↗</button>
            <button onClick={downloadZip} className="btn !px-2.5 !py-1 border border-purple-500/50 bg-purple-900/30 text-xs text-purple-200 hover:bg-purple-900/50">📦 Download Fullstack (.zip)</button>
          </div>
        </div>
      )}
      {cloneError && (
        <div className="mx-4 mt-3 rounded-md border border-rose-700/50 bg-rose-950/40 px-3 py-2 text-xs text-rose-300">
          <span className="font-semibold">Clone failed:</span> {cloneError}
        </div>
      )}
      <div className="p-4">{content()}</div>
    </section>
  );
}
