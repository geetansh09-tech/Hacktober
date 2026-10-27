import type { Analysis, Hypothesis } from "../types";

const tag = (h: Hypothesis) => `${h.provenance.toUpperCase()} · ${h.confidence} confidence`;

export function toMarkdown(a: Analysis): string {
  const L: string[] = [];
  L.push(`# BlackBox Atlas Report — ${a.target_url}`, "");
  if (a.fixture) L.push("> ⚠️ **UI PREVIEW FIXTURE** — sample data for interface development. Not a real observation.", "");
  else if (a.demo) L.push("> 🧪 **DEMO MODE** — observations come from the bundled synthetic app, not a real third-party site.", "");
  L.push(`- Status: ${a.status}`, `- Engine: ${a.engine}`, `- Pages: ${a.pages.length}  ·  Edges: ${a.edges.length}`,
    `- Elapsed: ${a.elapsed_s.toFixed(1)}s  ·  Limits: ${a.limits.max_pages} pages / ${a.limits.time_limit_s}s`, "");
  L.push("## Pages and features discovered", "");
  for (const p of a.pages) {
    L.push(`### ${p.title || p.path} — \`${p.path}\``);
    if (p.headings.length) L.push(`- Headings: ${p.headings.join(" | ")}`);
    if (p.buttons.length) L.push(`- Buttons: ${p.buttons.join(", ")}`);
    if (p.forms.length) L.push(`- Forms: ${p.forms.map((f) => `${f.method.toUpperCase()} ${f.action || "(self)"} [${f.fields.join(", ")}]`).join("; ")}`);
    L.push(`- Outgoing links: ${p.links.length}`, "");
  }
  L.push("## Navigation graph", "", "```mermaid", "graph LR");
  const name = (id: string) => a.pages.find((p) => p.id === id)?.path ?? id;
  for (const e of a.edges)
    L.push(`  ${e.source}["${name(e.source)}"] ${e.provenance === "observed" ? "-->" : "-.->"}|${e.action.replace(/[|"]/g, "'")}| ${e.target}["${name(e.target)}"]`);
  L.push("```", "");
  for (const [cat, title] of [["module", "Candidate modules"], ["workflow", "User workflows"], ["architecture", "Architectural hypotheses"]] as const) {
    const hs = a.hypotheses.filter((h) => h.category === cat);
    if (!hs.length) continue;
    L.push(`## ${title}`, "");
    for (const h of hs) L.push(`### ${h.title}  _(${tag(h)})_`, h.description, "", "Evidence:", ...h.evidence.map((e) => `- ${e}`), "");
  }
  L.push("## Observed vs inferred", "",
    `- Observed relationships: ${a.edges.filter((e) => e.provenance === "observed").length}`,
    `- Inferred relationships: ${a.edges.filter((e) => e.provenance === "inferred").length}`, "");
  L.push("## Missing information", "", ...a.missing_info.map((m) => `- ${m}`), "");
  L.push("## Suggested next experiments", "", ...a.next_experiments.map((m) => `- ${m}`), "");
  return L.join("\n");
}

export const toJson = (a: Analysis) => JSON.stringify(a, null, 2);

export function download(filename: string, text: string, mime: string) {
  const url = URL.createObjectURL(new Blob([text], { type: mime }));
  const el = Object.assign(document.createElement("a"), { href: url, download: filename });
  el.click();
  URL.revokeObjectURL(url);
}
