import { CATEGORY_LABEL } from "../format";
import { EvidenceResponse } from "../types";
import { RefLink } from "./CitationViewer";
import { Card, Chip, Empty } from "./ui";

const SUFF_TONE = { strong: "ok", moderate: "info", weak: "warn", insufficient: "bad" } as const;

export function EvidencePanel({ ev, onOpenRef, compact = false }:
  { ev: EvidenceResponse | null; onOpenRef: (r: string) => void; compact?: boolean }) {
  if (!ev || !ev.snapshot) return <Card title="Evidence"><Empty>No evidence collected yet. Run the investigation.</Empty></Card>;
  const observations = ev.items.filter((i) => i.kind === "observation");
  const statements = ev.items.filter((i) => i.kind === "statement" || i.kind === "note");
  const records = ev.items.filter((i) => i.kind === "record" || i.kind === "policy");
  const group = (title: string, items: typeof ev.items, note: string) => (
    <section aria-label={title}>
      <h4>{title} <span className="muted">({items.length})</span></h4>
      <p className="muted small">{note}</p>
      <ul className="evidence-list">
        {items.map((i) => (
          <li key={i.ref_id}>
            <RefLink refId={i.ref_id} onOpen={onOpenRef} />{" "}
            {i.freshness === "stale" && <Chip tone="warn">Stale</Chip>}{" "}
            {i.flags.includes("prompt_injection") && <Chip tone="bad">Untrusted content quarantined</Chip>}{" "}
            {i.flags.includes("proximity_only") && <Chip tone="warn">Proximity only — not on mapped path</Chip>}{" "}
            {i.supports.map((s) => <Chip key={s} tone="ok" title="Supports by documented rule">supports {s}</Chip>)}{" "}
            {i.opposes.map((s) => <Chip key={s} tone="neutral" title="Opposes by documented rule">opposes {s}</Chip>)}
            <div className={compact ? "excerpt-inline clamp" : "excerpt-inline"}>{i.excerpt}</div>
          </li>
        ))}
      </ul>
    </section>
  );
  return (
    <Card title="Evidence and hypotheses" actions={<span className="muted small">Snapshot {ev.snapshot.id}</span>}>
      <div className="stack">
        {ev.diagnosis && (
          <div className={`diag diag-${ev.diagnosis.conclusion}`}>
            <h3>{CATEGORY_LABEL[ev.diagnosis.conclusion] ?? ev.diagnosis.conclusion}</h3>
            <p>{ev.diagnosis.summary}</p>
            {ev.diagnosis.validation_errors && ev.diagnosis.validation_errors.length > 0 && (
              <details><summary>Validator notes ({ev.diagnosis.validation_errors.length})</summary>
                <ul>{ev.diagnosis.validation_errors.map((e) => <li key={e}>{e}</li>)}</ul></details>
            )}
          </div>
        )}
        {ev.hypotheses.length > 0 && (
          <section aria-label="Hypotheses">
            <h4>Hypotheses (ranked)</h4>
            <ol className="hyps">
              {ev.hypotheses.map((h) => (
                <li key={h.category}>
                  <Chip tone={SUFF_TONE[h.sufficiency as keyof typeof SUFF_TONE] ?? "neutral"}>
                    Evidence sufficiency: {h.sufficiency}
                  </Chip>{" "}
                  <strong>{h.statement}</strong>
                  <div className="small">Supporting: {h.supporting_refs.map((r) => <RefLink key={r} refId={r} onOpen={onOpenRef} />)}
                    {h.opposing_refs.length > 0 && <> · Opposing: {h.opposing_refs.map((r) => <RefLink key={r} refId={r} onOpen={onOpenRef} />)}</>}
                  </div>
                </li>
              ))}
            </ol>
            <p className="muted small">Sufficiency labels come from documented rules, not probabilities.</p>
          </section>
        )}
        {ev.snapshot.missing_evidence.length > 0 && (
          <p className="warn-note">Missing evidence: {ev.snapshot.missing_evidence.join(", ")}</p>
        )}
        {group("Measured observations", observations, "Telemetry and test measurements.")}
        {group("Reported statements and notes", statements, "What customers and agents said — not measurements.")}
        {!compact && group("Records and policies", records, "System records, mappings, incidents and synthetic knowledge documents.")}
      </div>
    </Card>
  );
}
