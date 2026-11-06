import { ACTION_LABEL } from "../format";
import { Approval, Recommendation } from "../types";
import { RefLink } from "./CitationViewer";
import { Card, Chip } from "./ui";

export function RecommendationCard({ rec, approval, onOpenRef, onChooseAlternative }: {
  rec: Recommendation; approval: Approval | null; onOpenRef: (r: string) => void;
  onChooseAlternative?: (action: string) => void;
}) {
  const req = rec.approval_requirement;
  return (
    <Card title="Recommendation" className="rec-card"
          actions={<Chip tone="info">Generation: {rec.generation_mode}</Chip>}>
      <div className="stack">
        <div>
          <h3 className="rec-action">{ACTION_LABEL[rec.action_type] ?? rec.action_type}</h3>
          <p className="muted">Suspected cause — proposed next step. Policy {rec.policy_version}.</p>
        </div>
        <section aria-label="Purpose"><h4>Expected purpose</h4><p>{rec.purpose}</p></section>
        <section aria-label="Evidence">
          <h4>Evidence</h4>
          <p className="refs">{rec.evidence_refs.map((r) => <RefLink key={r} refId={r} onOpen={onOpenRef} />)}</p>
        </section>
        <section aria-label="Prerequisites">
          <h4>Prerequisites</h4>
          <ul>{rec.prerequisites.map((p) => <li key={p}>{p}</li>)}</ul>
        </section>
        <section aria-label="Uncertainty"><h4>Uncertainty</h4><p>{rec.uncertainty}</p></section>
        <section aria-label="Risk and approval">
          <h4>Risk and approval requirement</h4>
          <p>
            <Chip tone={rec.risk === "high" ? "bad" : rec.risk === "medium" ? "warn" : "ok"}>Risk: {rec.risk}</Chip>{" "}
            Approver role(s): <strong>{req.approver_roles.join(", ") || "none"}</strong>
            {req.separation_of_duties && <> · proposer cannot approve</>} · executor role(s): {req.executor_roles.join(", ")}
          </p>
          {approval && (
            <p>
              <Chip tone={approval.status === "pending" ? "warn" : approval.status === "rejected" ? "bad" : "ok"}>
                {approval.status === "pending" ? "Pending approval" : `Approval ${approval.status}`}
              </Chip>{" "}
              <span className="muted">bound to payload {rec.payload_hash.slice(0, 12)}…, expires {approval.expires_at ? new Date(approval.expires_at).toLocaleTimeString() : "—"}</span>
            </p>
          )}
        </section>
        {rec.prior_interventions.length > 0 && (
          <section aria-label="Earlier interventions">
            <h4>Earlier interventions</h4>
            <ul>
              {rec.prior_interventions.map((p) => (
                <li key={p.action + p.source_ref}>
                  <strong>{p.action.replace(/_/g, " ")}</strong> ({p.outcome.replace(/_/g, " ")}) — {p.justification}{" "}
                  <RefLink refId={p.source_ref} onOpen={onOpenRef} />
                </li>
              ))}
            </ul>
          </section>
        )}
        {rec.refused_requests.length > 0 && (
          <section aria-label="Requests not fulfilled">
            <h4>Requests the copilot will not fulfil</h4>
            <ul>
              {rec.refused_requests.map((r) => (
                <li key={r.request}><strong>{r.request}:</strong> {r.reason}{" "}
                  {r.citations.map((c) => <RefLink key={c} refId={c} onOpen={onOpenRef} />)}</li>
              ))}
            </ul>
          </section>
        )}
        <details>
          <summary>Payload and alternatives</summary>
          <pre className="record">{JSON.stringify(rec.payload, null, 2)}</pre>
          <ul className="alts">
            {rec.alternatives.map((a) => (
              <li key={a.action_type}>
                <Chip tone={a.allowed ? (a.executable ? "ok" : "warn") : "bad"}>
                  {a.allowed ? (a.executable ? "Permitted" : "Proposal only") : "Not permitted"}
                </Chip>{" "}
                {ACTION_LABEL[a.action_type] ?? a.action_type} — <span className="muted">{a.reasons.join(" ")}</span>
                {onChooseAlternative && a.allowed && a.executable && (
                  <button className="btn btn-small" onClick={() => onChooseAlternative(a.action_type)}>Propose instead</button>
                )}
              </li>
            ))}
          </ul>
        </details>
      </div>
    </Card>
  );
}
