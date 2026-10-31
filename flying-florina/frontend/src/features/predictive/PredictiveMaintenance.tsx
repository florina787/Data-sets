import { useMutation } from "@tanstack/react-query";
import { AlertCircle, BrainCircuit, Radar } from "lucide-react";
import { useState } from "react";
import { Chart } from "@/components/Chart";
import { DataTable } from "@/components/DataTable";
import { QwenAnswerCard, QwenStatusCard, type QwenAnswer } from "@/components/QwenBlocks";
import { Badge, Card, ErrorBox, Loading, PageHeader } from "@/components/ui";
import { post } from "@/lib/api";
import { useApi } from "@/lib/hooks";

type Score = { aircraft: string; type: string; base: string; vibration_z: number | null; egt_z: number | null; oil_z: number | null; missing_days: number; data_quality: string; risk_score: number; priority: string };
type Pred = {
  method: { type: string; risk_score: string; priority: string; not_trustworthy_when: string[]; accuracy: string };
  scores: Score[]; distribution: { priority: string; aircraft: number }[]; anomaly_timeline: { day: string; aircraft_with_z_over_3: number }[];
  heatmap: { aircraft: string[]; sensors: string[]; cells: number[][] }; threshold: { vibration_index: number; label: string };
};
type Telemetry = { telemetry: { day: string; vibration_index: number | null; egt_delta_c: number | null; oil_pressure_index: number | null }[] };
type Explain = { available: boolean; reason?: string; error?: string; verdict?: string; explanation?: Omit<QwenAnswer, "type" | "meta" | "challenger">; challenger?: QwenAnswer["challenger"];
  meta?: QwenAnswer["meta"] };

export function PredictiveMaintenance() {
  const [base, setBase] = useState("");
  const [sel, setSel] = useState("AC-204");
  const q = useApi<Pred>(["predictive", base], `/api/predictive/overview${base ? `?base=${base}` : ""}`);
  const t = useApi<Telemetry>(["pm-telemetry", sel], `/api/aircraft/${sel}?days=90`);
  const ex = useMutation({ mutationFn: () => post<Explain>("/api/predictive/explain", { aircraft_id: sel }) });
  const d = q.data;
  const tel = t.data?.telemetry ?? [];
  const e = ex.data?.data;
  return (
    <div className="space-y-5">
      <PageHeader title="Predictive Maintenance" icon={<Radar className="h-5 w-5" />}
        subtitle="Explainable anomaly scoring from synthetic telemetry. Scores are deterministic statistics, not a trained model; no accuracy is claimed."
        actions={<select className="input !py-1 text-xs" value={base} onChange={(ev) => setBase(ev.target.value)} aria-label="Filter by base">
          <option value="">All bases</option>{["MAIN-HUB", "NORTH-FIELD", "EAST-DEPOT"].map((b) => <option key={b}>{b}</option>)}</select>} />
      {q.isLoading && <Loading label="Scoring telemetry" />}
      {q.error ? <ErrorBox error={q.error} /> : null}
      {d && (
        <>
          <div className="flex items-start gap-2 rounded-2xl border border-warn/30 bg-warn/[0.05] p-3 text-xs" role="note">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-warn" aria-hidden />
            <div><b>Method:</b> {d.method.type}. {d.method.risk_score}. Priority: {d.method.priority}. <b>{d.method.accuracy}</b></div>
          </div>
          <div className="grid gap-4 xl:grid-cols-3">
            <Card title="Risk distribution" subtitle="Aircraft by statistical priority">
              <Chart title="Risk distribution" spec={{ kind: "bar", x: d.distribution.map((x) => x.priority), series: [{ name: "Aircraft", data: d.distribution.map((x) => x.aircraft) }] }} height={240} />
            </Card>
            <Card title="Anomaly timeline" subtitle="Aircraft-days with vibration z > 3 vs own baseline" className="xl:col-span-2">
              <Chart title="Anomaly timeline" spec={{ kind: "bar", x: d.anomaly_timeline.map((x) => x.day), series: [{ name: "Aircraft with z > 3", data: d.anomaly_timeline.map((x) => x.aircraft_with_z_over_3) }] }} height={240} />
            </Card>
          </div>
          <div className="grid gap-4 xl:grid-cols-2">
            <Card title="Component health heatmap" subtitle="|z| per sensor, top 20 aircraft by risk · click a row to inspect">
              <Chart title="Component health heatmap" spec={{ kind: "heatmap", x: d.heatmap.sensors, y: d.heatmap.aircraft, cells: d.heatmap.cells, series: [] }} height={420}
                onSelect={(p) => { const row = (p.data as number[])[1]; if (d.heatmap.aircraft[row]) setSel(d.heatmap.aircraft[row]); }} />
            </Card>
            <Card title="Maintenance priority matrix" subtitle="Risk score vs missing readings (data quality)">
              <Chart title="Priority matrix" spec={{ kind: "scatter", x: [], xLabel: "Risk score (|z|)", yLabel: "Missing days", series: [{ name: "Aircraft", data: [], points: d.scores.slice(0, 60).map((s) => [s.risk_score, s.missing_days, s.aircraft]) }] }} height={420}
                onSelect={(p) => setSel(String((p.data as (string | number)[])[2]))} />
            </Card>
          </div>
          <div className="grid gap-4 xl:grid-cols-[1.4fr_1fr]">
            <Card title={`Multi-sensor time series · ${sel}`} subtitle="Vibration index, EGT delta and oil pressure index (synthetic) · dashed line = fictional demo threshold"
              actions={<select className="input !py-1 text-xs" value={sel} onChange={(ev) => setSel(ev.target.value)} aria-label="Select aircraft">{d.scores.slice(0, 40).map((s) => <option key={s.aircraft}>{s.aircraft}</option>)}</select>}>
              {t.isLoading ? <Loading /> : (
                <>
                  <Chart title="Vibration" spec={{ kind: "line", x: tel.map((r) => r.day), series: [{ name: "Vibration index", data: tel.map((r) => r.vibration_index) }], markLine: { y: d.threshold.vibration_index, label: "Demo threshold" } }} height={200} />
                  <Chart title="EGT and oil" spec={{ kind: "line", x: tel.map((r) => r.day), series: [{ name: "EGT delta (C)", data: tel.map((r) => r.egt_delta_c) }, { name: "Oil pressure index", data: tel.map((r) => r.oil_pressure_index) }] }} height={200} />
                </>
              )}
            </Card>
            <Card title="Prediction explanation" subtitle="Local Qwen explains the scores; the Evidence Challenger checks every number"
              actions={<button className="btn btn-primary !py-1 text-xs" onClick={() => ex.mutate()} disabled={ex.isPending} data-testid="explain-pm"><BrainCircuit className="h-3.5 w-3.5" />{ex.isPending ? "Explaining…" : `Explain ${sel}`}</button>}>
              {(() => {
                const s = d.scores.find((x) => x.aircraft === sel);
                return s ? (
                  <div className="mb-3 flex flex-wrap gap-1.5">
                    <Badge tone={s.priority === "high" ? "red" : s.priority === "medium" ? "amber" : "teal"}>priority {s.priority}</Badge>
                    <Badge tone="gray">risk |z| {s.risk_score}</Badge><Badge tone="gray">vibration z {s.vibration_z}</Badge><Badge tone="gray">EGT z {s.egt_z}</Badge>
                    <Badge tone={s.data_quality === "ok" ? "teal" : "amber"}>data quality: {s.data_quality}</Badge>
                  </div>
                ) : null;
              })()}
              {ex.error ? <ErrorBox error={ex.error} /> : null}
              {e && !e.available && <QwenStatusCard b={{ type: "qwen_status", available: false, reason: e.reason, note: "No explanation was generated; the scores above are the evidence." }} />}
              {e && e.available && e.error && <QwenStatusCard b={{ type: "qwen_status", available: true, error: e.error, note: "Qwen did not finish." }} />}
              {e?.explanation && e.meta && e.challenger && <QwenAnswerCard b={{ type: "qwen_answer", ...e.explanation, meta: e.meta, challenger: e.challenger } as QwenAnswer} />}
              {e && e.verdict === "reject" && <QwenStatusCard b={{ type: "qwen_status", available: true, rejected: true, challenger: e.challenger, note: "Rejected: unsupported claims." }} />}
              <p className="label mt-4 mb-1">Do not trust these scores when</p>
              <ul className="space-y-1 text-xs muted">{d.method.not_trustworthy_when.map((m) => <li key={m}>• {m}</li>)}</ul>
            </Card>
          </div>
          <Card title="Risk prioritization" subtitle="All scored aircraft">
            <DataTable label="Anomaly scores" columns={[{ key: "aircraft", label: "Aircraft" }, { key: "type", label: "Type" }, { key: "base", label: "Base" }, { key: "priority", label: "Priority" }, { key: "risk_score", label: "Risk |z|" }, { key: "vibration_z", label: "Vibration z" }, { key: "egt_z", label: "EGT z" }, { key: "oil_z", label: "Oil z" }, { key: "missing_days", label: "Missing days" }, { key: "data_quality", label: "Data quality" }]} rows={d.scores} />
          </Card>
        </>
      )}
    </div>
  );
}
