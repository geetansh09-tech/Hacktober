// API contract shared with the (upcoming) FastAPI backend.
export type Status = "queued" | "running" | "completed" | "failed";
export type Provenance = "observed" | "inferred";
export type Confidence = "high" | "medium" | "low";

export interface NetReq { method: string; url: string; type: string; blocked: string | null }

export interface PageObs {
  id: string;
  url: string;
  title: string;
  path: string;
  status_code?: number;
  headings: string[];
  links: { text: string; href: string }[];
  buttons: string[];
  forms: { action: string; method: string; fields: string[] }[];
  requests?: NetReq[];
  interactions?: { button: string; requests: NetReq[]; dom_text_delta: number; navigated: boolean }[];
  signals?: string[];
  headers?: Record<string, string>;
  inaccessible?: boolean;
}

export interface EdgeObs {
  id: string;
  source: string;
  target: string;
  provenance: Provenance;
  action: string; // e.g. "click link 'Pricing'"
  evidence: string[];
  global_nav?: boolean; // header/footer link repeated across most pages
}

export interface Hypothesis {
  id: string;
  category: "module" | "workflow" | "architecture";
  title: string;
  description: string;
  provenance: Provenance;
  confidence: Confidence;
  evidence: string[]; // references to page/edge ids or short observation strings
}

export interface Analysis {
  id: string;
  target_url: string;
  status: Status;
  demo: boolean;
  fixture?: boolean; // true only for the UI-preview fixture
  started_at: string;
  elapsed_s: number;
  limits: { max_pages: number; time_limit_s: number };
  progress: { pages_discovered: number; pages_visited: number; message: string };
  pages: PageObs[];
  edges: EdgeObs[];
  hypotheses: Hypothesis[];
  missing_info: string[];
  next_experiments: string[];
  engine: "rules" | "llm+rules";
  embeddings?: { enabled: boolean; model?: string; pages_embedded?: number; groups?: number; error?: string };
  error?: string;
}

export interface StartRequest {
  url: string;
  demo: boolean;
  max_pages: number;
  time_limit_s: number;
}

export interface AppConfig { embeddings: { enabled: boolean; model: string | null; provider: string }; llm: boolean }
export interface SearchHit { page_id: string; path: string; title: string; score: number }
