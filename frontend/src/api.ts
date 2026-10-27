import type { Analysis, AppConfig, AskResult, ChatTurn, SearchHit, StartRequest } from "./types";

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

export const buildClone = (id: string, mode: "auto" | "ai" | "static" = "auto") =>
  fetch(`/api/analyses/${id}/clone`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ mode }) })
    .then((r) => j<{ html: string; filename: string; mode: "ai" | "static"; note: string; zip_available?: boolean }>(r));

export const cloneInstant = (url: string, demo = false) =>
  fetch("/api/clone-instant", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ url, demo }) })
    .then((r) => j<{ id: string; html: string; filename: string; mode: "ai" | "static"; note: string; zip_url: string; analysis?: Analysis }>(r));

export const getCloneZipUrl = (id: string) => `/api/analyses/${id}/clone/zip`;

export const askQuestion = (id: string, question: string, history: ChatTurn[]) =>
  fetch(`/api/analyses/${id}/ask`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question, history }) })
    .then((r) => j<AskResult>(r));
