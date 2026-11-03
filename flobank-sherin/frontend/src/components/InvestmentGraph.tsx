import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { Background, ReactFlow, type Edge, type Node } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useApi } from "../lib/api";
import { Spinner } from "./ui";

const DEC: Record<string, string> = { PASS: "#13795B", REVIEW: "#B8913A", BLOCK: "#B4413C", INSUFFICIENT_DATA: "#7C8C99" };

/** Investment web graph: portfolios → sectors, with pending trade proposals coloured by Guardian decision. */
export function InvestmentGraph({ height = 360, compact = false }: { height?: number; compact?: boolean }) {
  const { data } = useApi<any>("/guardian/graph");
  const props = useApi<any[]>("/guardian/proposals");
  const nav = useNavigate();
  const graph = useMemo(() => {
    if (!data) return null;
    const decisions = new Map((props.data ?? []).map((p) => [`proposal:${p.id}`, p.decision]));
    const ports = data.nodes.filter((n: any) => n.type === "portfolio");
    const sectors = data.nodes.filter((n: any) => n.type === "sector");
    const proposals = data.nodes.filter((n: any) => n.type === "proposal");
    // compact = stacked rows for a narrow side panel; otherwise three columns left-to-right.
    const secRows = Math.ceil(sectors.length / 3);
    const pos = {
      port: (i: number) => (compact ? { x: i * 150, y: 0 } : { x: 0, y: 40 + i * 130 }),
      sec: (i: number) => (compact ? { x: (i % 3) * 150, y: 90 + Math.floor(i / 3) * 42 } : { x: 230, y: i * 38 }),
      prop: (i: number) => (compact ? { x: (i % 2) * 225, y: 130 + secRows * 42 + Math.floor(i / 2) * 70 } : { x: 420, y: 20 + i * 62 }),
    };
    const nodes: Node[] = [
      ...ports.map((p: any, i: number) => ({ id: p.id, position: pos.port(i), data: { label: p.label.replace("FLO ", "") },
        style: { background: "#0B3D2E", color: "#fff", borderRadius: 14, fontSize: compact ? 12 : 11, fontWeight: 700, width: compact ? 140 : 150, border: "none" } })),
      ...sectors.map((s: any, i: number) => ({ id: s.id, position: pos.sec(i), data: { label: s.label }, style: { background: "#E6F4EE", borderRadius: 999, fontSize: compact ? 12 : 10, width: compact ? 135 : 110, border: "1px solid #BFE3D2", padding: 4 } })),
      ...proposals.map((p: any, i: number) => { const d = decisions.get(p.id) ?? p.decision; return { id: p.id, position: pos.prop(i), data: { label: <span title={d ?? ""}>{p.label}<br /><b style={{ color: DEC[d] ?? "#5B6B65" }}>{d ?? "not evaluated"}</b></span> },
        style: { background: "#fff", borderRadius: 12, fontSize: compact ? 12 : 10, width: compact ? 210 : 170, border: `2px solid ${DEC[d] ?? "#DCE8E2"}`, cursor: "pointer" } }; }),
    ];
    const maxV = Math.max(...data.edges.map((e: any) => e.value), 1);
    const edges: Edge[] = data.edges.map((e: any, i: number) => ({ id: `e${i}`, source: e.source.startsWith("proposal:") ? e.target : e.source, target: e.source.startsWith("proposal:") ? e.source : e.target,
      style: { stroke: e.source.startsWith("proposal:") ? "#B8913A" : "#9CC9B4", strokeWidth: 1 + 5 * Math.sqrt(e.value / maxV), opacity: 0.75 } }));
    return { nodes, edges };
  }, [data, props.data, compact]);
  if (!graph) return <Spinner label="Loading investment graph" />;
  return (
    <div style={{ height }} className="rounded-2xl border border-line bg-white" data-testid="investment-graph">
      <ReactFlow nodes={graph.nodes} edges={graph.edges} fitView nodesConnectable={false} minZoom={0.2}
        onNodeClick={(_, n) => n.id.startsWith("proposal:") && nav(`/guardian?proposal=${n.id.slice(9)}`)}>
        <Background color="#EEF4F1" gap={18} />
      </ReactFlow>
    </div>
  );
}
