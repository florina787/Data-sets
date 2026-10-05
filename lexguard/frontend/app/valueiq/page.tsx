"use client";

import { useState } from "react";
import { BarList } from "@/components/BarList";
import { ErrorBox, Kpi, LoadingBlock, PageHead, Panel } from "@/components/ui";
import { useApi } from "@/hooks/useApi";
import { useAppState } from "@/hooks/useAppState";
import { num, pct, usd } from "@/lib/format";

const DIMS = [["matter", "Matter"], ["practice", "Practice"], ["workflow", "Workflow"], ["provider", "Provider"]] as const;

export default function ValueIQPage() {
  const { userId } = useAppState();
  const { data: d, error, loading, reload } = useApi<any>("/value/metrics", userId);
  const [dim, setDim] = useState<(typeof DIMS)[number][0]>("matter");
  return (
    <div className="page">
      <PageHead title="ValueIQ" description="Business value beyond prompt counts: hours, review effort, rework, cost and outcome rates. All figures are synthetic estimates.">
        <button className="btn" onClick={reload}>Refresh</button>
      </PageHead>
      <ErrorBox error={error} onRetry={reload} />
      {loading && !d ? <LoadingBlock rows={6} /> : d && (<>
        <div className="notice" style={{ marginBottom: 12 }}>{d.label} Formula: <span className="mono">{d.formula}</span> (blended rate {usd(d.blended_rate_usd)}/h).</div>
        <div className="grid grid-6">
          <Kpi label="Traditional est. hours" value={num(d.totals.traditional_hours)} />
          <Kpi label="AI processing hours" value={num(d.totals.ai_processing_hours, 1)} />
          <Kpi label="Lawyer review hours" value={num(d.totals.lawyer_review_hours)} />
          <Kpi label="Rework hours" value={num(d.totals.rework_hours, 1)} />
          <Kpi label="Net hours saved" value={num(d.totals.net_hours_saved)} tone="good" hint={`${d.totals.productivity_improvement_pct}% productivity improvement`} />
          <Kpi label="Estimated value" value={usd(d.totals.estimated_value_usd)} tone="good" hint={`cost ${usd(d.totals.estimated_workflow_cost_usd)}`} />
          <Kpi label="Completion rate" value={pct(d.totals.completion_rate)} />
          <Kpi label="Abandonment rate" value={pct(d.totals.abandonment_rate, 1)} />
          <Kpi label="Human override rate" value={pct(d.totals.human_override_rate, 1)} />
          <Kpi label="Assurance failure rate" value={pct(d.totals.assurance_failure_rate, 1)} />
          <Kpi label="Runs" value={num(d.totals.runs)} />
        </div>
        <div className="row" style={{ margin: "14px 0 8px" }} role="tablist">
          {DIMS.map(([k, label]) => <button key={k} role="tab" aria-selected={dim === k} className={`btn btn-sm ${dim === k ? "btn-primary" : ""}`} onClick={() => setDim(k)}>By {label}</button>)}
        </div>
        <div className="grid" style={{ gridTemplateColumns: "1fr 2fr" }}>
          <Panel title="Net hours saved"><BarList data={d.by[dim].map((r: any) => ({ label: r.name, value: r.net_hours_saved }))} /></Panel>
          <Panel title={`Value by ${dim}`} bodyClass="table-wrap">
            <table className="table"><thead><tr><th>{dim}</th><th className="right">Trad. h</th><th className="right">Review h</th><th className="right">Rework h</th>
              <th className="right">Net saved h</th><th className="right">Est. value</th><th className="right">Completion</th><th className="right">Override</th><th className="right">Assur. fail</th></tr></thead>
              <tbody>{d.by[dim].map((r: any) => <tr key={r.id}><td className="small strong">{r.name}</td><td className="right mono">{num(r.traditional_hours)}</td>
                <td className="right mono">{num(r.lawyer_review_hours)}</td><td className="right mono">{num(r.rework_hours, 1)}</td><td className="right mono">{num(r.net_hours_saved)}</td>
                <td className="right mono">{usd(r.estimated_value_usd)}</td><td className="right mono">{pct(r.completion_rate)}</td><td className="right mono">{pct(r.human_override_rate)}</td>
                <td className="right mono">{pct(r.assurance_failure_rate)}</td></tr>)}</tbody></table>
          </Panel>
        </div>
      </>)}
    </div>
  );
}
