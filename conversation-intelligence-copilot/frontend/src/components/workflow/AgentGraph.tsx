import { Background, Handle, MarkerType, Position, ReactFlow, type Edge, type Node, type NodeProps } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { CheckCircle2, CircleDashed, CircleSlash, Loader2, XCircle } from "lucide-react";
import { memo, useMemo } from "react";
import { ms } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { GraphDefinition, NodeStatus } from "@/types/api";

export interface NodeState { status: NodeStatus; duration_ms?: number | null; retries?: number }

const COL_A = ["START", "input_validation", "session_context", "intent", "supervisor"];
const COL_B = ["topic_agent", "sentiment_agent", "coaching_agent", "leadership_agent", "analytics_agent", "retrieval"];
const COL_C = ["evidence", "explanation", "visualization", "qa", "governance", "response", "memory_telemetry", "END"];

function column(id: string): number {
  return COL_A.includes(id) ? 0 : COL_B.includes(id) ? 1 : 2;
}

function position(id: string): { x: number; y: number } {
  const a = COL_A.indexOf(id), b = COL_B.indexOf(id), c = COL_C.indexOf(id);
  if (a >= 0) return { x: id === "START" ? 40 : 0, y: a * 96 };
  if (b >= 0) return { x: 270, y: 8 + b * 78 };
  return { x: 540, y: c * 66 + (id === "END" ? 6 : 0) };
}

const STATUS_STYLE: Record<NodeStatus, string> = {
  pending: "border-line bg-surface text-muted",
  running: "border-cyan/70 bg-cyan/10 text-ink shadow-[0_0_24px_-4px_rgba(34,211,238,0.6)]",
  completed: "border-pos/40 bg-pos/[0.07] text-ink",
  failed: "border-neg/60 bg-neg/10 text-ink",
  skipped: "border-dashed border-line bg-transparent text-faint",
  cancelled: "border-warn/50 bg-warn/10 text-ink",
};

function StatusIcon({ s }: { s: NodeStatus }) {
  if (s === "running") return <Loader2 className="h-3.5 w-3.5 animate-spin text-cyan" aria-label="running" />;
  if (s === "completed") return <CheckCircle2 className="h-3.5 w-3.5 text-pos" aria-label="completed" />;
  if (s === "failed") return <XCircle className="h-3.5 w-3.5 text-neg" aria-label="failed" />;
  if (s === "skipped") return <CircleSlash className="h-3.5 w-3.5 text-faint" aria-label="skipped" />;
  if (s === "cancelled") return <XCircle className="h-3.5 w-3.5 text-warn" aria-label="cancelled" />;
  return <CircleDashed className="h-3.5 w-3.5 text-faint" aria-label="pending" />;
}

type FlowData = { label: string; status: NodeStatus; duration?: number | null; retries?: number; selected?: boolean; terminal?: boolean };

const AgentNode = memo(({ data }: NodeProps<Node<FlowData>>) => (
  <div className={cn("w-[210px] rounded-xl border px-3 py-1.5 text-xs transition-all duration-300", STATUS_STYLE[data.status], data.selected && "ring-2 ring-violet",
    data.terminal && "w-[120px] rounded-full text-center")}>
    <Handle id="t" type="target" position={Position.Top} className="!h-1.5 !w-1.5 !border-0 !bg-faint" />
    <Handle id="l" type="target" position={Position.Left} className="!h-1.5 !w-1.5 !border-0 !bg-faint" />
    <div className={cn("flex items-center gap-2", data.terminal && "justify-center")}>
      {!data.terminal && <StatusIcon s={data.status} />}
      <span className="truncate font-medium">{data.label}</span>
    </div>
    {!data.terminal && (
      <div className="mt-0.5 flex justify-between pl-5 text-[10px] text-faint">
        <span className="capitalize">{data.status}</span>
        {data.duration != null && data.status !== "skipped" && <span className="num">{ms(data.duration)}{data.retries ? ` · ${data.retries} retry` : ""}</span>}
      </div>
    )}
    <Handle id="b" type="source" position={Position.Bottom} className="!h-1.5 !w-1.5 !border-0 !bg-faint" />
    <Handle id="r" type="source" position={Position.Right} className="!h-1.5 !w-1.5 !border-0 !bg-faint" />
  </div>
));
AgentNode.displayName = "AgentNode";
const nodeTypes = { agent: AgentNode };

export function AgentGraph({ definition, states, selected, onSelect, height = 600, finished }: {
  definition: GraphDefinition; states: Record<string, NodeState>; selected?: string | null; onSelect?: (id: string) => void; height?: number; finished: boolean;
}) {
  const { nodes, edges } = useMemo(() => {
    const statusOf = (id: string): NodeStatus => {
      if (id === "START") return Object.keys(states).length ? "completed" : "pending";
      if (id === "END") return states.memory_telemetry?.status === "completed" ? "completed" : "pending";
      return states[id]?.status ?? (finished ? "skipped" : "pending");
    };
    const nodes: Node<FlowData>[] = definition.nodes.map((n) => ({
      id: n.id, type: "agent", position: position(n.id), draggable: false,
      data: { label: n.label, status: statusOf(n.id), duration: states[n.id]?.duration_ms, retries: states[n.id]?.retries, selected: selected === n.id, terminal: n.id === "START" || n.id === "END" },
    }));
    const edges: Edge[] = definition.edges.map((e) => {
      const s = statusOf(e.source), t = statusOf(e.target);
      const traversed = (s === "completed" || s === "failed") && (t === "completed" || t === "running" || t === "failed");
      const same = column(e.source) === column(e.target);
      return {
        id: `${e.source}-${e.target}`, source: e.source, target: e.target, animated: t === "running" && traversed,
        sourceHandle: same ? "b" : "r", targetHandle: same ? "t" : "l", type: same ? "straight" : "default",
        style: { stroke: traversed ? "#22D3EE" : "rgba(148,163,184,0.18)", strokeWidth: traversed ? 1.8 : 1, strokeDasharray: e.conditional && !traversed ? "4 4" : undefined },
        markerEnd: { type: MarkerType.ArrowClosed, color: traversed ? "#22D3EE" : "rgba(148,163,184,0.3)", width: 14, height: 14 },
      };
    });
    return { nodes, edges };
  }, [definition, states, selected, finished]);

  return (
    <div style={{ height }} className="rounded-2xl border border-line bg-bg/60" aria-label="Agent execution graph">
      <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} fitView fitViewOptions={{ padding: 0.06 }} minZoom={0.4} maxZoom={1.6}
        nodesConnectable={false} proOptions={{ hideAttribution: true }} onNodeClick={(_, n) => onSelect?.(n.id)}>
        <Background color="rgba(148,163,184,0.12)" gap={22} size={1} />
      </ReactFlow>
    </div>
  );
}
