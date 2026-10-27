import { Fragment, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { askQuestion } from "../api";
import type { Analysis, AppConfig, AskSource, ChatTurn } from "../types";
import { Empty } from "./ui";

interface Msg extends ChatTurn { sources?: AskSource[]; retrieval?: string; model?: string; error?: boolean }
interface Props { a: Analysis; cfg: AppConfig | null; onPick: (pageId: string) => void }

const SUGGESTIONS = [
  "Give me a one-paragraph summary of this app.",
  "Walk me through the main user flow step by step.",
  "Which pages handle authentication and what do they collect?",
  "What parts of the blueprint are only inferred, and why?",
  "What should I explore next to fill the gaps?",
];

// Tiny, safe markdown renderer (no HTML injection): **bold**, `code`, "- " bullets, "1." lists, paragraphs.
function inline(text: string, paths: Map<string, string>, onPick: (id: string) => void): ReactNode[] {
  return text.split(/(`[^`]+`|\*\*[^*]+\*\*)/g).filter(Boolean).map((t, i) => {
    if (t.startsWith("**") && t.endsWith("**") && t.length > 4) return <strong key={i} className="font-semibold text-slate-100">{t.slice(2, -2)}</strong>;
    if (t.startsWith("`") && t.endsWith("`") && t.length > 2) {
      const code = t.slice(1, -1), id = paths.get(code);
      return id
        ? <button key={i} onClick={() => onPick(id)} title="Select this page in the graph" className="rounded bg-signal/10 px-1 font-mono text-[12px] text-signal hover:bg-signal/20">{code}</button>
        : <code key={i} className="rounded bg-ink-800 px-1 font-mono text-[12px] text-slate-200">{code}</code>;
    }
    return <Fragment key={i}>{t}</Fragment>;
  });
}

function Markdown({ text, a, onPick }: { text: string; a: Analysis; onPick: (id: string) => void }) {
  const paths = new Map(a.pages.map((p) => [p.path, p.id]));
  const blocks: ReactNode[] = [];
  let list: { ordered: boolean; items: string[] } | null = null;
  const flush = () => {
    if (!list) return;
    const Tag = list.ordered ? "ol" : "ul";
    blocks.push(<Tag key={blocks.length} className={`my-1.5 space-y-1 pl-5 ${list.ordered ? "list-decimal" : "list-disc"}`}>{list.items.map((it, i) => <li key={i}>{inline(it, paths, onPick)}</li>)}</Tag>);
    list = null;
  };
  for (const raw of text.split("\n")) {
    const line = raw.trimEnd();
    const b = line.match(/^\s*[-*•]\s+(.*)/), n = line.match(/^\s*\d+[.)]\s+(.*)/);
    if (b || n) {
      const ordered = !!n;
      if (!list || list.ordered !== ordered) { flush(); list = { ordered, items: [] }; }
      list.items.push((b ?? n)![1]);
    } else {
      flush();
      if (line.trim()) blocks.push(<p key={blocks.length} className="my-1.5">{inline(line.replace(/^#{1,6}\s+/, ""), paths, onPick)}</p>);
    }
  }
  flush();
  return <div className="text-sm leading-relaxed text-slate-300">{blocks}</div>;
}

export default function AskAI({ a, cfg, onPick }: Props) {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const end = useRef<HTMLDivElement>(null);
  const abort = useRef(0);
  useEffect(() => { setMsgs([]); abort.current++; setBusy(false); }, [a.id]);  // new analysis → fresh conversation
  useEffect(() => { end.current?.scrollIntoView({ block: "nearest", behavior: "smooth" }); }, [msgs, busy]);

  if (a.id === "fixture") return <Empty icon="💬" title="Ask AI is unavailable for the UI preview fixture" hint="Run a real or demo analysis so the backend has data to answer from." />;
  if (cfg && !cfg.qa?.enabled) return <Empty icon="🔑" title="Ask AI is off" hint="Put NVIDIA_API_KEY=nvapi-… in the project .env and restart the backend. The same key powers embeddings and chat." />;
  if (!cfg) return <Empty icon="💬" title="Backend config unavailable" hint="Start the backend to use Ask AI." />;
  if (a.status !== "completed") return <Empty icon="⏳" title="Waiting for the analysis to finish" hint="You can ask questions as soon as the flowchart and blueprint are complete." />;

  const send = async (text: string) => {
    const question = text.trim();
    if (!question || busy) return;
    const history = msgs.filter((m) => !m.error).map(({ role, content }) => ({ role, content }));
    const ticket = ++abort.current;
    setMsgs((m) => [...m, { role: "user", content: question }]); setQ(""); setBusy(true);
    try {
      const r = await askQuestion(a.id, question, history);
      if (ticket === abort.current) setMsgs((m) => [...m, { role: "assistant", content: r.answer, sources: r.sources, retrieval: r.retrieval, model: r.model }]);
    } catch (e) {
      if (ticket === abort.current) setMsgs((m) => [...m, { role: "assistant", content: (e as Error).message, error: true }]);
    } finally { if (ticket === abort.current) setBusy(false); }
  };

  return (
    <div>
      <div className="max-h-[420px] min-h-[160px] space-y-3 overflow-y-auto pr-1" aria-live="polite">
        {msgs.length === 0 && (
          <div>
            <p className="text-sm text-slate-400">Ask anything about this app's <b className="text-slate-200">flowchart</b> and <b className="text-slate-200">blueprint</b>. Answers come from the observed pages, edges and hypotheses of this analysis.</p>
            <div className="mt-3 flex flex-wrap gap-2">{SUGGESTIONS.map((s) => (
              <button key={s} onClick={() => send(s)} className="rounded-full border border-ink-600 px-3 py-1 text-xs text-slate-300 hover:border-signal/50 hover:text-signal">{s}</button>))}</div>
          </div>)}
        {msgs.map((m, i) => m.role === "user"
          ? <div key={i} className="flex justify-end"><div className="max-w-[85%] rounded-lg border border-signal/30 bg-signal/10 px-3 py-2 text-sm text-slate-100">{m.content}</div></div>
          : <div key={i} className={`rounded-lg border px-3.5 py-2.5 ${m.error ? "border-rose-500/40 bg-rose-500/10" : "border-ink-700 bg-ink-950/60"}`}>
              {m.error ? <p role="alert" className="text-sm text-rose-300">✖ {m.content}</p> : <Markdown text={m.content} a={a} onPick={onPick} />}
              {!!m.sources?.length && (
                <div className="mt-2 flex flex-wrap items-center gap-1.5 border-t border-ink-700 pt-2">
                  <span className="label">Pages consulted</span>
                  {m.sources.map((s) => <button key={s.page_id} onClick={() => onPick(s.page_id)} title={s.title} className="chip border-ink-600 text-slate-300 hover:border-signal/50 hover:text-signal">{s.path}</button>)}
                  <span className="ml-auto text-[10px] text-slate-600">{m.retrieval === "embeddings" ? "NVIDIA embeddings retrieval" : "keyword retrieval"} · {m.model}</span>
                </div>)}
            </div>)}
        {busy && <div className="flex items-center gap-2 text-xs text-slate-500"><span className="inline-block h-2 w-2 animate-pulse rounded-full bg-signal" />Thinking…</div>}
        <div ref={end} />
      </div>
      <div className="mt-3 flex gap-2">
        <input value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && send(q)} maxLength={1000} disabled={busy}
          placeholder="e.g. “How does a user get from the catalog to checkout?”" aria-label="Ask a question about this analysis"
          className="min-w-0 flex-1 rounded-md border border-ink-600 bg-ink-950 px-3 py-2 text-sm text-slate-200 outline-none focus:border-signal/60 disabled:opacity-60" />
        <button onClick={() => send(q)} disabled={busy || !q.trim()} className="btn border border-signal/40 bg-signal/10 text-signal disabled:opacity-40">{busy ? "Asking…" : "Ask"}</button>
        {msgs.length > 0 && <button onClick={() => { abort.current++; setMsgs([]); setBusy(false); }} className="btn border border-ink-600 text-slate-400 hover:text-slate-200">Clear</button>}
      </div>
      <p className="mt-2 text-[11px] text-slate-500">Powered by NVIDIA ({cfg.qa?.model}). Answers are generated from observations and can be wrong — hypotheses stay labelled inferred. Click a <code className="font-mono text-signal">/path</code> to highlight it in the graph.</p>
    </div>
  );
}
