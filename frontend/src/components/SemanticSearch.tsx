import { useState } from "react";
import { searchPages } from "../api";
import type { Analysis, AppConfig, SearchHit } from "../types";
import { Empty } from "./ui";

interface Props { a: Analysis; cfg: AppConfig | null; onPick: (pageId: string) => void }

export default function SemanticSearch({ a, cfg, onPick }: Props) {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<SearchHit[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const emb = a.embeddings;
  const ready = !!cfg?.embeddings.enabled && !!emb?.pages_embedded && a.id !== "fixture";

  if (!ready) {
    const why = a.id === "fixture" ? "Semantic search is unavailable for the UI preview fixture (no backend data)."
      : !cfg ? "Backend config unavailable."
      : !cfg.embeddings.enabled ? "Set NVIDIA_API_KEY in the backend .env, restart, and re-run an analysis to enable NVIDIA embeddings."
      : emb?.error ? `Embedding step failed for this analysis: ${emb.error}` : "This analysis ran before embeddings were enabled — run it again.";
    return <Empty icon="🧭" title="Semantic search is off" hint={why} />;
  }

  const run = async () => {
    if (!q.trim()) return;
    setBusy(true); setErr(null);
    try { setHits((await searchPages(a.id, q.trim())).results); } catch (e) { setErr((e as Error).message); setHits(null); }
    finally { setBusy(false); }
  };

  return (
    <div>
      <div className="flex gap-2">
        <input value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && run()} maxLength={300}
          placeholder="Describe a feature, e.g. “where do users pay?”" aria-label="Semantic search query"
          className="min-w-0 flex-1 rounded-md border border-ink-600 bg-ink-950 px-3 py-2 text-sm text-slate-200 outline-none focus:border-signal/60" />
        <button onClick={run} disabled={busy || !q.trim()} className="btn border border-signal/40 bg-signal/10 text-signal disabled:opacity-40">{busy ? "Searching…" : "Search"}</button>
      </div>
      <p className="mt-2 text-[11px] text-slate-500">Ranked by cosine similarity of NVIDIA embeddings ({emb?.model}) over observed page text. Similarity is a hint, not proof.</p>
      {err && <div role="alert" className="mt-3 rounded-md border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-xs text-rose-300">✖ {err}</div>}
      {hits && (hits.length === 0 ? <Empty icon="∅" title="No results" /> :
        <ul className="mt-3 space-y-1.5">{hits.map((h) => (
          <li key={h.page_id}><button onClick={() => onPick(h.page_id)} className="flex w-full items-center justify-between gap-3 rounded-md border border-ink-700 bg-ink-950/60 px-3 py-2 text-left hover:border-signal/50">
            <span className="min-w-0"><span className="block truncate font-mono text-xs text-slate-200">{h.path}</span><span className="block truncate text-[11px] text-slate-500">{h.title}</span></span>
            <span className="chip border-ink-600 text-slate-300">{h.score.toFixed(2)}</span></button></li>))}</ul>)}
    </div>
  );
}
