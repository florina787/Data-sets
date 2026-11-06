import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { api, enc, getToken, post } from "../api";
import { useSession } from "../App";
import { CitationViewer, RefLink } from "../components/CitationViewer";
import { EvidencePanel } from "../components/EvidencePanel";
import { RecommendationCard } from "../components/RecommendationCard";
import { Timeline, WorkflowStatus } from "../components/Timeline";
import { Card, Chip, Empty, ErrorNote, StatusChip } from "../components/ui";
import { fmtTime, human } from "../format";
import { go } from "../router";
import { AuditEvent, CaseDetail, CaseSummary, ChatMessage, EvidenceResponse } from "../types";

export function Workspace({ caseId }: { caseId?: string }) {
  const { me, setLastCase } = useSession();
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [detail, setDetail] = useState<CaseDetail | null>(null);
  const [ev, setEv] = useState<EvidenceResponse | null>(null);
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [openRef, setOpenRef] = useState<string | null>(null);
  const [chat, setChat] = useState("");
  const [clarify, setClarify] = useState("");
  const [customerReport, setCustomerReport] = useState("");
  const [reason, setReason] = useState("");
  const idemKeys = useRef<Record<string, string>>({});

  useEffect(() => { api<CaseSummary[]>("/api/cases").then(setCases).catch(() => setCases([])); }, [me?.id]);

  const refresh = useCallback(async () => {
    if (!caseId) return;
    try {
      const [d, e, a, m] = await Promise.all([
        api<CaseDetail>(`/api/cases/${enc(caseId)}`),
        api<EvidenceResponse>(`/api/cases/${enc(caseId)}/evidence`),
        api<AuditEvent[]>(`/api/cases/${enc(caseId)}/audit`),
        api<ChatMessage[]>(`/api/cases/${enc(caseId)}/messages`),
      ]);
      setDetail(d); setEv(e); setEvents(a); setMessages(m); setError(null);
      setLastCase(caseId);
    } catch (err) { setDetail(null); setError((err as Error).message); }
  }, [caseId, setLastCase]);

  useEffect(() => { refresh(); }, [refresh, me?.id]);

  // Live status from persisted audit events (server-sent events).
  useEffect(() => {
    if (!caseId || !getToken() || typeof EventSource === "undefined") return;
    const lastSeq = events.length ? events[events.length - 1].seq : 0;
    const es = new EventSource(`/api/cases/${enc(caseId)}/events?access_token=${enc(getToken()!)}&after=${lastSeq}`);
    let timer: ReturnType<typeof setTimeout> | undefined;
    es.addEventListener("audit", () => { clearTimeout(timer); timer = setTimeout(refresh, 250); });
    es.onerror = () => es.close();
    return () => { clearTimeout(timer); es.close(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId, me?.id]);

  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true); setError(null);
    try { await fn(); } catch (err) { setError((err as Error).message); }
    finally { setBusy(false); await refresh(); }
  };

  if (!caseId) {
    return (
      <Card title="Copilot Workspace">
        <Empty>Select a case to investigate.</Empty>
        <ul className="case-pick">
          {cases.map((c) => (
            <li key={c.id}><button className="btn btn-ghost" onClick={() => go("workspace", c.id)}>
              {c.id} — {c.title}</button> <StatusChip status={c.status} /></li>
          ))}
        </ul>
      </Card>
    );
  }
  if (!detail) return <Card title={`Case ${caseId}`}><ErrorNote error={error} />{!error && <p>Loading…</p>}</Card>;

  const rec = detail.recommendation;
  const appr = detail.approval;
  const status = detail.status;
  const perms = new Set(me?.permissions ?? []);
  const canDecide = !!(appr && appr.status === "pending" && me && appr.required_roles.includes(me.role) &&
    perms.has("approval:decide") && !(appr.separation_of_duties && rec?.proposed_by === me.id));
  const canExecute = status === "APPROVED" && !!rec && !!me && rec.approval_requirement.executor_roles.includes(me.role)
    && perms.has("action:execute");
  const unknownExec = status === "EXECUTING" && detail.execution?.status === "unknown";
  const investigable = ["NEW", "FAILED", "REJECTED", "ESCALATED", "RECOMMENDATION_READY", "MONITORING", "RESOLVED"]
    .includes(status) && perms.has("case:investigate");
  const escalation = [...events].reverse().find((e) => e.to_status === "ESCALATED" || e.to_status === "NEEDS_INFORMATION");

  const keyFor = (approvalId: string) =>
    (idemKeys.current[approvalId] ??= `exec-${approvalId}-${Math.random().toString(36).slice(2, 10)}`);

  const send = (e: FormEvent) => {
    e.preventDefault();
    if (!chat.trim()) return;
    const text = chat; setChat("");
    act(() => post(`/api/cases/${enc(caseId)}/messages`, { text }));
  };

  return (
    <div className="workspace">
      <div className="ws-main stack">
        <Card title={<>{detail.id}: {detail.title}</>} actions={<StatusChip status={status} />}>
          <ErrorNote error={error} />
          <dl className="kv cols">
            <dt>Customer</dt><dd>{detail.customer.display_name} · {detail.customer.contact_phone}</dd>
            <dt>Service</dt><dd>{detail.service.id} · {detail.service.plan} ({detail.service.access_technology})</dd>
            <dt>Address</dt><dd>{detail.account.service_address} · area {detail.account.postal_area}</dd>
            <dt>Network mapping</dt><dd>{detail.mapping ? `${detail.mapping.asset_id} port ${detail.mapping.port}` : "unknown"}</dd>
            <dt>Equipment</dt><dd>{detail.equipment ? `${detail.equipment.model} fw ${detail.equipment.firmware}` : "unknown"}</dd>
            <dt>Linked incident</dt><dd>{detail.linked_incident_id ?? "none"}</dd>
          </dl>
          <blockquote className="excerpt" aria-label="Customer complaint (reported)">
            <span className="muted small">Customer reported: </span>{detail.complaint_text}
          </blockquote>
          <p className="muted small">{detail.status_reason && <>Status reason: {detail.status_reason}</>}</p>
          <WorkflowStatus events={events} running={detail.investigation_running} />
          <div className="toolbar">
            {investigable && (
              <button className="btn" disabled={busy || detail.investigation_running}
                onClick={() => act(() => post(`/api/cases/${enc(caseId)}/investigate`))}>
                {detail.investigation_running ? "Investigating…" : status === "NEW" ? "Run investigation" : "Re-investigate"}
              </button>
            )}
            {status === "RECOMMENDATION_READY" && rec && (
              <button className="btn" disabled={busy}
                onClick={() => act(() => post(`/api/cases/${enc(caseId)}/approvals`, { action: "request", recommendation_id: rec.id }))}>
                Request approval
              </button>
            )}
          </div>
        </Card>

        {escalation && ["ESCALATED", "NEEDS_INFORMATION"].includes(status) && (
          <Card title={status === "ESCALATED" ? "Escalated for analyst review" : "Insufficient evidence"}>
            <p>{String(escalation.detail.summary ?? escalation.detail.reason ?? "")}</p>
            {Array.isArray(escalation.detail.clarifying_questions) && (
              <><h4>Request for further evidence</h4>
                <ul>{(escalation.detail.clarifying_questions as string[]).map((q) => <li key={q}>{q}</li>)}</ul></>
            )}
            {status === "NEEDS_INFORMATION" && perms.has("case:clarify") && (
              <form className="form inline" onSubmit={(e) => { e.preventDefault(); act(() =>
                post(`/api/cases/${enc(caseId)}/clarifications`, { text: clarify })); setClarify(""); }}>
                <label>Clarification from customer<input value={clarify} onChange={(e) => setClarify(e.target.value)} minLength={2} required /></label>
                <button className="btn" disabled={busy}>Add and re-run</button>
              </form>
            )}
          </Card>
        )}

        {rec && (
          <RecommendationCard rec={rec} approval={appr} onOpenRef={setOpenRef}
            onChooseAlternative={["RECOMMENDATION_READY", "AWAITING_APPROVAL"].includes(status) && perms.has("case:investigate")
              ? (a) => act(() => post(`/api/cases/${enc(caseId)}/recommendations`, { action_type: a })) : undefined} />
        )}

        {(appr?.status === "pending" || canExecute || unknownExec || ["VERIFYING", "MONITORING"].includes(status) || detail.execution) && (
          <Card title="Approval, execution and recovery">
            <div className="stack">
              {appr?.status === "pending" && (
                canDecide ? (
                  <div className="toolbar">
                    <label className="grow">Decision reason (required to reject)
                      <input value={reason} onChange={(e) => setReason(e.target.value)} /></label>
                    <button className="btn" disabled={busy} onClick={() => act(() => post(`/api/cases/${enc(caseId)}/approvals`,
                      { action: "approve", approval_id: appr.id, payload_hash: rec!.payload_hash, reason }))}>Approve</button>
                    <button className="btn btn-danger" disabled={busy} onClick={() => act(() => post(`/api/cases/${enc(caseId)}/approvals`,
                      { action: "reject", approval_id: appr.id, payload_hash: rec!.payload_hash, reason }))}>Reject</button>
                  </div>
                ) : (
                  <p><Chip tone="warn">Pending approval</Chip> Requires role {appr.required_roles.join(" or ")}
                    {appr.separation_of_duties && " (not the proposer)"}. Your persona ({me?.role}) cannot decide it.</p>
                )
              )}
              {(canExecute || unknownExec) && appr && (
                <div>
                  <button className="btn" disabled={busy} onClick={() => act(() => post(`/api/cases/${enc(caseId)}/execute`,
                    { approval_id: appr.id }, { idempotencyKey: keyFor(appr.id) }))}>
                    {unknownExec ? "Reconcile and retry (same idempotency key)" : "Execute (simulated)"}
                  </button>
                  <p className="muted small">Execution re-checks authorization, policy version, payload hash and expiry.
                    A successful response does not prove service recovery.</p>
                </div>
              )}
              {status === "APPROVED" && !canExecute && <p>Approved. Execution requires role {rec?.approval_requirement.executor_roles.join(" or ")}.</p>}
              {detail.execution && (
                <p>Execution {detail.execution.id}: <Chip tone={detail.execution.status === "succeeded" ? "ok" : "warn"}>
                  {detail.execution.status}</Chip> via {detail.execution.connector} ({detail.execution.connector_mode}),
                  ref {detail.execution.external_ref ?? "—"}, attempts {detail.execution.attempts}.</p>
              )}
              {["VERIFYING", "MONITORING"].includes(status) && perms.has("recovery:verify") && (
                <form className="form inline" onSubmit={(e) => { e.preventDefault(); act(() =>
                  post(`/api/cases/${enc(caseId)}/verify`, { customer_report: customerReport || null })); }}>
                  <label>Customer follow-up report (optional)<input value={customerReport}
                    onChange={(e) => setCustomerReport(e.target.value)} placeholder="e.g. still dropping since the visit" /></label>
                  <button className="btn" disabled={busy}>Verify recovery</button>
                </form>
              )}
              {detail.recovery && (
                <div className={`recovery recovery-${detail.recovery.outcome}`}>
                  <StatusChip status={detail.recovery.outcome} /> {detail.recovery.healthy_samples} healthy /{" "}
                  {detail.recovery.unhealthy_samples} unhealthy of {detail.recovery.required_samples} required samples,
                  window {fmtTime(detail.recovery.window_start)}–{fmtTime(detail.recovery.window_end)}
                  {detail.recovery.simulation_time && <Chip tone="info">simulated, fast-forwarded telemetry</Chip>}
                  <ul>{detail.recovery.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
                </div>
              )}
            </div>
          </Card>
        )}

        <Card title="Copilot chat" actions={<span className="muted small">Answers cite sources; DEMO answers are retrieved excerpts</span>}>
          <ol className="chat" aria-live="polite">
            {messages.length === 0 && <li className="muted">Ask about this case, e.g. “Why not another modem restart?”</li>}
            {messages.map((m) => (
              <li key={m.id} className={`msg msg-${m.role}`}>
                <span className="small muted">{m.role === "user" ? "You" : `Copilot · ${m.generation_mode}`}</span>
                <div className="msg-text">{m.text}</div>
                {m.citations.length > 0 && <div className="small">{m.citations.map((c) =>
                  <RefLink key={c.id} refId={c.id} onOpen={setOpenRef} />)}</div>}
              </li>
            ))}
          </ol>
          <form className="form inline" onSubmit={send}>
            <label className="grow">Message<input value={chat} onChange={(e) => setChat(e.target.value)} placeholder="Ask about evidence, policy or next steps" /></label>
            <button className="btn" disabled={busy || !chat.trim()}>Send</button>
          </form>
        </Card>
      </div>

      <aside className="ws-side stack" aria-label="Evidence and history">
        <EvidencePanel ev={ev} onOpenRef={setOpenRef} compact />
        <Card title={`Earlier support contacts (${detail.support_history.length})`}>
          {detail.support_history.length === 0 ? <Empty>No earlier contacts.</Empty> : (
            <ol className="timeline">
              {detail.support_history.map((h) => (
                <li key={h.id}>
                  <time dateTime={h.occurred_at}>{fmtTime(h.occurred_at)}</time> · {h.channel} · {h.author_type}
                  {h.untrusted_content_flag && <> <Chip tone="bad">Untrusted content quarantined</Chip></>}
                  <div><strong>{h.summary}</strong></div>
                  <div className="small">{h.notes}</div>
                  <div className="small muted">Tried: {h.actions_taken.map(human).join(", ") || "nothing recorded"} · outcome {human(h.outcome)}</div>
                </li>
              ))}
            </ol>
          )}
        </Card>
        <Timeline events={events} />
      </aside>
      {openRef && <CitationViewer caseId={caseId} refId={openRef} onClose={() => setOpenRef(null)} />}
    </div>
  );
}
