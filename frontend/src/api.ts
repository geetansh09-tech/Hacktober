import type { Analysis, AppConfig, SearchHit, StartRequest } from "./types";

async function j<T>(r: Response): Promise<T> {
  if (!r.ok) {
    let detail = r.statusText;
    try { detail = (await r.json()).detail ?? detail; } catch { /* ignore */ }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return r.json();
}

export const startAnalysis = (req: StartRequest) =>
  fetch("/api/analyses", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(req) })
    .then((r) => j<{ id: string }>(r));

export const getAnalysis = (id: string) => fetch(`/api/analyses/${id}`).then((r) => j<Analysis>(r));
export const cancelAnalysis = (id: string) => fetch(`/api/analyses/${id}/cancel`, { method: "POST" }).then((r) => j<unknown>(r));
export const listAnalyses = () => fetch("/api/analyses").then((r) => j<Pick<Analysis, "id" | "target_url" | "status" | "demo" | "started_at">[]>(r));
export const getConfig = () => fetch("/api/config").then((r) => j<AppConfig>(r));
export const searchPages = (id: string, query: string) =>
  fetch(`/api/analyses/${id}/search`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ query }) })
    .then((r) => j<{ model: string; results: SearchHit[] }>(r));

export async function buildClone(id: string): Promise<{ html: string; filename: string }> {
  const r = await fetch(`/api/analyses/${id}/clone`, { method: "POST" });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}
