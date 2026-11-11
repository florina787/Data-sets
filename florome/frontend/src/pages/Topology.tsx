import { Background, Controls, Handle, MiniMap, Position, ReactFlow, type Edge, type Node, type NodeProps } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Search, X } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Page } from "../components/Layout";
import { Badge, Card, DemoLabel, Empty, ErrorBox, Loading, SectionTitle, cx } from "../components/ui";
import { api, type TopoNode, type Topology as Topo } from "../lib/api";
import { PLATFORM_COLORS } from "../lib/format";
import { useAsync } from "../lib/useAsync";

type Data = { [K in keyof TopoNode]: TopoNode[K] } & { dim: boolean; match: boolean };
const ROLE_RING: Record<string, string> = { root: "ring-bad", symptom: "ring-warn", impacted: "ring-dome-400" };
const HEALTH_DOT: Record<string, string> = { healthy: "bg-ok", degraded: "bg-warn", failed: "bg-bad", unknown: "bg-ink-mute" };

function ResourceNode({ data }: NodeProps<Node<Data>>) {
  const role = data.incident?.role;
  return (
    <div className={cx("w-[188px] rounded-xl border border-dome-100 bg-white px-3 py-2.5 shadow-tile transition",
      role && `ring-2 ${ROLE_RING[role]}`, data.dim && "opacity-25", data.match && "ring-2 ring-dome-500")}>
      <Handle type="target" position={Position.Left} className="!h-1.5 !w-1.5 !border-0 !bg-dome-300" />
      <div className="flex items-center gap-2">
        <span className="h-2 w-2 rounded-full" style={{ background: PLATFORM_COLORS[data.platform] ?? "#8A8DAA" }} />
        <span className="font-mono text-[10px] uppercase tracking-wider text-ink-mute">{data.platform} · {data.kind.replace(/_/g, " ")}</span>
      </div>
      <div className="mt-1 flex items-center justify-between gap-2">
        <span className="truncate text-[13px] font-medium">{data.name}</span>
        <span className={cx("h-2.5 w-2.5 shrink-0 rounded-full", HEALTH_DOT[data.health] ?? "bg-ink-mute")} title={`health: ${data.health}`} />
      </div>
      {role && <div className="mt-1 text-[10px] font-semibold uppercase tracking-wider text-bad">{role === "root" ? "root cause" : role}</div>}
      <Handle type="source" position={Position.Right} className="!h-1.5 !w-1.5 !border-0 !bg-dome-300" />
    </div>
  );
}
const nodeTypes = { resource: ResourceNode };

export function layout(t: Topo): Record<string, { x: number; y: number }> {
  const depth: Record<string, number> = {};
  const parents = (id: string) => t.edges.filter((e) => e.target === id).map((e) => e.source);
  const d = (id: string, seen = new Set<string>()): number => {
    if (depth[id] !== undefined) return depth[id];
    if (seen.has(id)) return 0;
    seen.add(id);
    const ps = parents(id);
    depth[id] = ps.length ? 1 + Math.max(...ps.map((p) => d(p, seen))) : 0;
    return depth[id];
  };
  t.nodes.forEach((n) => d(n.id));
  const rows: Record<number, number> = {};
  const pos: Record<string, { x: number; y: number }> = {};
  [...t.nodes].sort((a, b) => a.platform.localeCompare(b.platform)).forEach((n) => {
    const col = depth[n.id];
    rows[col] = (rows[col] ?? 0) + 1;
    pos[n.id] = { x: col * 250, y: (rows[col] - 1) * 120 };
  });
  return pos;
}

export default function Topology() {
  const { data, error, loading, reload } = useAsync(() => api<Topo>("/topology"));
  const [query, setQuery] = useState("");
  const [platforms, setPlatforms] = useState<Set<string>>(new Set());
  const [impactOnly, setImpactOnly] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);

  const allPlatforms = useMemo(() => [...new Set((data?.nodes ?? []).map((n) => n.platform))].sort(), [data]);
  const { nodes, edges } = useMemo(() => {
    if (!data) return { nodes: [] as Node<Data>[], edges: [] as Edge[] };
    const pos = layout(data);
    const q = query.trim().toLowerCase();
    const visible = (n: TopoNode) => (platforms.size === 0 || platforms.has(n.platform)) && (!impactOnly || n.incident);
    const nodes: Node<Data>[] = data.nodes.map((n) => ({
      id: n.id, type: "resource", position: pos[n.id],
      data: { ...n, dim: !visible(n), match: !!q && (n.name.toLowerCase().includes(q) || n.kind.includes(q)) },
    }));
    const inc = new Set(data.nodes.filter((n) => n.incident).map((n) => n.id));
    const edges: Edge[] = data.edges.map((e) => {
      const hot = inc.has(e.source) && inc.has(e.target);
      return { id: `${e.source}-${e.target}`, source: e.source, target: e.target, label: e.kind.replace("_", " "), animated: hot,
        style: { stroke: hot ? "#E0534A" : "#A3AAFB", strokeWidth: hot ? 2 : 1.2 }, labelStyle: { fontSize: 9, fill: "#8A8DAA" } };
    });
    return { nodes, edges };
  }, [data, query, platforms, impactOnly]);

  const sel = data?.nodes.find((n) => n.id === selected);
  const toggle = (p: string) => setPlatforms((s) => {
    const n = new Set(s);
    if (n.has(p)) n.delete(p); else n.add(p);
    return n;
  });

  return (
    <Page>
      <SectionTitle eyebrow="Enterprise digital nervous system" title="Every dependency, one map"
        sub="Resources discovered through verified connectors, linked by declared data and call flows. Incident roles come from the latest RCA, not guesses." />
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <label className="flex items-center gap-2 rounded-lg border border-dome-100 bg-white px-3 py-1.5">
          <Search className="h-4 w-4 text-ink-mute" />
          <input aria-label="Search resources" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search resources" className="w-48 bg-transparent text-sm outline-none" />
        </label>
        {allPlatforms.map((p) => (
          <button key={p} onClick={() => toggle(p)} aria-pressed={platforms.has(p)}
            className={cx("rounded-full border px-3 py-1 text-xs capitalize", platforms.has(p) ? "border-ink bg-ink text-white" : "border-dome-100 bg-white text-ink-soft")}>
            {p}
          </button>
        ))}
        <label className="ml-auto flex items-center gap-2 text-xs text-ink-soft">
          <input type="checkbox" checked={impactOnly} onChange={(e) => setImpactOnly(e.target.checked)} /> Incident impact only
        </label>
        {data?.data_mode === "demo" && <DemoLabel />}
      </div>
      {error && <ErrorBox error={error} onRetry={reload} />}
      {loading && <Loading label="Discovering topology" />}
      {data && data.nodes.length === 0 && <Empty>No resources discovered. Verify a connection first.</Empty>}
      {data && data.nodes.length > 0 && (
        <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
          <div className="h-[560px] overflow-hidden rounded-2xl border border-dome-100 bg-white/70" data-testid="topology-canvas">
            <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} fitView minZoom={0.3} onNodeClick={(_, n) => setSelected(n.id)}>
              <Background gap={24} color="#E0E3FF" />
              <MiniMap pannable zoomable nodeColor={(n) => PLATFORM_COLORS[(n.data as Data).platform] ?? "#A3AAFB"} />
              <Controls showInteractive={false} />
            </ReactFlow>
          </div>
          <Card>
            {sel ? (
              <div>
                <div className="flex items-start justify-between">
                  <div>
                    <div className="font-mono text-[10px] uppercase text-ink-mute">{sel.platform} · {sel.kind}</div>
                    <h3 className="mt-1 text-lg font-semibold">{sel.name}</h3>
                  </div>
                  <button aria-label="Close details" onClick={() => setSelected(null)}><X className="h-4 w-4 text-ink-mute" /></button>
                </div>
                <dl className="mt-4 space-y-2 text-sm">
                  <div className="flex justify-between"><dt className="text-ink-soft">Health (live read)</dt><dd><Badge value={sel.health} /></dd></div>
                  <div className="flex justify-between"><dt className="text-ink-soft">Environment</dt><dd>{sel.environment}</dd></div>
                  <div className="flex justify-between"><dt className="text-ink-soft">Upstream</dt><dd>{data.edges.filter((e) => e.target === sel.id).length}</dd></div>
                  <div className="flex justify-between"><dt className="text-ink-soft">Downstream</dt><dd>{data.edges.filter((e) => e.source === sel.id).length}</dd></div>
                </dl>
                {sel.incident && (
                  <div className="mt-4 rounded-xl bg-bad/5 p-3 text-sm">
                    <b className="capitalize">{sel.incident.role === "root" ? "Root cause" : sel.incident.role}</b> of an open incident.
                    <Link className="ml-1 text-dome-600 underline" to={`/rca?incident=${sel.incident.incident_id}`}>Open evidence</Link>
                  </div>
                )}
              </div>
            ) : (
              <p className="text-sm text-ink-soft">Select a resource to see its live health, dependencies and incident evidence.</p>
            )}
            <div className="mt-6 space-y-1.5 border-t border-dome-100 pt-4 text-xs text-ink-soft">
              <div className="flex items-center gap-2"><span className="h-3 w-3 rounded ring-2 ring-bad" /> root cause (from RCA)</div>
              <div className="flex items-center gap-2"><span className="h-3 w-3 rounded ring-2 ring-warn" /> symptom</div>
              <div className="flex items-center gap-2"><span className="h-3 w-3 rounded ring-2 ring-dome-400" /> impacted</div>
            </div>
          </Card>
        </div>
      )}
    </Page>
  );
}
