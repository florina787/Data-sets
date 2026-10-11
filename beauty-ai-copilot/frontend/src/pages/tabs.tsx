import { Fragment, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, idempotencyKey } from "../api";
import { useApp } from "../App";
import { Action, Badge, Card, DiffView, ErrorBox, SourceLink } from "../components";
import { pct, shortDigest, when } from "../format";
import type { TabProps } from "./ChangePage";

const can = (me: any, p: string) => !!me?.permissions?.includes(p);

// ------------------------------------------------------------------ Overview

export function OverviewTab({ d }: TabProps) {
  const it = d.interrupt?.interrupt;
  const chain = d.release_readiness;
  return (
    <div>
      <Card title="Next steps">
        {it && <div className="note">Workflow paused for human input: <strong>{it.awaiting}</strong>{it.detail ? ` — ${it.detail}` : ""}</div>}
        <ul>{d.next_steps.map((s: any) => <li key={s.label}>{s.label} {s.you_can ? <Badge s="OK" label="you can" /> : <span className="small muted">(another role: {s.permission})</span>}</li>)}</ul>
        <div className="small muted">Permitted next states: {d.allowed_transitions.join(", ")}</div>
      </Card>
      <Card title="Change">
        <dl className="kv">
          <dt>Statement</dt><dd>{d.change.description}</dd>
          <dt>Baseline</dt><dd><code>{d.change.baseline_model_id}</code></dd>
          <dt>Candidate</dt><dd><code>{d.change.candidate_model_id ?? "—"}</code></dd>
          <dt>Code revision</dt><dd><code>{d.change.code_revision_id ?? "—"}</code></dd>
          <dt>Dataset snapshot</dt><dd><code>{d.change.dataset_snapshot_id ?? "—"}</code> (synthetic)</dd>
          <dt>Evaluation config</dt><dd><code>{d.change.evaluation_config_id ?? "—"}</code></dd>
          <dt>Deployment target</dt><dd><code>{d.change.deployment_target}</code> (simulated)</dd>
        </dl>
      </Card>
      {chain.gates.length > 0 && (
        <Card title="Release readiness (computed)" right={<Badge s={chain.overall} />}>
          <GateTable gates={chain.gates} />
          {chain.recommendation && <p className="small">Release agent: {chain.recommendation.summary} <em>Recommendation is not authorization.</em></p>}
        </Card>
      )}
    </div>
  );
}

export function GateTable({ gates }: { gates: any[] }) {
  return (
    <div className="table-wrap">
      <table data-testid="gate-table">
        <thead><tr><th>Gate</th><th>Rule</th><th>Observed</th><th>Status</th><th>Owner</th><th>Evidence</th></tr></thead>
        <tbody>{gates.map((g) => (
          <tr key={g.gate_id} data-gate={g.gate_id} data-status={g.status}>
            <td><code>{g.gate_id}</code></td><td className="small">{g.rule}</td><td className="small">{g.observed}</td>
            <td><Badge s={g.status} /></td><td className="small">{g.owner_role}</td>
            <td className="small">{(g.evidence ?? []).slice(0, 2).map((r: any, i: number) => <div key={i}><SourceLink r={r} /></div>)}</td>
          </tr>
        ))}</tbody>
      </table>
    </div>
  );
}

// -------------------------------------------------------------- Requirements

function Clarification({ c, d, reload }: { c: any; d: any; reload: () => void }) {
  const { me } = useApp();
  const [ans, setAns] = useState("");
  const open = !c.answer;
  const editable = ["NEEDS_CLARIFICATION", "DRAFT"].includes(d.change.status) && can(me, "clarification.answer");
  return (
    <div className="card" data-testid={`clar-${c.key}`}>
      <div className="spread"><strong>{c.question}</strong><Badge s={open ? "PENDING" : "PASS"} label={open ? "open" : `answered (cycle ${c.cycle})`} /></div>
      <div className="small muted">key <code>{c.key}</code> · owner {c.owner_role} · {c.required ? "required" : "optional"}</div>
      {c.related_guidance?.length > 0 && <div className="small">Related guidance: {c.related_guidance.map((r: any, i: number) => <SourceLink key={i} r={r} />)}</div>}
      {c.answer && <blockquote>{c.answer}<div className="small muted">by {c.answered_by} · {when(c.answered_at)}</div></blockquote>}
      {editable && (
        <div>
          {c.suggested_answer && open && <div className="note small">Configured synthetic demo clarification: {c.suggested_answer}</div>}
          <div className="row">
            {c.suggested_answer && <Action label="Use demo clarification" run={() => api(`/api/changes/${d.change.id}/clarifications`, { method: "POST", body: { key: c.key, use_suggested: true } })} onDone={reload} testId={`use-demo-${c.key}`} />}
            <input aria-label={`Answer ${c.key}`} value={ans} onChange={(e) => setAns(e.target.value)} placeholder="Or write an answer…" style={{ flex: 1, minWidth: 180 }} />
            <Action label="Save answer" disabled={!ans.trim()} run={() => api(`/api/changes/${d.change.id}/clarifications`, { method: "POST", body: { key: c.key, answer: ans } })} onDone={() => { setAns(""); reload(); }} />
          </div>
        </div>
      )}
    </div>
  );
}

export function RequirementsTab({ d, reload }: TabProps) {
  const { me } = useApp();
  const open = d.clarifications.filter((c: any) => c.required && !c.answer).length;
  const latest = d.requirement_versions[d.requirement_versions.length - 1];
  const useAll = async () => {
    for (const c of d.clarifications.filter((x: any) => !x.answer && x.suggested_answer)) {
      await api(`/api/changes/${d.change.id}/clarifications`, { method: "POST", body: { key: c.key, use_suggested: true } });
    }
  };
  return (
    <div>
      <Card title="Requirement versions">
        {d.requirement_versions.map((rv: any) => (
          <div key={rv.id} style={{ marginBottom: 10 }}>
            <div className="row"><strong>v{rv.version}</strong><Badge s={rv.status === "APPROVED" ? "APPROVED" : rv.status === "DRAFT" ? "PENDING" : "neutral"} label={rv.status} />
              {rv.approved_by && <span className="small muted">approved by {rv.approved_by} {when(rv.approved_at)}</span>}</div>
            <div className="small">{rv.statement}</div>
            {rv.acceptance_criteria.length > 0 && (
              <table style={{ marginTop: 6 }}><thead><tr><th>Code</th><th>Acceptance criterion</th><th>Gate</th></tr></thead>
                <tbody>{rv.acceptance_criteria.map((a: any) => <tr key={a.code}><td><code>{a.code}</code></td><td>{a.text}</td><td><code>{a.gate_id ?? "report only"}</code></td></tr>)}</tbody></table>
            )}
          </div>
        ))}
        <div className="warnbox small">Thresholds are configurable demo rules, not L’Oréal standards or scientifically established thresholds. The policy engine applies the stricter of policy and acceptance criteria.</div>
        <div className="row">
          {open > 0 && can(me, "clarification.answer") && d.change.status === "NEEDS_CLARIFICATION" && <Action label={`Use all ${open} demo clarifications`} run={useAll} onDone={reload} testId="use-all-demo" />}
          {can(me, "requirements.approve") && latest?.status === "DRAFT" && (
            <Action primary label={`Approve requirement v${latest.version}`} disabled={open > 0}
              run={() => api(`/api/changes/${d.change.id}/requirements/approve`, { method: "POST" })} onDone={reload} testId="approve-requirements" />
          )}
        </div>
      </Card>
      <h2>Ambiguities flagged by the requirements agent ({open} open)</h2>
      {d.clarifications.map((c: any) => <Clarification key={c.id} c={c} d={d} reload={reload} />)}
    </div>
  );
}

// ------------------------------------------------------------------ Evidence

export function EvidenceTab({ d, reload }: TabProps) {
  const { me } = useApp();
  const a = d.evidence_analysis;
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<any[] | null>(null);
  const [err, setErr] = useState<unknown>(null);
  return (
    <div>
      <Card title="Evidence bundle" right={can(me, "investigate.run") && ["REQUIREMENTS_APPROVED", "IMPACT_REVIEW"].includes(d.change.status) &&
        <Action primary label={d.evidence.length ? "Re-run evidence and impact" : "Run evidence and impact agents"} testId="investigate"
          run={() => api(`/api/changes/${d.change.id}/investigate`, { method: "POST" })} onDone={reload} />}>
        {d.evidence.length === 0 && <p className="muted">No evidence yet. Approve the requirement, then run the investigation.</p>}
        {d.evidence.length > 0 && (
          <div className="table-wrap"><table>
            <thead><tr><th>Purpose</th><th>Source (opens exact excerpt)</th><th>Status</th><th>Flags</th><th>Retrieved</th></tr></thead>
            <tbody>{d.evidence.map((e: any) => (
              <tr key={e.id}><td className="small">{e.purpose}</td><td><SourceLink r={e} /></td><td><Badge s={e.validation_status} /></td>
                <td className="small">{e.flags.join("; ")}</td><td className="small">{when(e.retrieved_at)}</td></tr>
            ))}</tbody>
          </table></div>
        )}
      </Card>
      {a && (
        <>
          {a.injection_flags.length > 0 && <Card title="Instruction-like text ignored">
            {a.injection_flags.map((f: any, i: number) => <div key={i} className="warnbox"><code>{f.source_id} {f.section}</code>: {f.action}. Patterns: {f.patterns.join(", ")}</div>)}
          </Card>}
          {a.conflicts.length > 0 && <Card title="Outdated or conflicting versions">
            {a.conflicts.map((c: any, i: number) => (
              <div key={i} className="small" style={{ marginBottom: 8 }}><strong>{c.doc_id} {c.section}</strong>: v{c.outdated_version} (superseded) says “{c.outdated_text}” — current v{c.current_version} says “{c.current_text}”</div>
            ))}
          </Card>}
          <Card title="Claims without approved support (marked unknown)">
            <ul>{a.unsupported_claims.map((u: any) => <li key={u.claim}><Badge s="INCONCLUSIVE" label="UNKNOWN" /> {u.claim}</li>)}</ul>
          </Card>
        </>
      )}
      <Card title="Search approved knowledge (authorization-filtered, lexical)">
        <form className="row" onSubmit={async (e) => { e.preventDefault(); setErr(null); try { setHits((await api(`/api/knowledge/search?q=${encodeURIComponent(q)}`)).results); } catch (x) { setErr(x); } }}>
          <input aria-label="Search knowledge" value={q} onChange={(e) => setQ(e.target.value)} placeholder="e.g. abstention denominator" style={{ flex: 1 }} />
          <button type="submit">Search</button>
        </form>
        <ErrorBox error={err} />
        {hits && <ul>{hits.map((h, i) => <li key={i}><SourceLink r={h} /> — <span className="small">{h.excerpt.slice(0, 160)}…</span></li>)}{hits.length === 0 && <li className="muted">No approved source found — unknown.</li>}</ul>}
      </Card>
    </div>
  );
}

// -------------------------------------------------------------------- Impact

export function ImpactTab({ d, reload }: TabProps) {
  const { me } = useApp();
  const ia = d.impact;
  if (!ia) return <Card title="Impact assessment"><p className="muted">Run the evidence and impact agents from the Evidence tab.</p></Card>;
  const c = ia.content;
  return (
    <div>
      <Card title="Impact assessment" right={ia.accepted_by ? <Badge s="APPROVED" label={`accepted by ${ia.accepted_by}`} /> :
        (can(me, "impact.accept") && d.change.status === "IMPACT_REVIEW" && <Action primary label="Accept impact assessment" testId="accept-impact"
          run={() => api(`/api/changes/${d.change.id}/impact/accept`, { method: "POST" })} onDone={reload} />)}>
        <h3>Risks</h3>
        <ul>{c.risks.map((r: any, i: number) => <li key={i}><Badge s={r.severity === "high" ? "FAIL" : "INCONCLUSIVE"} label={r.severity} /> {r.risk} <SourceLink r={r.ref} /></li>)}</ul>
        <h3>Affected components</h3>
        <table><thead><tr><th>Component</th><th>Kind</th><th>Owner</th><th>Matched terms</th></tr></thead>
          <tbody>{c.components.map((x: any) => <tr key={x.id}><td>{x.name}</td><td>{x.kind}</td><td>{x.owner_role}</td><td className="small">{x.matched_terms.join(", ")}</td></tr>)}</tbody></table>
        <h3>Tests</h3>
        <ul>{c.tests.map((t: any) => <li key={t.id}><code>{t.id}</code> {t.name} — {t.owner_role}</li>)}</ul>
        <div className="small muted">Owners: {c.owners.join(", ")}</div>
      </Card>
    </div>
  );
}

// --------------------------------------------------------------- Development

export function DevelopmentTab({ d, reload }: TabProps) {
  const { me } = useApp();
  const cands = d.models.filter((m: any) => m.role !== "baseline");
  const rev = d.revisions.find((r: any) => r.id === d.change.code_revision_id);
  const dev = d.development;
  const canReg = can(me, "candidate.register") && ["DEVELOPMENT", "EVALUATION_FAILED", "EVALUATION_INCONCLUSIVE", "REVIEW_REQUIRED"].includes(d.change.status);
  const canEval = can(me, "evaluation.run") && d.change.candidate_model_id && ["DEVELOPMENT", "EVALUATION_FAILED", "EVALUATION_INCONCLUSIVE", "REVIEW_REQUIRED"].includes(d.change.status);
  const code = d.review_status?.status?.code;
  return (
    <div>
      <Card title="Model versions (fixture registry)">
        <div className="table-wrap"><table>
          <thead><tr><th>Model</th><th>Role</th><th>Artifact digest</th><th>Preprocessing</th><th>Lighting map</th><th>Provenance</th><th></th></tr></thead>
          <tbody>{d.models.map((m: any) => (
            <tr key={m.id}><td><code>{m.id}</code>{m.id === d.change.candidate_model_id && <> <Badge s="info" label="current candidate" /></>}</td><td>{m.role}</td>
              <td className="mono" title={m.artifact_digest}>{shortDigest(m.artifact_digest)}</td>
              <td className="small">{Object.entries(m.preprocessing).map(([k, v]) => `${k}=${v}`).join(", ")}</td><td><code>{m.lighting_profile_map_id}</code></td>
              <td className="small">{m.provenance}</td>
              <td>{canReg && cands.some((c: any) => c.id === m.id) && m.id !== d.change.candidate_model_id &&
                <Action label="Register as candidate" testId={`register-${m.id}`} run={() => api(`/api/changes/${d.change.id}/candidates`, { method: "POST", body: { model_id: m.id } })} onDone={reload} />}</td></tr>
          ))}</tbody>
        </table></div>
        <div className="small muted">Fixture adapters: no training occurred; predictions are fixed-seed fixtures.</div>
      </Card>
      {rev && (
        <Card title={<>Implementation diff <code>{rev.id}</code></>} right={<Badge s={code ?? "PENDING"} label={`code review: ${code ?? "PENDING"}`} />}>
          <p>{rev.summary} <span className="small muted">author {rev.author} · digest {shortDigest(rev.diff_digest)}</span></p>
          <DiffView diff={rev.diff} />
          <div className="row">
            {can(me, "review.code") && <Action label="Approve code review" testId="approve-code" run={() => api(`/api/changes/${d.change.id}/reviews`, { method: "POST", body: { kind: "code", decision: "APPROVE", comment: "Diff reviewed against BR-101 criteria" } })} onDone={reload} />}
            {can(me, "review.code") && <Action label="Request changes" run={() => api(`/api/changes/${d.change.id}/reviews`, { method: "POST", body: { kind: "code", decision: "REJECT" } })} onDone={reload} />}
          </div>
        </Card>
      )}
      {dev && (
        <Card title="Development agent: plan and traceability">
          <ol>{dev.plan.map((p: string) => <li key={p}>{p}</li>)}</ol>
          <table><thead><tr><th>File</th><th>Requirements</th><th>Tests</th></tr></thead>
            <tbody>{dev.traceability.map((t: any) => <tr key={t.file}><td><code>{t.file}</code></td><td>{t.requirement_refs.join(", ")}</td><td>{t.test_refs.join(", ")}</td></tr>)}</tbody></table>
          {dev.risks.map((r: any, i: number) => <div key={i} className="warnbox">⚠ {r.risk}</div>)}
          <div className="small muted">Diff analysed as text only; nothing was executed in the application runtime.</div>
        </Card>
      )}
      <Card title="Evaluation">
        {canEval ? <Action primary label="Run evaluation (background job)" testId="run-evaluation" run={() => api(`/api/changes/${d.change.id}/evaluations`, { method: "POST" })} onDone={reload} />
          : <span className="muted small">Evaluation available to ML/QA/CV engineers once a candidate is registered.</span>}
        <span style={{ marginLeft: 8 }}><Link to={`/changes/${d.change.id}/evaluation`}>View results →</Link></span>
      </Card>
    </div>
  );
}

// ----------------------------------------------------------------- Approvals

export function ApprovalsTab({ d, reload }: TabProps) {
  const { me } = useApp();
  const [comment, setComment] = useState("");
  const rs = d.review_status?.status ?? {};
  const inReview = d.change.status === "REVIEW_REQUIRED";
  const review = (kind: string, decision: string) => api(`/api/changes/${d.change.id}/reviews`, { method: "POST", body: { kind, decision, comment } });
  return (
    <div>
      <Card title="Required reviews">
        <table><thead><tr><th>Review</th><th>Status (bound to current artifacts)</th><th></th></tr></thead>
          <tbody>{Object.entries(rs).map(([k, v]: any) => (
            <tr key={k}><td>{k}</td><td><Badge s={v} /></td>
              <td>{can(me, `review.${k}`) && (k === "code" || inReview) && <span className="row">
                <Action label="Approve" testId={`review-${k}`} run={() => review(k, "APPROVE")} onDone={reload} />
                <Action label="Reject" run={() => review(k, "REJECT")} onDone={reload} /></span>}</td></tr>
          ))}</tbody></table>
        <textarea aria-label="Review comment" placeholder="Comment (optional)" value={comment} onChange={(e) => setComment(e.target.value)} />
      </Card>
      {d.governance && <Card title="Governance packet (governance agent)">
        <p>{d.governance.summary}</p>
        <table><thead><tr><th>Control test</th><th>Kind</th><th>Status</th><th>Observed</th></tr></thead>
          <tbody>{d.governance.data.packet.controls.map((c: any) => <tr key={c.test_id}><td><code>{c.test_id}</code></td><td>{c.kind}</td><td><Badge s={c.status} /></td><td className="small">{c.observed}</td></tr>)}</tbody></table>
        <div className="small">Eligibility exclusions: {JSON.stringify(d.governance.data.packet.eligibility_exclusions)}</div>
        <ul>{d.governance.data.packet.model_risk.map((m: string) => <li key={m} className="small">{m}</li>)}</ul>
      </Card>}
      <Card title="Release approval" right={can(me, "release.approve") && inReview && <span className="row">
        <Action primary label="Approve release" testId="approve-release" run={() => api(`/api/changes/${d.change.id}/release-approvals`, { method: "POST", body: { decision: "APPROVED", comment } })} onDone={reload} />
        <Action label="Reject release" run={() => api(`/api/changes/${d.change.id}/release-approvals`, { method: "POST", body: { decision: "REJECTED", comment } })} onDone={reload} /></span>}>
        <p className="small">Demo policy: approver must differ from the revision author; approval is single-use, expires, and binds to the artifacts below. Any change invalidates it.</p>
        {d.current_binding && <dl className="kv">{Object.entries(d.current_binding).map(([k, v]: any) => <Fragment key={k}><dt>{k}</dt><dd className="mono">{String(v)}</dd></Fragment>)}</dl>}
      </Card>
      <Card title="Approval and review history">
        <table><thead><tr><th>Record</th><th>Decision</th><th>By</th><th>When</th><th>State</th></tr></thead>
          <tbody>
            {d.approvals.map((a: any) => <tr key={a.id}><td>{a.kind} approval <code>{a.id}</code></td><td><Badge s={a.decision} /></td><td>{a.approver_id}</td><td className="small">{when(a.created_at)}</td>
              <td className="small">{a.invalidated_at ? `invalidated: ${a.invalidated_reason}` : a.consumed_at ? `used by ${a.consumed_by}` : a.kind === "release" ? `expires ${when(a.expires_at)}` : ""}</td></tr>)}
            {d.reviews.map((r: any) => <tr key={r.id}><td>{r.kind} review <code>{r.id}</code></td><td><Badge s={r.decision} /></td><td>{r.reviewer_id}</td><td className="small">{when(r.created_at)}</td>
              <td className="small">{r.invalidated_at ? `invalidated: ${r.invalidated_reason}` : r.comment}</td></tr>)}
          </tbody></table>
      </Card>
    </div>
  );
}

// ------------------------------------------------------------------- Release

export function ReleaseTab({ d, reload }: TabProps) {
  const { me } = useApp();
  const rel = d.releases[d.releases.length - 1];
  return (
    <div>
      <Card title="Release readiness (revalidated at deploy time)">
        {d.release_readiness.gates.length > 0 ? <GateTable gates={d.release_readiness.gates} /> : <p className="muted">No candidate yet.</p>}
        {d.release_readiness.recommendation && <p className="small">Release agent recommendation: <Badge s={d.release_readiness.recommendation.data.recommendation} /> — not authorization.</p>}
        {can(me, "release.execute") && d.change.status === "RELEASE_APPROVED" &&
          <Action primary label="Start simulated canary" testId="start-canary" run={() => api(`/api/changes/${d.change.id}/releases`, { method: "POST", body: {}, headers: { "Idempotency-Key": idempotencyKey() } })} onDone={reload} />}
      </Card>
      {rel && <Card title={<>Simulated release <code>{rel.id}</code></>} right={<Badge s={rel.status} />}>
        <p>Model <code>{rel.model_id}</code> at <strong>{rel.allocation_pct}%</strong> of simulated sessions. Stages {rel.stages.join("% → ")}% (prototype settings). Last approved version preserved: <code>{rel.previous_model_id}</code>.</p>
        <div className="row">
          {can(me, "release.execute") && ["CANARY", "MONITORING"].includes(rel.status) && <Action label="Promote to next stage" testId="promote" run={() => api(`/api/releases/${rel.id}/promote`, { method: "POST" })} onDone={reload} />}
          <Link to={`/changes/${d.change.id}/monitoring`}>Monitoring →</Link>
        </div>
        <h3>History</h3>
        <ul>{rel.history.map((h: any, i: number) => <li key={i} className="small">{when(h.at)} — {h.event} {h.stage_pct}% by {h.by} {h.note ? `(${h.note})` : ""}</li>)}</ul>
        <div className="small muted">Deployment events are simulated and are not customer traffic.</div>
      </Card>}
    </div>
  );
}

// ---------------------------------------------------------------- Monitoring

export function MonitoringTab({ d, reload }: TabProps) {
  const { me } = useApp();
  const rel = d.releases[d.releases.length - 1];
  const [m, setM] = useState<any>(null);
  const [err, setErr] = useState<unknown>(null);
  const [reason, setReason] = useState("Outcome regression for DEV-T3 under warm indoor lighting");
  const load = () => rel && api(`/api/releases/${rel.id}/monitoring`).then(setM).catch(setErr);
  useEffect(() => { load(); }, [rel?.id, d]); // eslint-disable-line
  if (!rel) return <Card title="Monitoring"><p className="muted">No release yet.</p></Card>;
  const after = () => { reload(); load(); };
  const pending = m?.rollbacks?.find((r: any) => r.status === "REQUESTED");
  return (
    <div>
      <ErrorBox error={err} />
      <Card title="Simulated monitoring" right={can(me, "monitoring.advance") && ["CANARY", "MONITORING", "RELEASED"].includes(rel.status) &&
        <Action primary label="Advance simulated window" testId="advance-window" run={() => api(`/api/releases/${rel.id}/monitoring/advance`, { method: "POST" })} onDone={after} />}>
        {m && <>
          <div className="note small">{m.simulator.note} {m.simulator.sessions_per_window_at_100pct} sessions/window at 100%, reference labels for {m.simulator.label_rate * 100}% of sessions. Alert rule: labelled ≥ {m.rule.min_labels_per_cohort_cell}, accuracy &lt; reference − {m.rule.alert_drop_pp} pp, and Wilson 95% upper bound below reference.</div>
          <h3>Cumulative outcomes by device cohort × lighting</h3>
          <div className="table-wrap"><table data-testid="cohort-table">
            <thead><tr><th>Cohort cell</th><th className="num">Simulated sessions</th><th className="num">Labelled</th><th className="num">Correct</th><th className="num">Top-1</th><th>Wilson 95%</th><th className="num">Reference</th></tr></thead>
            <tbody>{Object.entries(m.cumulative).map(([k, v]: any) => {
              const ref = m.reference_by_lighting[k.split("|")[1]];
              const alert = m.alerts.find((a: any) => a.scope === k);
              return <tr key={k}><td><code>{k}</code> {alert && <Badge s="FAIL" label="alert" />}</td><td className="num">{v.sessions}</td><td className="num">{v.labelled}</td><td className="num">{v.correct}</td>
                <td className="num">{pct(v.accuracy_pct)}</td><td className="small">{v.wilson95?.[0] ?? "—"}–{v.wilson95?.[1] ?? "—"}%</td><td className="num">{pct(ref)}</td></tr>;
            })}</tbody>
          </table></div>
          <h3>Windows</h3>
          <ul>{m.windows.map((w: any) => <li key={w.id} className="small">window {w.index} at {w.allocation_pct}%: {w.simulated_sessions} simulated sessions, {w.labelled} labelled</li>)}</ul>
        </>}
      </Card>
      {m?.alerts.map((a: any) => (
        <Card key={a.id} title={<>Alert <code>{a.id}</code> — {a.scope}</>} right={<Badge s={a.status} />}>
          <p>Observed {a.observed.accuracy_pct}% on {a.observed.labelled} labelled simulated sessions vs reference {a.observed.reference_pct}% (Wilson 95% upper {a.observed.wilson95[1]}%).</p>
          <p className="small muted">Rule: {a.rule}. A statistical alert alone does not prove root cause.</p>
          {!a.investigation && can(me, "alert.investigate") && <Action primary label="Investigate (monitoring agent)" testId="investigate-alert" run={() => api(`/api/alerts/${a.id}/investigate`, { method: "POST" })} onDone={after} />}
          {a.investigation && <>
            <ul>{a.investigation.findings.map((f: string) => <li key={f}>{f}</li>)}</ul>
            {a.investigation.suspected_cause && <div className="warnbox"><strong>Suspected cause:</strong> {a.investigation.suspected_cause.hypothesis}<div className="small">Evidence: {a.investigation.suspected_cause.evidence.join(", ")} · {a.investigation.suspected_cause.confidence}</div></div>}
            <ul className="small">{a.investigation.caveats.map((c: string) => <li key={c}>{c}</li>)}</ul>
            <p>Proposed response: <strong>{a.investigation.proposed_response.action}</strong> → <code>{a.investigation.proposed_response.target_model_id}</code> ({a.investigation.proposed_response.requires})</p>
          </>}
        </Card>
      ))}
      <Card title="Rollback">
        {can(me, "rollback.request") && ["CANARY", "MONITORING", "RELEASED"].includes(rel.status) && !pending && <div>
          <input aria-label="Rollback reason" value={reason} onChange={(e) => setReason(e.target.value)} style={{ width: "100%" }} />
          <Action label="Request rollback" testId="request-rollback" run={() => api(`/api/releases/${rel.id}/rollback-requests`, { method: "POST", headers: { "Idempotency-Key": idempotencyKey() }, body: { reason, alert_id: m?.alerts?.[0]?.id ?? null } })} onDone={after} />
        </div>}
        {pending && can(me, "rollback.approve") && <div className="row">
          <span>Pending rollback <code>{pending.id}</code> requested by {pending.requested_by}</span>
          <Action primary label="Approve rollback" testId="approve-rollback" run={() => api(`/api/rollbacks/${pending.id}/decision`, { method: "POST", body: { decision: "APPROVE" } })} onDone={after} />
          <Action label="Reject rollback" run={() => api(`/api/rollbacks/${pending.id}/decision`, { method: "POST", body: { decision: "REJECT" } })} onDone={after} />
        </div>}
        {pending && !can(me, "rollback.approve") && <p className="small">Rollback <code>{pending.id}</code> awaits a release manager (prototype policy: authorized review required).</p>}
        <ul>{m?.rollbacks.map((r: any) => <li key={r.id}><Badge s={r.status} /> <code>{r.id}</code> → <code>{r.target_model_id}</code> {r.error && <span className="small">{r.error}</span>}
          {r.compatibility && <span className="small"> checks: {Object.entries(r.compatibility.checks).map(([k, v]) => `${k}=${v}`).join(", ")}</span>}</li>)}</ul>
      </Card>
    </div>
  );
}

// --------------------------------------------------------------------- Audit

export function AuditTab({ d }: TabProps) {
  const [a, setA] = useState<any>(null);
  const [t, setT] = useState<any>(null);
  const [tel, setTel] = useState<any>(null);
  useEffect(() => {
    api(`/api/changes/${d.change.id}/audit`).then(setA);
    api(`/api/changes/${d.change.id}/traceability`).then(setT);
    api(`/api/changes/${d.change.id}/telemetry`).then(setTel);
  }, [d]);
  const download = async (fmt: "md" | "json") => {
    const res = await fetch(`/api/changes/${d.change.id}/report?format=${fmt}`, { headers: { "X-Demo-User": localStorage.getItem("persona") ?? "u-po" } });
    const blob = new Blob([await res.text()], { type: fmt === "md" ? "text/markdown" : "application/json" });
    const url = URL.createObjectURL(blob);
    const el = document.createElement("a"); el.href = url; el.download = `${d.change.id}-report.${fmt}`; el.click(); URL.revokeObjectURL(url);
  };
  return (
    <div>
      <Card title="Traceability" right={<span className="row"><button onClick={() => download("md")}>Export report (.md)</button><button onClick={() => download("json")}>Export (.json)</button></span>}>
        {t && <ol data-testid="trace-chain">{t.chain.map((x: any) => <li key={x.type + x.id}><Badge s="info" label={x.type} /> {x.label} <code className="small">{x.id}</code></li>)}</ol>}
      </Card>
      {tel && <Card title="Agent telemetry (measured)">
        <p className="small muted">{tel.note}</p>
        <table><thead><tr><th>Agent</th><th className="num">Invocations</th><th className="num">Errors</th><th className="num">p50 ms</th><th className="num">Tool calls</th><th className="num">Tokens in/out</th><th className="num">Cost USD</th></tr></thead>
          <tbody>{Object.entries(tel.by_agent).map(([k, v]: any) => <tr key={k}><td>{k}</td><td className="num">{v.invocations}</td><td className="num">{v.errors}</td><td className="num">{v.latency_ms_p50}</td><td className="num">{v.tool_calls}</td><td className="num">{v.input_tokens}/{v.output_tokens}</td><td className="num">{v.cost_usd}</td></tr>)}</tbody></table>
      </Card>}
      {a && <Card title="Audit events (append-only, hash-chained)" right={<Badge s={a.chain.valid ? "PASS" : "FAIL"} label={a.chain.valid ? `chain valid (${a.chain.events} tenant events)` : "chain broken"} />}>
        <div className="table-wrap"><table>
          <thead><tr><th>#</th><th>When</th><th>Who</th><th>What</th><th>Status</th><th>Reason</th></tr></thead>
          <tbody>{a.events.map((e: any) => <tr key={e.id}><td>{e.id}</td><td className="small">{when(e.at)}</td><td className="small">{e.actor}</td><td><code>{e.action}</code></td><td><Badge s={e.status} /></td><td className="small">{e.reason}</td></tr>)}</tbody>
        </table></div>
        <p className="small muted">Application-level append-only with hash chain. Stronger tamper resistance requires infrastructure controls (WORM storage, restricted DB roles).</p>
      </Card>}
    </div>
  );
}
