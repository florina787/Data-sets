import { useMemo } from "react";
import { Background, Controls, MarkerType, ReactFlow, type Edge, type Node } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { money, compact } from "../lib/format";

const STATUS_COLOR: Record<string, string> = { running: "#2BB673", waiting: "#B8913A", idle: "#C9D9D1", ok: "#13795B", failed: "#B4413C", denied: "#B4413C" };

/** Live agent execution graph: harness pipeline in the centre, the 15 agents around it. */
export function AgentGraph({ agents, run, cur, height = 520, mini = false }: { agents: any[]; run?: any; cur: string; height?: number; mini?: boolean }) {
  const { nodes, edges } = useMemo(() => {
    const pipe = ["plan_task", "execute_step", "verify", "approval_gate", "finalize"];
    const visited = new Set<string>((run?.trace ?? []).map((t: any) => t.node));
    const activeAgents = new Set<string>((run?.plan ?? []).map((p: any) => p.agent));
    const doneSteps = new Map<string, any>((run?.result?.steps ?? []).map((s: any) => [s.agent, s]));
    const n: Node[] = pipe.map((p, i) => ({
      id: p, position: { x: mini ? 40 + i * 120 : 260 + i * 170, y: mini ? 20 : 250 }, data: { label: p.replace("_", " ") }, draggable: !mini,
      style: { borderRadius: 999, padding: mini ? "4px 8px" : "8px 14px", fontSize: mini ? 10 : 12, fontWeight: 700, border: "2px solid " + (visited.has(p) ? "#13795B" : "#DCE8E2"),
        background: visited.has(p) ? "#E6F4EE" : "#fff", color: "#0B3D2E", width: "auto" },
    }));
    const e: Edge[] = pipe.slice(0, -1).map((p, i) => ({ id: `${p}-${pipe[i + 1]}`, source: p, target: pipe[i + 1], animated: run?.status === "running", markerEnd: { type: MarkerType.ArrowClosed }, style: { stroke: "#13795B" } }));
    if (!mini) {
      e.push({ id: "loop", source: "execute_step", target: "execute_step", label: "next step", style: { stroke: "#B8913A" } });
      const cx = 600, cy = 270, R = 300;
      agents.forEach((a, i) => {
        const ang = (Math.PI * 2 * i) / agents.length - Math.PI / 2;
        const st = doneSteps.get(a.id);
        const status = st ? (st.ok ? "ok" : st.denied ? "denied" : "failed") : a.status;
        n.push({ id: `agent:${a.id}`, position: { x: cx + R * 1.55 * Math.cos(ang) - 80, y: cy + R * 0.82 * Math.sin(ang) - 20 }, draggable: true,
          data: { label: (
            <div className="text-left" title={a.current_task ?? ""}>
              <div className="flex items-center gap-1 text-[11px] font-bold text-flo-950"><span className={`inline-block h-2 w-2 rounded-full ${status === "running" ? "pulse-dot" : ""}`} style={{ background: STATUS_COLOR[status] ?? "#C9D9D1" }} />{a.label.replace(" Agent", "")}</div>
              <div className="text-[9.5px] leading-tight text-muted">{compact(a.tokens)} tok · {money(a.compute_cost, cur)} · Q {a.quality_pass_rate ?? "—"}%</div>
              <div className="text-[9.5px] leading-tight text-flo-800">{a.verified_tasks ?? 0} verified · {money(a.economic_contribution, cur)}</div>
            </div>) },
          style: { width: 170, padding: 6, borderRadius: 12, border: `1.5px solid ${activeAgents.has(a.id) ? "#13795B" : "#DCE8E2"}`, background: activeAgents.has(a.id) ? "#F3FAF6" : "#fff",
            boxShadow: status === "running" ? "0 0 0 4px rgba(43,182,115,.25)" : "none" } });
        const target = a.id === "verification" ? "verify" : "execute_step";
        e.push({ id: `e-${a.id}`, source: target, target: `agent:${a.id}`, animated: activeAgents.has(a.id) && run?.status === "running",
          style: { stroke: activeAgents.has(a.id) ? "#13795B" : "#E3ECE7", strokeWidth: activeAgents.has(a.id) ? 2 : 1 } });
      });
    }
    return { nodes: n, edges: e };
  }, [agents, run, cur, mini]);
  return (
    <div style={{ height }} className="rounded-2xl border border-line bg-gradient-to-br from-white to-flo-50" data-testid="agent-graph">
      <ReactFlow key={`${agents.length}-${run?.id ?? ""}`} nodes={nodes} edges={edges} fitView fitViewOptions={{ padding: 0.08 }} proOptions={{ hideAttribution: false }} nodesConnectable={false} minZoom={0.2}>
        <Background color="#DCE8E2" gap={22} />
        {!mini && <Controls showInteractive={false} />}
      </ReactFlow>
    </div>
  );
}
