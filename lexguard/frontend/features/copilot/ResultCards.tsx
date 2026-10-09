"use client";

import { Badge, Bar, StatusPill, Tip } from "@/components/ui";
import { humanize, pct, statusTone } from "@/lib/format";
import type { Action, Card, CopilotResponse, TraceStep } from "@/types/api";

export type ActionHandler = (a: Action) => void;
export type FindingSelect = (findingId: string) => void;

const TRACE_ICON: Record<TraceStep["status"], string> = { ok: "✓", warn: "⚠", blocked: "✕", error: "✕", pending: "○", skipped: "–" };

export function AgentTrace({ steps, defaultOpen = false }: { steps: TraceStep[]; defaultOpen?: boolean }) {
  const warn = steps.filter((s) => s.status === "warn").length;
  const blocked = steps.filter((s) => s.status === "blocked" || s.status === "error").length;
  return (
    <details className="trace" open={defaultOpen}>
      <summary>
        <span>How LexGuard analyzed this</span>
        <span className="row small muted">{steps.length} steps{warn > 0 && <Badge tone="warn">{warn} warnings</Badge>}
          {blocked > 0 && <Badge tone="bad">{blocked} blocked</Badge>}</span>
      </summary>
      <ol>
        {steps.map((s) => (
          <li key={s.step}>
            <span className={`icon ${s.status}`} aria-label={s.status}>{TRACE_ICON[s.status]}</span>
            <span><span className="strong">{s.label}</span>{s.detail && <div className="tiny muted">{s.detail}</div>}</span>
            <span className="tiny muted" title={`Agent: ${s.agent}`}>{humanize(s.agent)}</span>
          </li>
        ))}
      </ol>
    </details>
  );
}

const STATUS_COPY: Record<string, { title: string; tone: string }> = {
  ACCESS_DENIED: { title: "Access denied — no documents were retrieved", tone: "bad" },
  BLOCKED: { title: "Blocked by deterministic policy", tone: "bad" },
  HUMAN_DECISION_REQUIRED: { title: "Lawyer decision required — AI will not make this judgment", tone: "warn" },
  REVIEW_REQUIRED: { title: "Lawyer review required before use", tone: "warn" },
  NEEDS_INPUT: { title: "More information needed", tone: "warn" },
  HALTED: { title: "Workflow halted by a safety limit", tone: "bad" },
  ERROR: { title: "Workflow error", tone: "bad" },
  COMPLETED: { title: "Completed", tone: "good" },
};

export function StatusBanner({ status }: { status: string }) {
  const c = STATUS_COPY[status] ?? STATUS_COPY.COMPLETED;
  if (status === "COMPLETED") return null;
  return (
    <div className={`status-banner tone-${c.tone}`} role={c.tone === "bad" ? "alert" : "status"}>
      <strong>{c.title}</strong>
    </div>
  );
}

function Metrics({ card }: { card: Card }) {
  if (!card.metrics.length) return null;
  return (
    <div className="metric-row">
      {card.metrics.map((m) => (
        <div className="metric" key={m.label} title={m.hint ?? undefined}>
          <div className={`v ${m.tone ?? ""} ${typeof m.value === "string" && m.value.length > 9 ? "v-text" : ""}`}>{m.value ?? "-"}</div>
          <div className="l">{m.label}{m.hint && <> <Tip text={m.hint} /></>}</div>
        </div>
      ))}
    </div>
  );
}

function Actions({ actions, onAction }: { actions: Action[]; onAction: ActionHandler }) {
  if (!actions.length) return null;
  return <div className="row" style={{ marginTop: 8 }}>{actions.map((a) =>
    <button key={a.id} className={`btn btn-sm ${a.id === "approve" || a.id === "send-review" ? "btn-primary" : ""}`} onClick={() => onAction(a)}>{a.label}</button>)}</div>;
}

function CardBody({ card, onAction, onFinding }: { card: Card; onAction: ActionHandler; onFinding: FindingSelect }) {
  switch (card.type) {
    case "PLAYBOOK_DEVIATION":
      return (
        <div className="list">
          {card.items.map((d: any) => (
            <div key={d.finding_id} className={`list-item ${d.doc_id ? "clickable" : ""}`} role={d.doc_id ? "button" : undefined}
              tabIndex={d.doc_id ? 0 : undefined} onClick={() => d.doc_id && onFinding(d.finding_id)}
              onKeyDown={(e) => e.key === "Enter" && d.doc_id && onFinding(d.finding_id)}>
              <StatusPill status={d.result} />
              <div style={{ flex: 1 }}>
                <div className="strong small">{d.doc_title}{d.doc_id && <span className="muted mono"> · {d.doc_id}</span>}</div>
                <div className="small">{d.topic}{d.rule_id && <span className="muted"> ({d.rule_id})</span>}</div>
                <div className="tiny muted">Playbook: {d.standard_position}</div>
                {!d.doc_id && <div className="tiny" style={{ marginTop: 2 }}>“{d.clause}”</div>}
              </div>
            </div>
          ))}
        </div>
      );
    case "FINDING":
      return (
        <div className="list">
          {card.items.map((f: any) => (
            <div key={f.finding_id} className="list-item clickable" role="button" tabIndex={0} onClick={() => onFinding(f.finding_id)}
              onKeyDown={(e) => e.key === "Enter" && onFinding(f.finding_id)}>
              <Badge tone="warn">Evidence review</Badge>
              <div style={{ flex: 1 }}>
                <div className="strong small">{f.doc_title} <span className="muted mono">· {f.doc_id}</span></div>
                {f.issues.map((i: any) => <div key={i.pid} className="tiny"><StatusPill status={i.status} /> {i.reasons[0]}</div>)}
              </div>
            </div>
          ))}
        </div>
      );
    case "ASSURANCE": {
      const items = card.items as { component: string; value: number; weight: number }[];
      return (
        <div className="stack">
          <div className="grid" style={{ gridTemplateColumns: "1fr 1fr", gap: 6 }}>
            {items.map((i) => (
              <div key={i.component}>
                <div className="row tiny" style={{ justifyContent: "space-between" }}><span>{humanize(i.component)}</span><span className="mono">{pct(i.value)} · w{i.weight}</span></div>
                <Bar value={i.value} tone={i.value >= 0.95 ? "good" : i.value >= 0.8 ? "warn" : "bad"} />
              </div>
            ))}
          </div>
          <div className="notice">{card.body}</div>
        </div>
      );
    }
    case "DRAFT":
      return (
        <div className="stack">
          {card.items.map((p: any, i: number) => (
            <div key={i}>
              {p.heading && <div className="strong small">{p.heading}</div>}
              <div className="small">{p.text} {p.citations?.map((c: any) => <span key={c.doc_id + c.section_id} className="badge tone-info mono">{c.doc_id} §{c.section_id}</span>)}</div>
            </div>
          ))}
        </div>
      );
    case "CITATION_REPORT":
      return (
        <div className="table-wrap"><table className="table">
          <thead><tr><th>#</th><th>Claim</th><th>Status</th><th>Source</th></tr></thead>
          <tbody>{card.items.map((c: any) => (
            <tr key={c.pid}><td className="mono">{c.pid}</td><td>{c.claim}<div className="tiny muted">{c.reasons?.[0]}</div></td>
              <td><StatusPill status={c.status} /></td><td className="mono tiny">{c.doc_id ? `${c.doc_id} §${c.section_id}` : "—"}</td></tr>))}
          </tbody></table></div>
      );
    case "POLICY_BLOCK":
      return (
        <div className="stack">
          {card.body && <div className="small"><span className="strong">Client policy: </span>{card.body}</div>}
          {card.items.map((i: any, n: number) => (
            <div key={n} className="small">{i.rule_id && <Badge tone="bad">{i.rule_id}</Badge>} {i.text}
              {i.source && <span className="tiny muted"> — source {i.source} §{i.section}</span>}</div>
          ))}
        </div>
      );
    case "PROVIDER_MATRIX":
      return (
        <div className="table-wrap"><table className="table">
          <thead><tr><th>Provider</th><th>Type</th><th>Decision</th></tr></thead>
          <tbody>{card.items.map((p: any) => (
            <tr key={p.provider_id}><td>{p.provider}<div className="tiny muted">{p.reasons?.[0]}</div></td>
              <td>{p.external ? "External" : "Internal"}</td><td><StatusPill status={p.permitted ? p.decision : "PROHIBITED"} /></td></tr>))}
          </tbody></table></div>
      );
    case "RISK":
    case "SECURITY":
      return (
        <div className="stack">
          {card.body && <div className="small">{card.body}</div>}
          {card.items.map((f: any, i: number) => (
            <div key={i} className="small"><Badge tone="bad">{f.label ?? "UNTRUSTED INSTRUCTION"}</Badge>{" "}
              {f.doc_id && <span className="mono">{f.doc_id} </span>}{f.detail ?? f.handling}</div>
          ))}
        </div>
      );
    case "HUMAN_JUDGMENT":
    case "NEXT_ACTION":
      return (
        <div className="stack">
          {card.body && <div className="small">{card.body}</div>}
          {card.items.length > 0 && <ul className="small" style={{ margin: 0, paddingLeft: 18 }}>{card.items.map((i: any, n: number) =>
            <li key={n}>{i.text ?? JSON.stringify(i)}</li>)}</ul>}
        </div>
      );
    case "ANALYSIS": {
      const rows = card.items.slice(0, 30);
      if (!rows.length) return <div className="small muted">No items.</div>;
      const keys = Object.keys(rows[0]).filter((k) => typeof rows[0][k] !== "object" || Array.isArray(rows[0][k])).slice(0, 5);
      return (
        <div className="table-wrap"><table className="table">
          <thead><tr>{keys.map((k) => <th key={k}>{humanize(k)}</th>)}</tr></thead>
          <tbody>{rows.map((r: any, i: number) => <tr key={i}>{keys.map((k) =>
            <td key={k} className="small">{Array.isArray(r[k]) ? r[k].join(", ") : String(r[k] ?? "")}</td>)}</tr>)}</tbody>
        </table></div>
      );
    }
    default:
      return card.body ? <div className="small">{card.body}</div> : null;
  }
}

export function ResultCard({ card, onAction, onFinding }: { card: Card; onAction: ActionHandler; onFinding: FindingSelect }) {
  return (
    <section className="rcard" aria-label={card.title}>
      <div className="rcard-head">
        <div><div className="rcard-type">{humanize(card.type)}</div><h3>{card.title}</h3></div>
        {card.severity && <Badge tone={statusTone(card.severity)}>{card.severity}</Badge>}
      </div>
      <div className="rcard-body stack">
        <Metrics card={card} />
        <CardBody card={card} onAction={onAction} onFinding={onFinding} />
        <Actions actions={card.actions} onAction={onAction} />
      </div>
    </section>
  );
}

export function CopilotResult({ resp, onAction, onFinding }: { resp: CopilotResponse; onAction: ActionHandler; onFinding: FindingSelect }) {
  return (
    <div className="msg-assistant">
      <StatusBanner status={resp.status} />
      <div className="answer">
        <div className="answer-head">
          <div className="row"><span className="strong">LexGuard</span><StatusPill status={resp.status} />
            <Badge tone={statusTone(resp.risk)}>Risk {resp.risk}</Badge>
            {resp.routing?.route && <Badge tone="neutral">Route: {humanize(resp.routing.route)}</Badge>}</div>
          <span className="tiny muted">{resp.metrics.latency_ms} ms · {resp.metrics.paid_llm_calls} paid LLM calls</span>
        </div>
        <div>{resp.answer}</div>
      </div>
      {resp.cards.map((c, i) => <ResultCard key={`${c.type}-${i}`} card={c} onAction={onAction} onFinding={onFinding} />)}
      <AgentTrace steps={resp.agent_trace} />
    </div>
  );
}
