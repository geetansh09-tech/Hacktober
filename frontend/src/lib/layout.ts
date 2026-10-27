import type { Analysis } from "../types";

/** Layered layout by BFS depth from the first page. Unreachable nodes go in the last column. */
export function layout(a: Analysis): Record<string, { x: number; y: number }> {
  const depth = new Map<string, number>();
  const adj = new Map<string, string[]>();
  a.edges.forEach((e) => adj.set(e.source, [...(adj.get(e.source) ?? []), e.target]));
  const root = a.pages[0]?.id;
  if (root) {
    depth.set(root, 0);
    const q = [root];
    while (q.length) {
      const n = q.shift()!;
      for (const m of adj.get(n) ?? []) if (!depth.has(m)) { depth.set(m, depth.get(n)! + 1); q.push(m); }
    }
  }
  const max = Math.max(0, ...depth.values());
  a.pages.forEach((p) => { if (!depth.has(p.id)) depth.set(p.id, max + 1); });
  const cols = new Map<number, string[]>();
  a.pages.forEach((p) => cols.set(depth.get(p.id)!, [...(cols.get(depth.get(p.id)!) ?? []), p.id]));
  const pos: Record<string, { x: number; y: number }> = {};
  cols.forEach((ids, d) => ids.forEach((id, i) => { pos[id] = { x: d * 290, y: (i - (ids.length - 1) / 2) * 135 }; }));
  return pos;
}
