"use client";

import { useState } from "react";
import { Badge, ErrorBox, Kpi, PageHead, Panel, Spinner, StatusPill } from "@/components/ui";
import { useApi } from "@/hooks/useApi";
import { useAppState } from "@/hooks/useAppState";
import { api, ApiError } from "@/lib/api";
import { humanize, statusTone } from "@/lib/format";
import type { MatterGuardResult, MatterSummary } from "@/types/api";

export default function MatterGuardPage() {
  const { userId, matterId } = useAppState();
  const matters = useApi<MatterSummary[]>("/matters", userId);
  const providers = useApi<any[]>("/providers", userId);
  const [form, setForm] = useState({ matter_id: matterId, provider_id: "P-MOCK-LEGAL-AI", destination: "internal", intent: "contract_review" });
  const [task, setTask] = useState("Review the contracts in this matter for change-of-control clauses.");
  const [res, setRes] = useState<MatterGuardResult | null>(null);
  const [route, setRoute] = useState<any>(null);
  const [err, setErr] = useState<ApiError | null>(null);
  const [busy, setBusy] = useState(false);
  const run = async () => {
    setBusy(true); setErr(null);
    try {
      setRes(await api.post<MatterGuardResult>("/matterguard/evaluate", userId, { ...form, provider_id: form.provider_id || null }));
      setRoute(await api.post<any>("/routing/recommend", userId, { matter_id: form.matter_id, task }).catch(() => null));
    } catch (e) { setErr(e as ApiError); setRes(null); } finally { setBusy(false); }
  };
  return (
    <div className="page">
      <PageHead title="MatterGuard" description="Deterministic evaluation of user, client, matter, task, provider, document sensitivity and destination. No LLM participates in these decisions." />
      <div className="grid grid-2">
        <Panel title="Evaluate a request">
          <div className="stack">
            <label className="small strong">Matter<select className="select" style={{ width: "100%" }} value={form.matter_id} onChange={(e) => setForm({ ...form, matter_id: e.target.value })}>
              {(matters.data ?? []).map((m) => <option key={m.matter_id} value={m.matter_id}>{m.name}</option>)}</select></label>
            <label className="small strong">Provider<select className="select" style={{ width: "100%" }} value={form.provider_id} onChange={(e) => setForm({ ...form, provider_id: e.target.value })}>
              <option value="">(none)</option>{(providers.data ?? []).map((p) => <option key={p.provider_id} value={p.provider_id}>{p.name}</option>)}</select></label>
            <label className="small strong">Output destination<select className="select" style={{ width: "100%" }} value={form.destination} onChange={(e) => setForm({ ...form, destination: e.target.value })}>
              {["internal", "external_client", "external_court", "external_public"].map((d) => <option key={d} value={d}>{humanize(d)}</option>)}</select></label>
            <label className="small strong">Task type<select className="select" style={{ width: "100%" }} value={form.intent} onChange={(e) => setForm({ ...form, intent: e.target.value })}>
              {["contract_review", "research", "draft_memo", "client_draft", "knowledge_question", "legal_judgment"].map((d) => <option key={d} value={d}>{humanize(d)}</option>)}</select></label>
            <label className="small strong">Task text (for AI Router)<textarea className="textarea" value={task} onChange={(e) => setTask(e.target.value)} /></label>
            <div className="row"><button className="btn btn-primary" onClick={run} disabled={busy}>Evaluate</button>{busy && <Spinner />}</div>
            <ErrorBox error={err} />
          </div>
        </Panel>
        <Panel title="Decision">
          {!res ? <div className="empty"><strong>No evaluation yet</strong>Choose inputs and press Evaluate.</div> : (
            <div className="stack">
              <div className="grid grid-3">
                <Kpi label="Decision" value={<StatusPill status={res.decision} />} />
                <Kpi label="Risk" value={<Badge tone={statusTone(res.risk)}>{res.risk}</Badge>} hint={`score ${res.risk_score}`} />
                <Kpi label="Human review" value={<span className="small">{res.human_review_label}</span>} />
              </div>
              <div className="small"><strong>External distribution:</strong> {humanize(res.external_distribution)}</div>
              {res.reasons.map((r) => <div key={r} className="small">• {r}</div>)}
              {res.alternatives.length > 0 && <div className="notice">Alternatives: {res.alternatives.join(" ")}</div>}
              <div className="section-title">Policy evidence</div>
              <table className="table"><tbody>{res.policy_evidence.map((e) => (
                <tr key={e.rule_id + e.description}><td><Badge tone={e.effect === "PROHIBIT" ? "bad" : e.effect === "RESTRICT" ? "warn" : "neutral"}>{e.rule_id}</Badge></td>
                  <td className="small">{e.description}</td><td className="tiny mono muted">{e.source_doc_id} §{e.source_section_id}</td></tr>))}</tbody></table>
              <div className="section-title">Allowed / blocked tools</div>
              <div className="row">{res.allowed_tools.map((t) => <Badge key={t} tone="good">{t}</Badge>)}{res.blocked_tools.map((t) => <Badge key={t} tone="bad">✕ {t}</Badge>)}</div>
            </div>)}
        </Panel>
      </div>
      {route && (
        <div style={{ marginTop: 12 }}><Panel title={<>AI Router: <StatusPill status="ok" label={humanize(route.routing.route)} /></>}>
          <div className="grid grid-4" style={{ marginBottom: 10 }}>
            {["ai_suitability", "agentic_suitability", "legal_judgment_risk", "autonomy_risk"].map((k) => <Kpi key={k} label={humanize(k)} value={route.suitability[k]} hint={route.suitability.bands[k]} />)}
          </div>
          <table className="table"><thead><tr><th>Route</th><th>Decision</th></tr></thead><tbody>{route.routing.options.map((o: any) => (
            <tr key={o.route}><td>{o.selected ? <strong>{humanize(o.route)}</strong> : humanize(o.route)}</td><td className="small">{o.selected && <Badge tone="good">selected</Badge>} {o.reason}</td></tr>))}</tbody></table>
        </Panel></div>)}
    </div>
  );
}
