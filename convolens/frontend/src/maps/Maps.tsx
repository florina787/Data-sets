import { useMemo } from "react";
import { Background, Controls, MarkerType, ReactFlow, type Edge, type Node } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { TOPIC_COLORS } from "../lib/palette";

const nodeBase = { borderRadius: 8, border: "1px solid #DCE3EB", background: "#fff", color: "#172B4D", fontSize: 12, padding: 6 };

/** Issue relationship map: topic nodes (size = conversations), subtheme nodes, observed co-occurrence edges. */
export function IssueMap({ data, onSelect, selected }: { data: any; onSelect: (n: { kind: string; key: string; topic?: string }) => void; selected?: string | null }) {
  const { nodes, edges } = useMemo(() => {
    const topics = data.topics.filter((t: any) => t.count > 0);
    const max = Math.max(1, ...topics.map((t: any) => t.count));
    const R = 260;
    const nodes: Node[] = [];
    const edges: Edge[] = [];
    topics.forEach((t: any, i: number) => {
      const a = (2 * Math.PI * i) / Math.max(topics.length, 1);
      const size = 70 + 70 * Math.sqrt(t.count / max);
      const x = 380 + R * Math.cos(a), y = 300 + R * Math.sin(a);
      nodes.push({
        id: `t:${t.key}`, position: { x: x - size / 2, y: y - size / 2 }, data: { label: `${t.label}\n${t.count} conversations` },
        style: { ...nodeBase, width: size, height: size, borderRadius: size, display: "flex", alignItems: "center", justifyContent: "center", textAlign: "center",
          whiteSpace: "pre-line", background: t.key === "unknown" ? "#F3F5F8" : "#fff", border: `${selected === t.key ? 3 : 2}px solid ${TOPIC_COLORS[t.key] ?? "#5F6B7A"}` },
        ariaLabel: `Topic ${t.label}, ${t.count} conversations`,
      });
      const subs = data.subthemes.filter((s: any) => s.topic === t.key);
      subs.forEach((s: any, j: number) => {
        const sa = a + (j - (subs.length - 1) / 2) * 0.35;
        const sx = 380 + (R + 150) * Math.cos(sa), sy = 300 + (R + 150) * Math.sin(sa);
        nodes.push({ id: `s:${t.key}:${s.key}`, position: { x: sx - 60, y: sy - 18 }, data: { label: `${s.label} (${s.count})` },
          style: { ...nodeBase, width: 130, fontSize: 11, borderStyle: "dashed", borderColor: TOPIC_COLORS[t.key] }, ariaLabel: `Subtheme ${s.label}, ${s.count} conversations` });
        edges.push({ id: `e:${t.key}:${s.key}`, source: `t:${t.key}`, target: `s:${t.key}:${s.key}`, style: { stroke: "#AEB8C4" } });
      });
    });
    const emax = Math.max(1, ...data.edges.map((e: any) => e.count));
    data.edges.forEach((e: any) => {
      if (!topics.find((t: any) => t.key === e.source) || !topics.find((t: any) => t.key === e.target)) return;
      edges.push({ id: `c:${e.source}:${e.target}`, source: `t:${e.source}`, target: `t:${e.target}`, label: `${e.count} co-occur`,
        labelStyle: { fontSize: 10, fill: "#5F6B7A" }, style: { stroke: "#087F8C", strokeWidth: 1 + 6 * (e.count / emax), opacity: 0.6 } });
    });
    return { nodes, edges };
  }, [data, selected]);
  return (
    <div className="h-[640px] rounded-md border border-line" aria-label="Issue relationship map">
      <ReactFlow nodes={nodes} edges={edges} fitView nodesDraggable nodesConnectable={false} elementsSelectable
        onNodeClick={(_, n) => {
          const [kind, key, sub] = n.id.split(":");
          onSelect(kind === "t" ? { kind: "topic", key } : { kind: "subtheme", key: sub, topic: key });
        }}>
        <Background color="#E6EAF0" gap={20} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}

const STAGE_POS: Record<string, { x: number; y: number }> = {
  problem: { x: 0, y: 140 }, clarification: { x: 230, y: 20 }, support_action: { x: 230, y: 260 },
  follow_up: { x: 470, y: 20 }, escalation: { x: 470, y: 260 }, outcome: { x: 700, y: 140 },
};

/** Conversation journey map from actual reply links between inferred stages. */
export function JourneyMap({ data }: { data: any }) {
  const { nodes, edges } = useMemo(() => {
    const n = data.denominator || 1;
    const nodes: Node[] = data.stages.map((s: any) => {
      const missingShare = s.missing / n;
      return {
        id: s.key, position: STAGE_POS[s.key],
        data: { label: `${s.label}\n${s.conversations} of ${data.denominator} conversations${s.missing ? `\nmissing in ${s.missing}` : ""}` },
        style: { ...nodeBase, width: 180, whiteSpace: "pre-line", textAlign: "center",
          border: missingShare > 0.5 ? "2px dashed #A96308" : "2px solid #087F8C", background: missingShare > 0.5 ? "#FBF1E4" : "#fff" },
        ariaLabel: `${s.label}: present in ${s.conversations} conversations, missing in ${s.missing}`,
      };
    });
    const emax = Math.max(1, ...data.transitions.map((t: any) => t.reply_edges));
    const edges: Edge[] = data.transitions.filter((t: any) => t.source !== t.target || t.reply_edges > 0).map((t: any) => ({
      id: `${t.source}-${t.target}`, source: t.source, target: t.target, label: `${t.reply_edges}`,
      markerEnd: { type: MarkerType.ArrowClosed, color: "#5F6B7A" }, labelStyle: { fontSize: 10 },
      style: { stroke: "#5F6B7A", strokeWidth: 1 + 5 * (t.reply_edges / emax), opacity: 0.7 },
    }));
    return { nodes, edges };
  }, [data]);
  return (
    <div className="h-[420px] rounded-md border border-line" aria-label="Conversation journey map">
      <ReactFlow nodes={nodes} edges={edges} fitView nodesConnectable={false}>
        <Background color="#E6EAF0" gap={20} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}

/** Ownership map: issue -> proposed intervention -> proposed department -> action record. */
export function OwnershipMap({ data }: { data: any }) {
  const { nodes, edges } = useMemo(() => {
    const nodes: Node[] = [];
    const edges: Edge[] = [];
    const depts = new Map<string, number>();
    data.candidates.forEach((c: any, i: number) => {
      const y = i * 90;
      nodes.push({ id: `i:${c.key}`, position: { x: 0, y }, data: { label: `${c.title}\n${c.frequency.numerator} conversations` },
        style: { ...nodeBase, width: 200, whiteSpace: "pre-line", borderLeft: `4px solid ${TOPIC_COLORS[c.topic]}` } });
      nodes.push({ id: `v:${c.key}`, position: { x: 260, y }, data: { label: c.intervention }, style: { ...nodeBase, width: 260, fontSize: 11 } });
      edges.push({ id: `iv:${c.key}`, source: `i:${c.key}`, target: `v:${c.key}`, markerEnd: { type: MarkerType.ArrowClosed } });
      if (!depts.has(c.proposed_department)) depts.set(c.proposed_department, depts.size);
      edges.push({ id: `vd:${c.key}`, source: `v:${c.key}`, target: `d:${c.proposed_department}`, label: "proposed", labelStyle: { fontSize: 10, fill: "#A96308" },
        style: { strokeDasharray: "5 4", stroke: "#A96308" }, markerEnd: { type: MarkerType.ArrowClosed, color: "#A96308" } });
    });
    depts.forEach((idx, name) => nodes.push({ id: `d:${name}`, position: { x: 590, y: idx * 110 }, data: { label: `${name}\n(proposed department)` },
      style: { ...nodeBase, width: 190, whiteSpace: "pre-line", border: "2px dashed #A96308", background: "#FBF1E4" } }));
    data.actions.forEach((a: any, i: number) => {
      nodes.push({ id: `a:${a.id}`, position: { x: 860, y: i * 90 }, data: { label: `Action #${a.id}: ${a.title}\n${a.status} · owner: ${a.owner ?? "not set"}${a.owner && !a.owner_confirmed ? " (unconfirmed)" : ""}` },
        style: { ...nodeBase, width: 230, whiteSpace: "pre-line", fontSize: 11, border: `2px ${a.owner_confirmed ? "solid #24734B" : "dashed #5F6B7A"}` } });
      if (a.department && depts.has(a.department)) edges.push({ id: `da:${a.id}`, source: `d:${a.department}`, target: `a:${a.id}`, markerEnd: { type: MarkerType.ArrowClosed } });
    });
    return { nodes, edges };
  }, [data]);
  return (
    <div className="h-[560px] rounded-md border border-line" aria-label="Ownership map">
      <ReactFlow nodes={nodes} edges={edges} fitView nodesConnectable={false}>
        <Background color="#E6EAF0" gap={20} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}

const GRAPH_POS: Record<string, { x: number; y: number }> = {
  __start__: { x: 0, y: 160 }, interpret_request: { x: 140, y: 160 }, resolve_context: { x: 330, y: 60 }, plan_analysis: { x: 520, y: 60 },
  execute_tools: { x: 710, y: 60 }, inspect_results: { x: 900, y: 60 }, validate_claims: { x: 900, y: 200 }, compose_response: { x: 710, y: 290 },
  request_action_approval: { x: 520, y: 400 }, persist_approved_action: { x: 330, y: 400 }, handle_failure: { x: 330, y: 260 }, __end__: { x: 140, y: 400 },
};
const STATE_STYLE: Record<string, { border: string; bg: string; label: string }> = {
  running: { border: "2px solid #087F8C", bg: "#E7F4F4", label: "running" },
  completed: { border: "2px solid #24734B", bg: "#E6F2EB", label: "completed" },
  failed: { border: "2px solid #B83D45", bg: "#F8E9EA", label: "failed" },
  awaiting_approval: { border: "2px dashed #A96308", bg: "#FBF1E4", label: "awaiting approval" },
};

/** Agent execution map: the actual LangGraph structure (from the backend) with the state of the latest run. */
export function AgentExecutionMap({ graph, states, live }: { graph: { nodes: string[]; edges: { source: string; target: string; label: string }[] }; states: Record<string, string>; live: boolean }) {
  const { nodes, edges } = useMemo(() => {
    const ids = ["__start__", ...graph.nodes, "__end__"];
    const nodes: Node[] = ids.map((id) => {
      const st = STATE_STYLE[states[id] ?? ""];
      return { id, position: GRAPH_POS[id] ?? { x: 0, y: 0 },
        data: { label: `${id.replace(/__/g, "").replace(/_/g, " ")}${st ? `\n(${st.label})` : states[id] === undefined && Object.keys(states).length ? "\n(not visited)" : ""}` },
        style: { ...nodeBase, width: 160, whiteSpace: "pre-line", textAlign: "center", border: st?.border ?? "1px solid #DCE3EB", background: st?.bg ?? "#fff",
          opacity: Object.keys(states).length && !st && !id.startsWith("__") ? 0.55 : 1 },
        ariaLabel: `${id}: ${st?.label ?? "not visited"}` };
    });
    const edges: Edge[] = graph.edges.map((e) => {
      const traversed = !!states[e.source] && !!states[e.target];
      return { id: `${e.source}-${e.target}`, source: e.source, target: e.target, label: e.label || undefined, labelStyle: { fontSize: 9, fill: "#5F6B7A" },
        animated: live && traversed && states[e.target] === "running",
        markerEnd: { type: MarkerType.ArrowClosed, color: traversed ? "#087F8C" : "#AEB8C4" },
        style: { stroke: traversed ? "#087F8C" : "#C9D1DB", strokeWidth: traversed ? 2 : 1 } };
    });
    return { nodes, edges };
  }, [graph, states, live]);
  return (
    <div className="h-[480px] rounded-md border border-line" aria-label="Agent execution map">
      <ReactFlow nodes={nodes} edges={edges} fitView nodesConnectable={false} nodesDraggable={false}>
        <Background color="#E6EAF0" gap={20} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
