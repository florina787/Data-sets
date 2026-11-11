import { Background, Controls, Handle, Position, ReactFlow, type Edge, type Node, type NodeProps } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Download, FlaskConical, ShieldCheck } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Chart, type ChartOption } from "../components/Chart";
import { Page } from "../components/Layout";
import { Badge, Button, Card, DemoLabel, Empty, ErrorBox, Loading, SectionTitle, cx } from "../components/ui";
import { ApiError, api, post, type Hypothesis, type Incident, type RCAReport } from "../lib/api";
import { PLATFORM_COLORS, downloadJson, fmtDateTime, fmtTime } from "../lib/format";
import { useAsync } from "../lib/useAsync";

const STATUS_COLOR: Record<string, string> = { confirmed: "#1F9D6B", probable: "#5B63E6", inconclusive: "#D9921A", disproven: "#8A8DAA" };
const KIND_SYMBOL: Record<string, string> = { log: "circle", metric: "rect", deployment: "diamond", config_change: "triangle", trace: "roundRect", status: "pin" };

type GNode = { label: string; type: string; status?: string; platform?: string; kind?: string; anomalous?: boolean; role?: string; selected: boolean };

function GraphNode({ data }: NodeProps<Node<GNode>>) {
  const base = "max-w-[230px] rounded-xl border px-3 py-2 text-[11px] shadow-sm";
  if (data.type === "resource")
    return (
      <div className={cx(base, "bg-white", data.anomalous ? "border-bad/50" : "border-dome-100", data.selected && "ring-2 ring-dome-500")}>
        <Handle type="target" position={Position.Right} className="!opacity-0" />
        <div className="font-mono text-[9px] uppercase" style={{ color: PLATFORM_COLORS[data.platform ?? ""] }}>{data.platform}</div>
        <div className="text-[12px] font-medium">{data.label}</div>
      </div>
    );
  if (data.type === "hypothesis")
    return (
      <div className={cx(base, "bg-white", data.status === "disproven" && "border-dashed opacity-70", data.selected && "ring-2 ring-dome-500")}
        style={{ borderColor: STATUS_COLOR[data.status ?? ""], borderWidth: 2 }}>
        <Handle type="target" position={Position.Right} className="!opacity-0" />
        <Handle type="source" position={Position.Left} className="!opacity-0" />
        <div className="flex items-center justify-between gap-2"><span className="font-mono text-[9px] uppercase text-ink-mute">{data.role}</span><Badge value={data.status ?? ""} /></div>
        <div className="mt-1 line-clamp-3">{data.label}</div>
      </div>
    );
  return (
    <div className={cx(base, "bg-canvas", data.selected ? "border-dome-500 ring-2 ring-dome-500" : "border-dome-100")}>
      <Handle type="source" position={Position.Left} className="!opacity-0" />
      <span className="font-mono text-[9px] uppercase text-dome-600">{data.kind}</span>
      <div className="line-clamp-2 text-ink-soft">{data.label}</div>
    </div>
  );
}
const nodeTypes = { g: GraphNode };

export function constellation(rep: RCAReport, selected: string | null, hideDisproven: boolean): { nodes: Node<GNode>[]; edges: Edge[] } {
  const g = rep.evidence_graph;
  const hidden = new Set(hideDisproven ? g.nodes.filter((n) => n.status === "disproven").map((n) => n.id) : []);
  const col: Record<string, number> = { resource: 0, hypothesis: 1, evidence: 2 };
  const count: Record<string, number> = {};
  const nodes: Node<GNode>[] = g.nodes.filter((n) => !hidden.has(n.id)).map((n) => {
    const c = col[n.type] ?? 2;
    count[n.type] = (count[n.type] ?? 0) + 1;
    const i = count[n.type] - 1;
    const position = n.type === "evidence" ? { x: 600 + (i % 2) * 260, y: Math.floor(i / 2) * 78 } : { x: c * 300, y: i * 92 };
    return { id: n.id, type: "g", position,
      data: { ...n, selected: n.id === selected } };
  });
  const edges: Edge[] = g.edges.filter((e) => !hidden.has(e.source) && !hidden.has(e.target)).map((e, i) => ({
    id: `e${i}`, source: e.source, target: e.target,
    style: e.type === "supports" ? { stroke: "#1F9D6B", strokeWidth: 1.4 } : e.type === "contradicts" ? { stroke: "#E0534A", strokeDasharray: "5 4", strokeWidth: 1.4 } : { stroke: "#C7CCFF" },
    animated: e.type === "supports" && (e.source === selected || e.target === selected),
  }));
  return { nodes, edges };
}

export function timelineOption(rep: RCAReport): ChartOption {
  const lanes = [...new Set(rep.timeline.map((t) => t.resource))];
  const root = rep.hypotheses.find((h) => h.id === rep.conclusion.root_hypothesis_id);
  const rootChange = root ? rep.timeline.find((t) => root.supporting_evidence.includes(t.evidence_id) && (t.kind === "deployment" || t.kind === "config_change")) : undefined;
  const marks: { name: string; xAxis: number }[] = [{ name: "Detected", xAxis: new Date(rep.incident.detected_at).getTime() }];
  if (rootChange) marks.push({ name: "Root change", xAxis: new Date(rootChange.at).getTime() });
  return {
    grid: { left: 150, right: 30, top: 30, bottom: 60 },
    tooltip: { trigger: "item", formatter: (p: { data: { value: [number, string]; summary: string; kind: string } }) => `<b>${p.data.kind}</b> ${fmtTime(new Date(p.data.value[0]).toISOString())}<br/>${p.data.summary}` },
    xAxis: { type: "time", max: new Date(rep.incident.detected_at).getTime() + 5 * 60e3, axisLabel: { color: "#8A8DAA" }, splitLine: { lineStyle: { color: "#EEF0FF" } } },
    yAxis: { type: "category", data: lanes, axisLabel: { color: "#4A4E6E" }, splitLine: { show: true, lineStyle: { color: "#F1F2FD" } } },
    dataZoom: [{ type: "slider", height: 18, bottom: 12 }, { type: "inside" }],
    series: [{
      type: "scatter", symbolSize: 14,
      data: rep.timeline.map((t) => ({ value: [new Date(t.at).getTime(), t.resource], id: t.evidence_id, summary: t.summary, kind: t.kind,
        symbol: KIND_SYMBOL[t.kind] ?? "circle", itemStyle: { color: t.anomalous ? "#E0534A" : t.kind === "deployment" || t.kind === "config_change" ? "#5B63E6" : "#A3AAFB" } })),
      markLine: { symbol: "none", label: { formatter: "{b}", color: "#4A4E6E", fontSize: 10 }, lineStyle: { color: "#14164A", type: "dashed" }, data: marks },
    }],
  };
}

interface EvidenceDetail { id: string; kind: string; observed_at: string; summary: string; payload: Record<string, unknown>; source_system: string; source_ref: string; content_hash: string; integrity_ok: boolean; collected_by: string; provenance: string; is_demo: boolean }

export default function RCA() {
  const [params, setParams] = useSearchParams();
  const incidents = useAsync(() => api<{ items: Incident[] }>("/incidents"));
  const incidentId = params.get("incident") ?? incidents.data?.items[0]?.id ?? null;
  const [report, setReport] = useState<RCAReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [evidence, setEvidence] = useState<EvidenceDetail | null>(null);
  const [hideDisproven, setHideDisproven] = useState(false);

  useEffect(() => {
    if (!incidentId) return;
    setLoading(true);
    setError(null);
    api<RCAReport>(`/rca/${incidentId}`).then(setReport).catch((e) => (e instanceof ApiError && e.status === 404 ? setReport(null) : setError(String(e.message)))).finally(() => setLoading(false));
  }, [incidentId]);

  const run = async () => {
    setRunning(true);
    setError(null);
    try {
      setReport(await post<RCAReport>(`/rca/${incidentId}`));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setRunning(false);
    }
  };

  const select = async (id: string) => {
    setSelected(id);
    setEvidence(null);
    if (id.startsWith("ev_")) setEvidence(await api<EvidenceDetail>(`/evidence/${id}`));
  };

  const graph = useMemo(() => (report ? constellation(report, selected, hideDisproven) : null), [report, selected, hideDisproven]);
  const tl = useMemo(() => (report ? timelineOption(report) : null), [report]);
  const selHyp: Hypothesis | undefined = report?.hypotheses.find((h) => h.id === selected);
  const name = (rid: string) => report?.affected_systems.find((a) => a.resource_id === rid)?.name ?? report?.evidence_graph.nodes.find((n) => n.id === rid)?.label ?? rid;
  const incident = incidents.data?.items.find((i) => i.id === incidentId);

  return (
    <Page>
      <SectionTitle eyebrow="RCA intelligence" title="Root cause, with the evidence that proves it"
        sub="Competing hypotheses are tested against collected telemetry. Each is confirmed, probable, inconclusive or disproven by named tests; no confidence percentages are invented." />
      {incidents.error && <ErrorBox error={incidents.error} />}
      <div className="mb-5 flex flex-wrap items-center gap-3">
        <select aria-label="Incident" value={incidentId ?? ""} onChange={(e) => setParams({ incident: e.target.value })}
          className="rounded-lg border border-dome-100 bg-white px-3 py-2 text-sm">
          {incidents.data?.items.map((i) => <option key={i.id} value={i.id}>{i.severity.toUpperCase()} · {i.title}</option>)}
        </select>
        {incident && <Badge value={incident.status} />}
        {incident?.is_demo && <DemoLabel />}
        <Button onClick={run} disabled={!incidentId || running}><FlaskConical className="h-4 w-4" />{running ? "Investigating…" : report ? "Re-run investigation" : "Run investigation"}</Button>
        {report && <Button kind="ghost" onClick={() => downloadJson(`rca-${report.id}.json`, report)}><Download className="h-4 w-4" />Export report</Button>}
      </div>
      {error && <ErrorBox error={error} />}
      {(loading || running) && <Loading label={running ? "Collecting evidence and testing hypotheses" : "Loading report"} />}
      {!loading && !running && !report && !error && incidentId && <Empty>No investigation yet for this incident. Run one to collect evidence. (Requires the operator role.)</Empty>}

      {report && !running && (
        <div className="space-y-5">
          <Card className="border-l-4" >
            <div className="flex flex-wrap items-start gap-4">
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-[11px] uppercase tracking-[0.14em] text-ink-mute">Conclusion</span>
                  <Badge value={report.conclusion.final_status} />
                  {report.challenge.downgraded_by.length > 0 && <span className="text-xs text-warn">downgraded by challenger: {report.challenge.downgraded_by.join(", ")}</span>}
                </div>
                <p className="mt-2 text-lg font-medium">{report.conclusion.statement}</p>
                <div className="mt-3 flex flex-wrap items-center gap-1.5 text-xs">
                  {report.conclusion.causal_chain.map((c, i) => (
                    <span key={c.resource_id} className="flex items-center gap-1.5">
                      {i > 0 && <span className={cx("font-mono", c.link_status === "confirmed" ? "text-ok" : "text-warn")}>→{c.link_status !== "confirmed" && <sup>{c.link_status}</sup>}</span>}
                      <span className={cx("rounded-md px-2 py-0.5", i === 0 ? "bg-bad/10 text-bad" : "bg-dome-50")}>{name(c.resource_id)}</span>
                    </span>
                  ))}
                </div>
              </div>
              <div className="text-right text-xs text-ink-mute">
                <div>{report.evidence_collection.collected} new evidence items · {report.timeline.length} total</div>
                <div className="mt-1 flex items-center justify-end gap-1"><ShieldCheck className="h-3.5 w-3.5 text-ok" /> report sha256 {report.report_hash.slice(0, 12)}…</div>
                <div>{fmtDateTime(report.created_at)}</div>
              </div>
            </div>
            <div className="mt-4 grid gap-2 md:grid-cols-3">
              {report.challenge.checks.map((c) => (
                <div key={c.check} className="rounded-lg border border-dome-100 bg-canvas p-2.5 text-xs">
                  <div className="flex items-center justify-between"><span className="font-mono">{c.check}</span><Badge value={c.status} /></div>
                  <p className="mt-1 text-ink-soft">{c.detail}</p>
                </div>
              ))}
            </div>
          </Card>

          <div className="grid gap-5 lg:grid-cols-[1fr_360px]">
            <Card className="p-0">
              <div className="flex items-center justify-between px-5 pt-4">
                <h3 className="font-semibold">Causality constellation</h3>
                <div className="flex items-center gap-4 text-[11px] text-ink-soft">
                  <span className="flex items-center gap-1"><span className="h-0.5 w-5 bg-ok" />supports</span>
                  <span className="flex items-center gap-1"><span className="h-0.5 w-5 border-t-2 border-dashed border-bad" />contradicts</span>
                  <label className="flex items-center gap-1"><input type="checkbox" checked={hideDisproven} onChange={(e) => setHideDisproven(e.target.checked)} />hide disproven</label>
                </div>
              </div>
              <div className="h-[520px]" data-testid="constellation">
                {graph && (
                  <ReactFlow nodes={graph.nodes} edges={graph.edges} nodeTypes={nodeTypes} fitView minZoom={0.2} onNodeClick={(_, n) => void select(n.id)}>
                    <Background gap={24} color="#EEF0FF" />
                    <Controls showInteractive={false} />
                  </ReactFlow>
                )}
              </div>
            </Card>
            <Card>
              <h3 className="font-semibold">Source evidence</h3>
              {!selected && <p className="mt-2 text-sm text-ink-soft">Click any node or timeline point to trace it back to the raw record it came from.</p>}
              {selHyp && (
                <div className="mt-3 space-y-2 text-sm">
                  <div className="flex items-center gap-2"><b>{selHyp.id}</b><Badge value={selHyp.status} /></div>
                  <p>{selHyp.title}</p>
                  <ul className="space-y-1.5">
                    {selHyp.tests.map((t) => (
                      <li key={t.test} className="rounded-lg bg-canvas p-2 text-xs"><div className="flex justify-between"><span className="font-mono">{t.test}</span><Badge value={t.result} /></div><p className="mt-1 text-ink-soft">{t.detail}</p></li>
                    ))}
                  </ul>
                  <p className="text-xs text-ink-mute">{selHyp.basis}</p>
                </div>
              )}
              {evidence && (
                <div className="mt-3 space-y-2 text-sm">
                  <div className="flex items-center gap-2"><span className="font-mono text-xs text-dome-600">{evidence.kind}</span>{evidence.is_demo && <DemoLabel />}</div>
                  <p className="font-medium">{evidence.summary}</p>
                  <dl className="space-y-1 text-xs">
                    <div className="flex justify-between"><dt className="text-ink-mute">Observed</dt><dd>{fmtDateTime(evidence.observed_at)}</dd></div>
                    <div className="flex justify-between"><dt className="text-ink-mute">Source</dt><dd className="font-mono">{evidence.source_system}:{evidence.source_ref}</dd></div>
                    <div className="flex justify-between"><dt className="text-ink-mute">Integrity</dt><dd>{evidence.integrity_ok ? <Badge value="pass" label="hash verified" /> : <Badge value="fail" label="hash mismatch" />}</dd></div>
                  </dl>
                  <pre className="max-h-56 overflow-auto rounded-lg bg-night p-3 font-mono text-[11px] text-dome-100">{JSON.stringify(evidence.payload, null, 2)}</pre>
                  <p className="text-[11px] text-ink-mute">{evidence.provenance}</p>
                </div>
              )}
              {selected && !selHyp && !evidence && !selected.startsWith("ev_") && <p className="mt-3 text-sm text-ink-soft">Resource node: see the Nervous System for live state.</p>}
            </Card>
          </div>

          <Card>
            <h3 className="font-semibold">Deployment time-travel</h3>
            <p className="text-xs text-ink-soft">Every collected event per resource. Red = anomalous; indigo = deployments and configuration changes. Drag the slider to compare before and after the root change.</p>
            {tl && <Chart option={tl} height={320} label="Incident timeline by resource" onClick={(p) => { const d = p.data as { id?: string }; if (d?.id) void select(d.id); }} />}
          </Card>

          <Card>
            <h3 className="mb-3 font-semibold">Hypothesis comparison</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="text-[11px] uppercase tracking-wider text-ink-mute">
                  <tr><th className="py-2">Id</th><th>Hypothesis</th><th>Status</th><th>Tests passed / failed / untestable</th><th>Support</th><th>Against</th></tr>
                </thead>
                <tbody>
                  {report.hypotheses.map((h) => (
                    <tr key={h.id} onClick={() => void select(h.id)} className={cx("cursor-pointer border-t border-dome-100 hover:bg-dome-50/50", selected === h.id && "bg-dome-50")}>
                      <td className="py-2 font-mono text-xs">{h.id}</td>
                      <td className="max-w-md pr-3">{h.title}</td>
                      <td><Badge value={h.status} /></td>
                      <td className="font-mono text-xs">{["pass", "fail", "unknown"].map((r) => h.tests.filter((t) => t.result === r).length).join(" / ")}</td>
                      <td className="text-ok">{h.supporting_evidence.length}</td>
                      <td className="text-bad">{h.contradicting_evidence.length}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          <div className="grid gap-5 md:grid-cols-3">
            <Card>
              <h3 className="font-semibold">Recommended remediation</h3>
              <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm">{report.recommended_remediation.map((r, i) => <li key={i}>{r.action} on <b>{r.target}</b> <Badge value={r.risk === "low" ? "pass" : "warn"} label={`${r.risk} risk`} /></li>)}</ol>
              {report.remediation_notes.map((n) => <p key={n} className="mt-2 text-xs text-warn">{n}</p>)}
              <Link to={`/actions?incident=${report.incident.id}`} className="mt-4 inline-block text-sm font-medium text-dome-600 underline">Plan and approve in Actions →</Link>
            </Card>
            <Card><h3 className="font-semibold">Validation procedure</h3><ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-ink-soft">{report.validation_procedure.map((v) => <li key={v}>{v}</li>)}</ul></Card>
            <Card><h3 className="font-semibold">Preventive measures</h3><ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-ink-soft">{report.preventive_measures.map((v) => <li key={v}>{v}</li>)}{!report.preventive_measures.length && <li>None until the root cause is at least probable.</li>}</ul></Card>
          </div>
        </div>
      )}
    </Page>
  );
}
