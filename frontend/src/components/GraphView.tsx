import { useEffect, useMemo, useState } from "react";
import { Background, BackgroundVariant, Controls, Handle, MarkerType, MiniMap, Position, ReactFlow, useEdgesState, useNodesState } from "@xyflow/react";
import type { Edge, Node, NodeProps } from "@xyflow/react";
import type { Analysis } from "../types";
import { layout } from "../lib/layout";
import { Empty } from "./ui";

type PageNodeData = { path: string; title: string; counts: string; selected: boolean };

function PageNode({ data }: NodeProps<Node<PageNodeData>>) {
  return (
    <div className={`w-[200px] rounded-lg border bg-ink-850 px-3 py-2.5 transition ${data.selected ? "border-signal shadow-glow" : "border-ink-600 hover:border-slate-500"}`}>
      <Handle type="target" position={Position.Left} className="!h-2 !w-2 !border-ink-600 !bg-signal" />
      <div className="truncate font-mono text-[11px] text-signal">{data.path}</div>
      <div className="mt-0.5 truncate text-sm font-medium text-slate-100">{data.title || "(untitled)"}</div>
      <div className="mt-1 font-mono text-[10px] text-slate-500">{data.counts}</div>
      <Handle type="source" position={Position.Right} className="!h-2 !w-2 !border-ink-600 !bg-signal" />
    </div>
  );
}
const nodeTypes = { page: PageNode };

interface Props {
  a: Analysis | null;
  selected: { kind: "node" | "edge"; id: string } | null;
  onSelect: (s: { kind: "node" | "edge"; id: string } | null) => void;
}

export default function GraphView({ a, selected, onSelect }: Props) {
  const [showNav, setShowNav] = useState(false);
  const hiddenCount = a?.edges.filter((e) => e.global_nav).length ?? 0;
  const built = useMemo(() => {
    if (!a) return { nodes: [] as Node<PageNodeData>[], edges: [] as Edge[] };
    const pos = layout(a);
    const nodes: Node<PageNodeData>[] = a.pages.map((p) => ({
      id: p.id, type: "page", position: pos[p.id] ?? { x: 0, y: 0 },
      data: { path: p.path, title: p.title, counts: `${p.links.length} links · ${p.buttons.length} btn · ${p.forms.length} forms`, selected: false },
    }));
    const edges: Edge[] = a.edges.filter((e) => showNav || !e.global_nav).map((e) => {
      const obs = e.provenance === "observed";
      const c = obs ? "#22d3ee" : "#fbbf24";
      return {
        id: e.id, source: e.source, target: e.target, type: "smoothstep", animated: !obs,
        label: e.action.length > 28 ? e.action.slice(0, 27) + "…" : e.action,
        style: { stroke: c, strokeWidth: 1.6, strokeDasharray: obs ? undefined : "6 5" },
        markerEnd: { type: MarkerType.ArrowClosed, color: c },
        labelStyle: { fill: "#94a3b8", fontSize: 10, fontFamily: "ui-monospace, monospace" },
        labelBgStyle: { fill: "#0a0d13", fillOpacity: 0.95 }, labelBgPadding: [4, 2] as [number, number], labelBgBorderRadius: 4,
        interactionWidth: 20,
      };
    });
    return { nodes, edges };
  }, [a, showNav]);

  const [nodes, setNodes, onNodesChange] = useNodesState(built.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(built.edges);
  useEffect(() => { setNodes(built.nodes); setEdges(built.edges); }, [built, setNodes, setEdges]);
  useEffect(() => {
    setNodes((ns) => ns.map((n) => ({ ...n, data: { ...n.data, selected: selected?.kind === "node" && selected.id === n.id } })));
    setEdges((es) => es.map((e) => (selected?.kind === "edge" && selected.id === e.id ? { ...e, style: { ...e.style, strokeWidth: 3 } } : { ...e, style: { ...e.style, strokeWidth: 1.6 } })));
  }, [selected, setNodes, setEdges]);

  const empty = !a || a.pages.length === 0;
  return (
    <div className="card relative h-[520px] overflow-hidden lg:h-[620px]">
      <div className="absolute left-3 top-3 z-10 flex flex-wrap items-center gap-3 rounded-lg border border-ink-700 bg-ink-900/90 px-3 py-1.5 text-[11px] text-slate-400 backdrop-blur">
        <span className="label !text-slate-400">Behavioral graph</span>
        <span className="flex items-center gap-1.5"><span className="inline-block h-0.5 w-5 bg-signal" />observed</span>
        <span className="flex items-center gap-1.5"><span className="inline-block w-5 border-t-2 border-dashed border-infer" />inferred</span>
        {hiddenCount > 0 && <button onClick={() => setShowNav(!showNav)} className="rounded border border-ink-600 px-1.5 py-0.5 text-slate-300 hover:border-signal/50 hover:text-signal">{showNav ? "Hide" : "Show"} {hiddenCount} global-nav links</button>}
      </div>
      {empty ? (
        <Empty icon="🕸" title={a ? "Waiting for the first page…" : "No graph yet"} hint="Start an analysis and pages will appear here as the browser discovers them. Edges are labelled with the action that was observed." />
      ) : (
        <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} onNodesChange={onNodesChange} onEdgesChange={onEdgesChange}
          onNodeClick={(_, n) => onSelect({ kind: "node", id: n.id })} onEdgeClick={(_, e) => onSelect({ kind: "edge", id: e.id })} onPaneClick={() => onSelect(null)}
          fitView fitViewOptions={{ padding: 0.25 }} minZoom={0.2} proOptions={{ hideAttribution: true }} colorMode="dark" nodesConnectable={false}>
          <Background variant={BackgroundVariant.Dots} gap={22} size={1} color="#1b2230" />
          <Controls showInteractive={false} />
          <MiniMap pannable zoomable nodeColor="#22d3ee" maskColor="rgba(6,8,12,.7)" />
        </ReactFlow>
      )}
    </div>
  );
}
