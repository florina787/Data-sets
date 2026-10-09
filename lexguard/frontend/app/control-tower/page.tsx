"use client";

import { BarList } from "@/components/BarList";
import { Badge, ErrorBox, Kpi, LoadingBlock, PageHead, Panel, StatusPill } from "@/components/ui";
import { useApi } from "@/hooks/useApi";
import { useAppState } from "@/hooks/useAppState";
import { num, pct, statusTone } from "@/lib/format";

export default function ControlTowerPage() {
  const { userId } = useAppState();
  const { data: d, error, loading, reload } = useApi<any>("/control-tower/metrics", userId);
  return (
    <div className="page">
      <PageHead title="Legal AI Control Tower" description="Firm-wide AI governance posture. Synthetic history (Apr-Sep 2026) combined with live demo activity.">
        <button className="btn" onClick={reload}>Refresh</button>
      </PageHead>
      <ErrorBox error={error} onRetry={reload} />
      {loading && !d ? <LoadingBlock rows={6} /> : d && (<>
        <div className="grid grid-6">
          <Kpi label="AI-enabled matters" value={d.ai_enabled_matters} hint={`of ${d.total_matters}`} />
          <Kpi label="AI-restricted matters" value={d.ai_restricted_matters} tone="warn" tip="Client prohibits all AI or external AI." />
          <Kpi label="Active AI workflows" value={d.active_ai_workflows} />
          <Kpi label="Assurance pass rate" value={pct(d.assurance_pass_rate)} tone="good" />
          <Kpi label="Citation failure rate" value={pct(d.citation_failure_rate, 1)} tone="warn" />
          <Kpi label="Human-review rate" value={pct(d.human_review_rate)} tone="good" />
          <Kpi label="Playbook deviations" value={num(d.playbook_deviations)} />
          <Kpi label="Policy violations blocked" value={num(d.policy_violations_blocked)} tone="bad" />
          <Kpi label="High-risk events" value={num(d.high_risk_events)} tone="bad" />
          <Kpi label="Est. hours saved" value={num(d.estimated_hours_saved)} tone="good" hint="Synthetic estimate" />
          <Kpi label="Rework hours" value={num(d.rework_hours, 1)} hint="Synthetic estimate" />
          <Kpi label="Live security events" value={Object.values(d.live_security_events as Record<string, number>).reduce((a, b) => a + b, 0)} tone="bad" tip="WARNING/CRITICAL audit events from this demo session." />
        </div>
        <div className="grid grid-3" style={{ marginTop: 12 }}>
          <Panel title="Provider usage (runs)"><BarList data={Object.entries(d.provider_usage).map(([label, value]) => ({ label, value: value as number }))} /></Panel>
          <Panel title="Practice-group adoption (runs)"><BarList data={Object.entries(d.practice_adoption).map(([label, value]) => ({ label, value: value as number }))} /></Panel>
          <Panel title="Live security events">{Object.keys(d.live_security_events).length === 0 ? <div className="muted small">None yet. Try Project Aurora or Matter Beta in the Copilot.</div> :
            Object.entries(d.live_security_events).map(([k, v]) => <div key={k} className="row small" style={{ justifyContent: "space-between" }}><span>{k}</span><Badge tone="bad">{v as number}</Badge></div>)}</Panel>
        </div>
        <div style={{ marginTop: 12 }}><Panel title="Matter AI posture" bodyClass="table-wrap">
          <table className="table"><thead><tr><th>Matter</th><th>Client</th><th>Practice</th><th>AI status</th><th>Risk</th></tr></thead>
            <tbody>{d.matters.map((m: any) => <tr key={m.matter_id}><td className="strong">{m.name}</td><td>{m.client}</td><td>{m.practice}</td>
              <td><StatusPill status={m.ai_status === "AI PROHIBITED" ? "PROHIBITED" : m.ai_status === "INTERNAL AI ONLY" ? "RESTRICTED" : "PERMITTED_WITH_CONTROLS"} label={m.ai_status} /></td>
              <td><Badge tone={statusTone(m.risk)}>{m.risk}</Badge></td></tr>)}</tbody></table>
        </Panel></div>
      </>)}
    </div>
  );
}
