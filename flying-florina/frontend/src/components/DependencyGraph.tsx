import { Background, Controls, MiniMap, ReactFlow, type Edge, type Node } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useMemo, useState } from "react";
import type { GraphEdge, GraphNode } from "@/lib/types";

const TYPE_COLOR: Record<string, string> = { system: "#5C35B7", api: "#0F8B8D", table: "#3B6FB6", view: "#0F8B8D", unknown: "#B7791F", file: "#D7B46A", event: "#A78BFA", entity: "#3B6FB6" };

export function DependencyGraph({ nodes, edges, height = 460 }: { nodes: GraphNode[]; edges: GraphEdge[]; height?: number }) {
  const [selected, setSelected] = useState<GraphNode | null>(null);
  const flow = useMemo(() => {
    const byType: Record<string, GraphNode[]> = {};
    nodes.forEach((n) => (byType[n.type] ??= []).push(n));
    const order = ["system", "api", "entity", "view", "table", "file", "event", "unknown"];
    const ns: Node[] = [];
    let col = 0;
    order.forEach((t) => {
      const c = t === "system" ? 0 : col++;
      (byType[t] ?? []).forEach((n, row) =>
        ns.push({
          id: n.id,
          // Systems in a 4-wide grid on top; each other node type gets its own column below.
          position: t === "system" ? { x: (row % 4) * 250, y: Math.floor(row / 4) * 120 } : { x: c * 250, y: 420 + row * 80 },
          data: { label: n.label },
          style: { fontSize: 10, width: 200, borderRadius: 10, border: `2px ${t === "unknown" ? "dashed" : "solid"} ${TYPE_COLOR[t] ?? "#999"}`, background: "var(--panel)", color: "var(--text)" },
        }),
      );
    });
    const ids = new Set(ns.map((n) => n.id));
    const es: Edge[] = edges.filter((e) => ids.has(e.source) && ids.has(e.target)).map((e) => ({ id: e.id, source: e.source, target: e.target, label: e.label, labelStyle: { fontSize: 9 } }));
    return { ns, es };
  }, [nodes, edges]);
  return (
    <div className="grid gap-3 lg:grid-cols-[1fr_280px]">
      <div style={{ height }} className="rounded-lg border border-token" data-testid="dependency-graph">
        <ReactFlow nodes={flow.ns} edges={flow.es} fitView onNodeClick={(_, n) => setSelected(nodes.find((x) => x.id === n.id) ?? null)} proOptions={{ hideAttribution: true }}>
          <Background gap={18} />
          <MiniMap pannable zoomable />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>
      <div className="panel p-3 text-xs">
        <div className="mb-2 flex flex-wrap gap-2">
          {Object.entries(TYPE_COLOR).map(([t, c]) => (
            <span key={t} className="inline-flex items-center gap-1">
              <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: c }} />
              {t}
            </span>
          ))}
        </div>
        {selected ? (
          <div className="space-y-1">
            <div className="text-sm font-semibold">{selected.label}</div>
            <div>Type: {selected.type}</div>
            <div>Confidence: {selected.confidence ?? "-"}</div>
            {selected.criticality && <div>Criticality: {selected.criticality}</div>}
            {selected.why && <div>Why it matters: {selected.why}</div>}
            <div className="muted">Evidence: {(selected.evidence ?? []).join(", ") || "none (unknown)"}</div>
          </div>
        ) : (
          <div className="muted">Select a node to see its evidence, confidence and unknowns. Dashed nodes are open questions, not assumptions.</div>
        )}
      </div>
    </div>
  );
}
