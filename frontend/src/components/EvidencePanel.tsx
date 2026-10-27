import type { Analysis } from "../types";
import { Empty, ProvChip, Section } from "./ui";

const pathOf = (u: string) => { try { const x = new URL(u); return x.pathname + x.search; } catch { return u; } };
const Mono = ({ children }: { children: React.ReactNode }) => <span className="rounded bg-ink-800 px-1.5 py-0.5 font-mono text-[11px] text-slate-300">{children}</span>;

export default function EvidencePanel({ a, selected }: { a: Analysis | null; selected: { kind: "node" | "edge"; id: string } | null }) {
  const body = (() => {
    if (!a || !selected) return <Empty icon="🔎" title="Select a node or edge" hint="Click a page to see its headings, buttons, forms and links. Click an edge to see the evidence for that relationship." />;
    if (selected.kind === "node") {
      const p = a.pages.find((x) => x.id === selected.id);
      if (!p) return null;
      const inc = a.edges.filter((e) => e.target === p.id).length, out = a.edges.filter((e) => e.source === p.id).length;
      return (
        <div className="space-y-4">
          <div>
            <div className="flex items-center gap-2"><ProvChip p="observed" />{p.status_code && <Mono>HTTP {p.status_code}</Mono>}</div>
            <h3 className="mt-2 text-base font-semibold text-slate-100">{p.title || "(untitled)"}</h3>
            <a className="break-all font-mono text-xs text-signal/80">{p.url}</a>
            <div className="mt-1 font-mono text-[11px] text-slate-500">in-degree {inc} · out-degree {out}</div>
          </div>
          <Section title={`Headings (${p.headings.length})`}>{p.headings.length ? <ul className="space-y-1 text-sm text-slate-300">{p.headings.map((h, i) => <li key={i}>› {h}</li>)}</ul> : <p className="text-xs text-slate-600">None observed</p>}</Section>
          <Section title={`Buttons (${p.buttons.length})`}><div className="flex flex-wrap gap-1.5">{p.buttons.length ? p.buttons.map((b, i) => <Mono key={i}>{b}</Mono>) : <span className="text-xs text-slate-600">None observed</span>}</div></Section>
          <Section title={`Forms (${p.forms.length})`}>
            {p.forms.length ? p.forms.map((f, i) => (
              <div key={i} className="mb-2 rounded-lg border border-ink-700 bg-ink-950/60 p-2.5 font-mono text-xs">
                <span className="text-infer">{f.method.toUpperCase()}</span> <span className="text-slate-300">{f.action || "(self)"}</span>
                <div className="mt-1.5 flex flex-wrap gap-1">{f.fields.map((x) => <Mono key={x}>{x}</Mono>)}</div>
              </div>)) : <p className="text-xs text-slate-600">None observed</p>}
          </Section>
          {p.inaccessible && <p className="rounded-lg border border-rose-500/30 bg-rose-500/5 p-2.5 text-xs text-rose-300">Page appears access-restricted (HTTP {p.status_code}). Atlas does not attempt to bypass it.</p>}
          {!!p.requests?.length && <Section title={`Network on load (${p.requests.length})`}><ul className="space-y-1 font-mono text-[11px]">{p.requests.map((r, i) => <li key={i} className="flex gap-2"><span className="text-infer">{r.method}</span><span className="truncate text-slate-300">{pathOf(r.url)}</span>{r.blocked && <span className="text-rose-400">blocked</span>}</li>)}</ul></Section>}
          {!!p.interactions?.length && <Section title={`Interactions (${p.interactions.length})`}>{p.interactions.map((x, i) => (
            <div key={i} className="mb-2 rounded-lg border border-ink-700 bg-ink-950/60 p-2.5 text-xs">
              <div className="text-slate-200">click <Mono>{x.button}</Mono> <span className="text-slate-500">· DOM text Δ {x.dom_text_delta}</span></div>
              {x.requests.map((r, j) => <div key={j} className="mt-1 font-mono text-[11px]"><span className="text-infer">{r.method}</span> <span className="text-slate-300">{pathOf(r.url)}</span> {r.blocked && <span className="text-rose-400">— {r.blocked}</span>}</div>)}
              {!x.requests.length && <div className="mt-1 text-slate-500">no network requests</div>}
            </div>))}</Section>}
          {!!p.signals?.length && <Section title="Technology signals"><ul className="space-y-1 font-mono text-[11px] text-slate-400">{p.signals.map((s, i) => <li key={i}>{s}</li>)}</ul></Section>}
          <Section title={`Links (${p.links.length})`}>
            <ul className="space-y-1 font-mono text-xs">{p.links.slice(0, 12).map((l, i) => <li key={i} className="flex justify-between gap-2"><span className="truncate text-slate-300">{l.text || "(no text)"}</span><span className="truncate text-slate-500">{l.href}</span></li>)}</ul>
          </Section>
        </div>
      );
    }
    const e = a.edges.find((x) => x.id === selected.id);
    if (!e) return null;
    const s = a.pages.find((p) => p.id === e.source), t = a.pages.find((p) => p.id === e.target);
    return (
      <div className="space-y-4">
        <ProvChip p={e.provenance} />
        <div className="flex items-center gap-2 font-mono text-sm"><Mono>{s?.path}</Mono><span className={e.provenance === "observed" ? "text-signal" : "text-infer"}>{e.provenance === "observed" ? "──▶" : "┄┄▶"}</span><Mono>{t?.path}</Mono></div>
        <Section title="Action"><p className="text-sm text-slate-200">{e.action}</p></Section>
        <Section title="Evidence"><ul className="space-y-2">{e.evidence.map((x, i) => <li key={i} className="rounded-lg border border-ink-700 bg-ink-950/60 p-2.5 text-xs text-slate-300">{x}</li>)}</ul></Section>
        {e.provenance === "inferred" && <p className="rounded-lg border border-infer/30 bg-infer/5 p-2.5 text-xs text-infer">This relationship was not directly observed. Treat as a hypothesis until confirmed by a follow-up experiment.</p>}
      </div>
    );
  })();
  return (
    <aside className="card flex h-[520px] flex-col lg:h-[620px]">
      <div className="border-b border-ink-700 px-4 py-3"><span className="label">Evidence panel</span></div>
      <div className="flex-1 overflow-y-auto p-4">{body}</div>
    </aside>
  );
}
