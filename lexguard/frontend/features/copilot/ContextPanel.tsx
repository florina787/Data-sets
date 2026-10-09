"use client";

import { useEffect, useMemo, useState } from "react";
import { Badge, Bar, Empty, ErrorBox, Spinner, StatusPill, Tip } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { humanize, splitHighlight, statusTone } from "@/lib/format";
import type { AuditEvent, CopilotResponse, Evidence } from "@/types/api";
import { AgentTrace } from "./ResultCards";

export const TABS = ["evidence", "sources", "risk", "playbook", "policy", "trace", "approval", "audit"] as const;
export type Tab = (typeof TABS)[number];
const TAB_LABEL: Record<Tab, string> = { evidence: "Evidence", sources: "Sources", risk: "Risk", playbook: "Playbook", policy: "Policy",
  trace: "Agent Trace", approval: "Approval", audit: "Audit" };

function EvidenceDetail({ ev }: { ev: Evidence }) {
  const h = splitHighlight(ev.text, ev.highlight);
  return (
    <div className="stack">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div><div className="strong">{ev.doc_title}</div><div className="tiny muted mono">{ev.doc_id} · {ev.heading}</div></div>
        <StatusPill status={ev.evidence_status} />
      </div>
      <div className="section-title">Source evidence</div>
      <div className="evidence-text">{h.before}{h.match && <mark>{h.match}</mark>}{h.after}</div>
      <div className="section-title">Citation verification</div>
      {ev.verification.map((v) => (
        <div key={v.pid} className="small" style={{ marginBottom: 6 }}>
          <div className="row"><StatusPill status={v.status} /><span className="tiny mono muted">{v.doc_id} §{v.section_id}</span></div>
          <div>{v.claim}</div><div className="tiny muted">{v.reasons.join(" ")}</div>
        </div>
      ))}
      <div className="section-title">Playbook comparison</div>
      <div className="grid" style={{ gridTemplateColumns: "1fr 1fr", gap: 8 }}>
        <div className="evidence-text small"><div className="tiny muted strong">CONTRACT CLAUSE</div>{ev.text}</div>
        <div className="evidence-text small"><div className="tiny muted strong">PLAYBOOK {ev.playbook.rule_id ?? ""}</div>
          {ev.playbook.playbook_source?.text ?? ev.playbook.standard_position}</div>
      </div>
      <div className="row"><StatusPill status={ev.playbook.result} /><span className="small">{ev.playbook.standard_position}</span></div>
    </div>
  );
}

function EvidenceTab({ resp, selected, onSelect, extraEvidence }:
  { resp: CopilotResponse; selected: string | null; onSelect: (id: string) => void; extraEvidence: Record<string, Evidence> }) {
  const [filter, setFilter] = useState<"review" | "all">("review");
  const evMap = useMemo(() => ({ ...Object.fromEntries(resp.evidence.map((e) => [e.finding_id, e])), ...extraEvidence }),
    [resp.evidence, extraEvidence]);
  const sel = selected ? evMap[selected] : resp.evidence[0];
  if (!resp.findings.length && !resp.evidence.length) {
    if (resp.citations.length) {
      return <div className="stack">{resp.citations.map((c: any) => (
        <div key={c.pid} className="small"><div className="row"><StatusPill status={c.status} /><span className="mono tiny">{c.doc_id} §{c.section_id}</span></div>
          <div>{c.claim}</div>{c.evidence_text && <div className="evidence-text tiny">{c.evidence_text}</div>}</div>))}</div>;
    }
    return <Empty title="No evidence for this response">Ask the Copilot to review documents, then click a finding.</Empty>;
  }
  const rows = filter === "review" ? resp.findings.filter((f) => f.evidence_status !== "VERIFIED" || f.playbook_result !== "ALIGNED")
    : resp.findings;
  return (
    <div className="stack">
      {selected && !evMap[selected] ? <Spinner label="Loading evidence" /> : sel ? <EvidenceDetail ev={sel} /> : null}
      <div className="row" style={{ justifyContent: "space-between", marginTop: 8 }}>
        <span className="section-title" style={{ margin: 0 }}>Findings ({rows.length})</span>
        <select className="select small" value={filter} onChange={(e) => setFilter(e.target.value as any)} aria-label="Finding filter">
          <option value="review">Deviations &amp; issues</option><option value="all">All findings</option>
        </select>
      </div>
      <div className="list">
        {rows.map((f) => (
          <div key={f.finding_id} className={`list-item clickable ${selected === f.finding_id ? "selected" : ""}`} role="button" tabIndex={0}
            onClick={() => onSelect(f.finding_id)} onKeyDown={(e) => e.key === "Enter" && onSelect(f.finding_id)}
            style={selected === f.finding_id ? { background: "var(--accent-weak)" } : undefined}>
            <StatusPill status={f.playbook_result} />
            <div style={{ flex: 1 }}><div className="small strong">{f.doc_title}</div><div className="tiny muted">{f.topic ?? f.heading}</div></div>
            {f.evidence_status !== "VERIFIED" && <Badge tone="warn">evidence</Badge>}
          </div>
        ))}
      </div>
    </div>
  );
}

function ApprovalTab({ resp, userId, onDecided }: { resp: CopilotResponse; userId: string; onDecided: (s: string) => void }) {
  const [destination, setDestination] = useState(resp.draft?.client_facing ? "external_client" : "internal");
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [result, setResult] = useState<any>(null);
  useEffect(() => { setResult(null); setError(null); }, [resp.request_id]);
  const a = resp.approval;
  if (!a) return <Empty title="No approval required">Deterministic answers and blocked requests do not create work product.</Empty>;
  const act = async (kind: "approve" | "reject") => {
    setBusy(true); setError(null);
    try {
      const r = kind === "approve" ? await api.approve(userId, a.work_product_id, destination, comment) : await api.reject(userId, a.work_product_id, comment);
      setResult(r); onDecided(r.status);
    } catch (e) { setError(e as ApiError); } finally { setBusy(false); }
  };
  return (
    <div className="stack">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div><div className="strong">Work product</div><div className="mono tiny">{a.work_product_id}</div></div>
        <StatusPill status={result?.status ?? "PENDING_REVIEW"} />
      </div>
      <div className="small">{a.reason}</div>
      <div className="grid" style={{ gridTemplateColumns: "1fr 1fr", gap: 8 }}>
        <div className="metric"><div className="l">Review level</div><div className="small strong">{a.label}</div></div>
        <div className="metric"><div className="l">Approver</div><div className="small strong">{a.required_roles.map(humanize).join(" / ")}</div></div>
        <div className="metric"><div className="l">Assurance</div><div className="small strong">{resp.assurance ? `${resp.assurance.score_pct}% · ${humanize(resp.assurance.status)}` : "-"}</div></div>
        <div className="metric"><div className="l">External delivery</div><div className="small strong">{a.external_delivery_allowed ? "Allowed after approval" : "Blocked until assurance passes"}</div></div>
      </div>
      {resp.assurance?.blocking_issues?.length ? (
        <div className="notice"><strong>Open issues:</strong><ul style={{ margin: "4px 0 0", paddingLeft: 18 }}>
          {resp.assurance.blocking_issues.map((b) => <li key={b}>{b}</li>)}</ul></div>) : null}
      {!result && (<>
        <label className="small strong" htmlFor="dest">Destination</label>
        <select id="dest" className="select" value={destination} onChange={(e) => setDestination(e.target.value)}>
          <option value="internal">Internal use</option><option value="external_client">External - client</option>
        </select>
        <label className="small strong" htmlFor="comment">Reviewer comment</label>
        <textarea id="comment" className="textarea" value={comment} onChange={(e) => setComment(e.target.value)} placeholder="Record your review rationale" />
        <div className="row">
          <button className="btn btn-primary" disabled={busy} onClick={() => act("approve")}>Approve as lawyer</button>
          <button className="btn btn-danger" disabled={busy} onClick={() => act("reject")}>Reject</button>
          {busy && <Spinner label="Recording decision" />}
        </div>
      </>)}
      {error && <ErrorBox error={error} />}
      {error?.code === "ESCALATION_REQUIRES_PARTNER" && <div className="notice">Switch the signed-in user to <strong>Eleanor Hart — Partner</strong> to approve escalations.</div>}
      {result && <div className={`status-banner tone-${statusTone(result.status)}`}>Decision recorded: <strong>{humanize(result.status)}</strong> for {humanize(result.destination)}. See the Audit tab.</div>}
    </div>
  );
}

const CHAIN: [string, string][] = [["REQUEST_RECEIVED", "User / Task"], ["ACCESS_DECISION", "Matter access"], ["ETHICAL_WALL_DECISION", "Ethical wall"],
  ["POLICY_DECISION", "Policy"], ["ROUTING_DECISION", "Workflow"], ["PROVIDER_INVOKED", "Provider"], ["RETRIEVAL", "Evidence"],
  ["WORK_PRODUCT_CREATED", "AI output"], ["ASSURANCE_RESULT", "Assurance"], ["HUMAN_REVIEW_APPROVED", "Lawyer approval"],
  ["HUMAN_REVIEW_REJECTED", "Lawyer rejection"], ["FINAL_STATUS", "Final status"]];

function AuditTab({ resp, userId, refreshKey }: { resp: CopilotResponse; userId: string; refreshKey: number }) {
  const [events, setEvents] = useState<AuditEvent[] | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  useEffect(() => {
    setEvents(null); setError(null);
    api.trace(userId, resp.request_id).then((r) => setEvents(r.chain)).catch(setError);
  }, [resp.request_id, userId, refreshKey]);
  if (error) return <ErrorBox error={error} />;
  if (!events) return <Spinner label="Loading audit chain" />;
  const types = new Set(events.map((e) => e.event_type));
  return (
    <div className="stack">
      <div className="row" style={{ gap: 4 }}>
        {CHAIN.filter(([t]) => types.has(t)).map(([t, label], i, arr) => (
          <span key={t} className="row" style={{ gap: 4 }}><Badge tone="info">{label}</Badge>{i < arr.length - 1 && <span className="muted">→</span>}</span>))}
      </div>
      <div className="tiny muted">Request <span className="mono">{resp.request_id}</span> · hash-chained, tamper-evident</div>
      <div className="list">
        {events.map((e) => (
          <div key={e.event_id} className="list-item">
            <Badge tone={e.severity === "INFO" ? "neutral" : statusTone(e.severity === "CRITICAL" ? "blocked" : "warn")}>{e.severity}</Badge>
            <div style={{ flex: 1 }}><div className="small strong">{humanize(e.event_type)}</div>
              <div className="tiny muted mono" style={{ wordBreak: "break-all" }}>{JSON.stringify(e.payload).slice(0, 220)}</div></div>
            <span className="tiny muted mono" title={e.hash}>{e.hash.slice(0, 8)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function ContextPanel({ resp, tab, setTab, selected, onSelect, extraEvidence, userId, onDecided, auditKey }: {
  resp: CopilotResponse | null; tab: Tab; setTab: (t: Tab) => void; selected: string | null; onSelect: (id: string) => void;
  extraEvidence: Record<string, Evidence>; userId: string; onDecided: (s: string) => void; auditKey: number;
}) {
  const counts: Partial<Record<Tab, number>> = resp ? { evidence: resp.findings.length || resp.citations.length, sources: resp.sources.length,
    playbook: resp.playbook_deviations.length, trace: resp.agent_trace.length } : {};
  return (
    <>
      <div className="tabs" role="tablist" aria-label="Context">
        {TABS.map((t) => (
          <button key={t} role="tab" className="tab" aria-selected={tab === t} onClick={() => setTab(t)}>
            {TAB_LABEL[t]}{counts[t] ? <span className="count">{counts[t]}</span> : null}
          </button>
        ))}
      </div>
      <div className="panel-body" style={{ overflowY: "auto", flex: 1 }} role="tabpanel">
        {!resp ? <Empty title="Context appears here">Evidence, sources, risk, playbook, policy, agent trace, approval and audit for each Copilot answer.</Empty> : (
          <>
            {tab === "evidence" && <EvidenceTab resp={resp} selected={selected} onSelect={onSelect} extraEvidence={extraEvidence} />}
            {tab === "sources" && (resp.sources.length ? <div className="stack">{resp.sources.map((s, i) => (
              <div key={i} className="small"><div className="row"><span className="strong">{s.title}</span>
                {s.untrusted_instruction_detected && <Badge tone="bad">untrusted instruction</Badge>}</div>
                <div className="tiny muted mono">{s.doc_id} §{s.section_id} · {humanize(s.kind)}</div>
                <div className="evidence-text tiny">{s.text}</div></div>))}</div>
              : <Empty title="No retrieved sources">{resp.status === "ACCESS_DENIED" ? "Access was denied before retrieval." : "This answer used deterministic controls or matter documents (see Evidence)."}</Empty>)}
            {tab === "risk" && (
              <div className="stack">
                <div className="row"><Badge tone={statusTone(resp.risk)}>Risk {resp.risk}</Badge>{resp.matterguard && <span className="small muted">score {resp.matterguard.risk_score}</span>}</div>
                {resp.suitability && <>
                  <div className="section-title">AI suitability (deterministic) <Tip text="Scores are computed by fixed formulas from task and matter factors - same inputs, same scores." /></div>
                  {["ai_suitability", "agentic_suitability", "legal_judgment_risk", "confidentiality_risk", "privilege_risk", "autonomy_risk",
                    "evidence_requirement", "human_review_requirement"].map((k) => (
                    <div key={k}><div className="row tiny" style={{ justifyContent: "space-between" }}><span>{humanize(k)}</span><span className="mono">{resp.suitability![k]}</span></div>
                      <Bar value={resp.suitability![k] / 100} tone={k.endsWith("risk") ? (resp.suitability![k] >= 70 ? "bad" : resp.suitability![k] >= 40 ? "warn" : "good") : undefined} /></div>))}
                </>}
                {resp.privilege_flags.length > 0 && <><div className="section-title">Potential privilege / confidentiality</div>
                  {resp.privilege_flags.map((f, i) => <div key={i} className="small"><Badge tone="bad">{f.label}</Badge> <span className="mono tiny">{f.doc_id}</span> {f.detail}</div>)}</>}
              </div>)}
            {tab === "playbook" && (resp.playbook_deviations.length ? <div className="list">{resp.playbook_deviations.map((d) => (
              <div key={d.finding_id} className="list-item clickable" role="button" tabIndex={0} onClick={() => d.doc_id && onSelect(d.finding_id)}>
                <StatusPill status={d.result} /><div><div className="small strong">{d.doc_title}</div><div className="tiny">{d.topic} · {d.rule_id}</div>
                  <div className="tiny muted">{d.standard_position}</div></div></div>))}</div>
              : <Empty title="No playbook deviations in this answer" />)}
            {tab === "policy" && (resp.matterguard ? (
              <div className="stack">
                <div className="row"><StatusPill status={resp.matterguard.decision} /><span className="small">{resp.matterguard.human_review_label}</span></div>
                {resp.matterguard.client_policy_summary && <div className="notice">{resp.matterguard.client_policy_summary}</div>}
                <div className="section-title">Policy evidence</div>
                <table className="table"><tbody>{resp.matterguard.policy_evidence.map((e) => (
                  <tr key={e.rule_id + e.description}><td><Badge tone={e.effect === "PROHIBIT" ? "bad" : e.effect === "RESTRICT" ? "warn" : "neutral"}>{e.rule_id}</Badge></td>
                    <td className="small">{e.description}{e.source_doc_id && <div className="tiny muted mono">{e.source_doc_id} §{e.source_section_id}</div>}</td></tr>))}</tbody></table>
                <div className="section-title">Tools</div>
                <div className="row">{resp.matterguard.allowed_tools.map((t) => <Badge key={t} tone="good">{t}</Badge>)}
                  {resp.matterguard.blocked_tools.map((t) => <Badge key={t} tone="bad">✕ {t}</Badge>)}</div>
                {resp.routing && <><div className="section-title">AI Router</div>
                  <table className="table"><tbody>{resp.routing.options.map((o) => (
                    <tr key={o.route}><td className="small">{o.selected ? <strong>{humanize(o.route)}</strong> : humanize(o.route)}</td>
                      <td className="tiny muted">{o.selected && <Badge tone="good">selected</Badge>} {o.reason}</td></tr>))}</tbody></table></>}
              </div>) : <Empty title={resp.status === "ACCESS_DENIED" ? "Stopped before policy evaluation" : "No policy evaluation"}>
                {resp.status === "ACCESS_DENIED" ? "Access control and the ethical wall run first. The request was denied and audited before MatterGuard, routing or retrieval ran." : null}</Empty>)}
            {tab === "trace" && <div className="stack"><AgentTrace steps={resp.agent_trace} defaultOpen />
              <div className="tiny muted">Graph path: <span className="mono">{resp.metrics.graph_path.join(" → ")}</span></div>
              <div className="tiny muted">Agents: {resp.metrics.agents_invoked.join(", ")} · Tools: {resp.metrics.tools_invoked.join(", ") || "none"} ·
                {" "}{resp.metrics.latency_ms} ms · est. ${resp.metrics.est_cost_usd} · paid LLM calls {resp.metrics.paid_llm_calls}</div></div>}
            {tab === "approval" && <ApprovalTab resp={resp} userId={userId} onDecided={onDecided} />}
            {tab === "audit" && <AuditTab resp={resp} userId={userId} refreshKey={auditKey} />}
          </>
        )}
      </div>
    </>
  );
}
