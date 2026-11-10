import { Background, Handle, Position, ReactFlow, type Edge, type Node, type NodeProps } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { memo, useMemo, useState } from "react";
import { Card, CardHeader } from "@/components/common/ui";
import { cn } from "@/lib/utils";
import type { GraphSpec } from "@/types/api";

type D = { label: string; kind: string; dim: boolean };
const RelNode = memo(({ data }: NodeProps<Node<D>>) => (
  <div className={cn("rounded-lg border px-2.5 py-1.5 text-[11px] font-medium capitalize transition-opacity",
    data.kind === "issue" ? "border-indigo/40 bg-indigo/10 text-ink" : "border-cyan/40 bg-cyan/10 text-ink", data.dim && "opacity-30")}>
    <Handle type="target" position={Position.Left} className="!h-1 !w-1 !border-0 !bg-transparent" />
    {data.label}
    <Handle type="source" position={Position.Right} className="!h-1 !w-1 !border-0 !bg-transparent" />
  </div>
));
RelNode.displayName = "RelNode";

/** Bipartite issue → closing-action graph. Edge width = observed conversation count. */
export function RelationGraph({ spec }: { spec: GraphSpec }) {
  const [focus, setFocus] = useState<string | null>(null);
  const { nodes, edges } = useMemo(() => {
    const issues = spec.nodes.filter((n) => n.kind === "issue");
    const res = spec.nodes.filter((n) => n.kind !== "issue");
    const maxW = Math.max(...spec.edges.map((e) => e.weight));
    const linked = (id: string) => !focus || id === focus || spec.edges.some((e) => (e.source === focus && e.target === id) || (e.target === focus && e.source === id));
    const nodes: Node<D>[] = [
      ...issues.map((n, i) => ({ id: n.id, type: "rel", position: { x: 0, y: i * 52 }, data: { label: n.label, kind: n.kind, dim: !linked(n.id) } })),
      ...res.map((n, i) => ({ id: n.id, type: "rel", position: { x: 380, y: 30 + i * 62 }, data: { label: n.label, kind: n.kind, dim: !linked(n.id) } })),
    ];
    const edges: Edge[] = spec.edges.map((e) => {
      const on = !focus || e.source === focus || e.target === focus;
      return { id: `${e.source}-${e.target}`, source: e.source, target: e.target, label: on && focus ? e.label : undefined,
        labelStyle: { fill: "#CBD5E1", fontSize: 10 }, labelBgStyle: { fill: "#17233C" },
        style: { stroke: on ? "#A78BFA" : "rgba(148,163,184,0.08)", strokeWidth: 0.5 + (4 * e.weight) / maxW, opacity: on ? 0.85 : 0.4 } };
    });
    return { nodes, edges };
  }, [spec, focus]);
  return (
    <Card>
      <CardHeader title={spec.title} subtitle={`${spec.description} Click a node to focus it.`} />
      <div className="h-[460px] px-3 pb-3 pt-2">
        <ReactFlow nodes={nodes} edges={edges} nodeTypes={{ rel: RelNode }} fitView proOptions={{ hideAttribution: true }} nodesConnectable={false}
          nodesDraggable={false} onNodeClick={(_, n) => setFocus((f) => (f === n.id ? null : n.id))} onPaneClick={() => setFocus(null)}>
          <Background color="rgba(148,163,184,0.08)" gap={20} />
        </ReactFlow>
      </div>
    </Card>
  );
}
