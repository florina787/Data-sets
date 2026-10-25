import { Background, Controls, ReactFlow, type Edge, type Node } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useMemo } from "react";
import type { RunView, WorkflowEvent } from "@/lib/types";

const COLORS: Record<string, string> = { completed: "#0F8B8D", failed: "#C53030", halted: "#C53030", running: "#B7791F", retrying: "#B7791F", queued: "#A78BFA", skipped: "#8890B0", cancelled: "#8890B0" };

/** DAG of the workflow graph, colored by the latest *recorded* status of each step. */
export function AgentGraph({ graph, events, height = 300 }: { graph: NonNullable<RunView["graph"]>; events: WorkflowEvent[]; height?: number }) {
  const { nodes, edges } = useMemo(() => {
    const last: Record<string, WorkflowEvent> = {};
    for (const e of events) last[e.step] = e;
    const depth: Record<string, number> = {};
    const d = (id: string): number => {
      if (depth[id] !== undefined) return depth[id];
      const n = graph.nodes.find((x) => x.id === id);
      depth[id] = n && n.deps.length ? Math.max(...n.deps.map(d)) + 1 : 0;
      return depth[id];
    };
    graph.nodes.forEach((n) => d(n.id));
    const perLevel: Record<number, number> = {};
    const nodes: Node[] = graph.nodes.map((n) => {
      const lvl = depth[n.id];
      const idx = (perLevel[lvl] = (perLevel[lvl] ?? -1) + 1);
      const st = last[n.id]?.status ?? "pending";
      return {
        id: n.id,
        position: { x: lvl * 190, y: idx * 78 },
        data: { label: `${n.id}\n${n.agent}\n[${st}]` },
        style: { whiteSpace: "pre-line", fontSize: 10, width: 170, borderRadius: 10, border: `2px solid ${COLORS[st] ?? "#DCD8EC"}`, background: "var(--panel)", color: "var(--text)" },
        ariaLabel: `${n.id} by ${n.agent}: ${st}`,
      };
    });
    const edges: Edge[] = graph.nodes.flatMap((n) => n.deps.map((dep) => ({ id: `${dep}-${n.id}`, source: dep, target: n.id, animated: last[n.id]?.status === "running" })));
    return { nodes, edges };
  }, [graph, events]);
  return (
    <div style={{ height }} className="rounded-lg border border-token" data-testid="agent-graph">
      <ReactFlow nodes={nodes} edges={edges} fitView nodesDraggable={false} nodesConnectable={false} proOptions={{ hideAttribution: true }}>
        <Background gap={16} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
