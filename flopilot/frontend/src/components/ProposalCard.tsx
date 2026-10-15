import { useState } from "react";
import { displayCellState, formatWithNumberFormat, uid } from "../lib/format";
import type { Operation } from "../lib/types";

interface Props {
  op: Operation;
  canApprove: boolean;
  previewing: boolean;
  onPreview: (op: Operation | null) => void;
  onApprove: (op: Operation, acknowledge: boolean, idempotencyKey: string) => Promise<void>;
  onReject: (op: Operation) => Promise<void>;
  onRefresh: (op: Operation) => Promise<void>;
}

const STATUS_LABEL: Record<Operation["status"], string> = {
  PROPOSED: "Awaiting your approval", APPLYING: "Applying…", APPLIED: "Applied", FAILED: "Not applied (failed)",
  REJECTED: "Rejected", STALE: "Out of date",
};

export function ProposalCard({ op, canApprove, previewing, onPreview, onApprove, onReject, onRefresh }: Props) {
  const [ack, setAck] = useState(false);
  const [busy, setBusy] = useState<null | "approve" | "reject" | "refresh">(null);
  // One idempotency key per card: retries of the same approval never write twice.
  const [key] = useState(uid);
  const f = op.flags;
  const pending = op.status === "PROPOSED" && !op.out_of_date;
  const formula = op.details?.formula_proposal;
  const sample = op.changes_sample ?? [];
  const cls = op.status === "APPLIED" ? "applied" : op.status === "FAILED" || op.status === "STALE" || op.out_of_date ? "failed" : op.destructive ? "destructive" : "";

  async function run(kind: "approve" | "reject" | "refresh", fn: () => Promise<void>) {
    setBusy(kind);
    try { await fn(); } finally { setBusy(null); }
  }

  return (
    <section className={`proposal ${cls}`} aria-label={`Proposed change: ${op.title}`}>
      <h4>{op.title}</h4>
      <div className="desc">{op.description}</div>
      <div className="badges">
        <span className={`chip ${op.status === "APPLIED" ? "" : op.status === "PROPOSED" && !op.out_of_date ? "neutral" : "danger"}`}>
          {op.out_of_date && op.status === "PROPOSED" ? `Out of date (prepared for v${op.base_version})` : STATUS_LABEL[op.status]}
        </span>
        <span className="chip neutral">{op.affected_cells.toLocaleString()} cell{op.affected_cells === 1 ? "" : "s"} affected</span>
        {f.overwrites_values > 0 && <span className="chip warn">Overwrites {f.overwrites_values} value{f.overwrites_values === 1 ? "" : "s"}</span>}
        {f.replaces_formulas > 0 && <span className="chip danger">Replaces {f.replaces_formulas} formula{f.replaces_formulas === 1 ? "" : "s"}</span>}
        {f.clears_values > 0 && <span className="chip danger">Clears {f.clears_values} value(s)</span>}
        {f.deletes_rows > 0 && <span className="chip danger">Deletes {f.deletes_rows} row{f.deletes_rows === 1 ? "" : "s"}</span>}
        {f.inserts_formulas > 0 && <span className="chip">Inserts {f.inserts_formulas} formula{f.inserts_formulas === 1 ? "" : "s"}</span>}
        {f.adds_sheet && <span className="chip">Adds a sheet</span>}
      </div>

      {formula && (
        <dl className="kv">
          <dt>Target</dt><dd>{formula.sheet}!{formula.target_range} (header {formula.header_cell})</dd>
          <dt>Formula</dt><dd><code>{formula.first_formula}</code> <span className="small-print">(row 2 shown; adjusts per row)</span></dd>
          <dt>Meaning</dt><dd>{formula.explanation}</dd>
          <dt>Inputs</dt><dd>{formula.inputs.join(", ")}</dd>
          <dt>Behaviour</dt><dd>{formula.expected_behavior}</dd>
          {formula.assumptions.length > 0 && <><dt>Assumptions</dt><dd>{formula.assumptions.join(" ")}</dd></>}
          <dt>References</dt><dd>{formula.anchoring}</dd>
          <dt>Compatibility</dt><dd>{formula.compatibility.join(" ")}</dd>
          <dt>Preview</dt><dd>{formula.preview_note}</dd>
        </dl>
      )}
      {op.details?.mapping && (
        <dl className="kv"><dt>Mapping</dt><dd>{Object.entries(op.details.mapping as Record<string, string>).map(([a, b]) => `“${a}” → “${b}”`).join("; ")}</dd></dl>
      )}
      {op.target_version && <p className="small-print">Version {op.target_version} will be copied into a new version. Nothing is deleted from history.</p>}

      {sample.length > 0 && (
        <table className="diff-table">
          <caption className="sr-only">Before and after values</caption>
          <thead><tr><th scope="col">Cell</th><th scope="col">Before</th><th scope="col">After</th></tr></thead>
          <tbody>
            {sample.slice(0, 6).map((c) => (
              <tr key={c.sheet + c.cell}>
                <td>{c.cell}</td>
                <td className="before" title={displayCellState(c.before)}>{displayCellState(c.before)}</td>
                <td className="after" title={displayCellState(c.after)}>{displayCellState(c.after)}{c.after.formula && c.after.value !== null && c.after.value !== "" ? ` → ${formatWithNumberFormat(c.after.value, c.number_format)}` : ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {op.changes_total > 6 && <div className="small-print">Showing 6 of {op.changes_total.toLocaleString()} cell changes. Use “Preview in grid” to see more.</div>}
      {op.removed_rows_sample?.length > 0 && (
        <div className="small-print">Rows to delete: {op.removed_rows_sample.map((r) => r.row).join(", ")} — {op.removed_rows_sample.map((r) => r.values.slice(0, 3).map((v) => String(v.value ?? "")).join(" · ")).join(" | ")}</div>
      )}
      {op.new_sheet && <div className="small-print">New sheet “{op.new_sheet.name}” with {op.new_sheet.rows.length} row(s){op.new_sheet.chart ? " and a native Excel chart (embedded in the exported file)" : ""}.</div>}

      {op.warnings.map((w) => <div key={w} className="small-print">⚠ {w}</div>)}

      {op.verification && (
        <div className="small-print" style={{ marginTop: 4 }}>
          {op.verification.status === "verified"
            ? `✓ Verified by ${op.verification.engine}: recalculated ${op.verification.checked_cells} formula cell(s)` +
              (op.verification.preview_mismatches?.length ? `; ${op.verification.preview_mismatches.length} differ from the preview — review before approving.` : "; results match the preview.") +
              (op.verification.unsupported_by_engine ? ` ${op.verification.unsupported_by_engine} use functions the engine cannot evaluate.` : "")
            : `Not verified: ${op.verification.message}`}
        </div>
      )}
      {op.dry_run && op.status === "PROPOSED" && (
        <div className="small-print">{op.dry_run.passed ? `✓ Dry run passed ${op.dry_run.checks.length} validation checks.` : "⚠ The dry run failed validation; applying is likely to fail."}</div>
      )}
      {op.requires_acknowledgement && pending && (
        <label className="ack">
          <input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} />
          <span>Applying this change drops workbook features FloPilot cannot preserve ({Object.keys(op.dry_run?.fidelity?.lost ?? {}).join(", ")}). I understand the new version will not contain them; earlier versions stay restorable.</span>
        </label>
      )}
      {!op.requires_acknowledgement && op.fidelity_at_risk.length > 0 && pending && (
        <div className="small-print">Workbook contains {op.fidelity_at_risk.map((r) => r.feature.replace(/_/g, " ")).join(", ")}; the dry run confirmed they are kept.</div>
      )}

      {op.validation && (
        <details className="how" open={!op.validation.passed}>
          <summary>{op.validation.passed ? `Validated — ${op.validation.checks.length} checks passed` : "Validation failed — nothing was changed"}</summary>
          <ul className="checks">{op.validation.checks.map((c) => <li key={c.name}><span className={c.passed ? "ok" : "bad"}>{c.passed ? "✓" : "✗"}</span><span>{c.detail}</span></li>)}</ul>
        </details>
      )}
      {op.error && <div className="small-print bad">{op.error.message}</div>}
      {op.status === "APPLIED" && op.result_version && <div className="small-print ok">Saved as version {op.result_version}. You can restore any earlier version from Activity.</div>}

      <div className="actions">
        {(sample.length > 0 || op.removed_rows_sample?.length > 0) && op.status === "PROPOSED" && (
          <button className="btn small" onClick={() => onPreview(previewing ? null : op)} aria-pressed={previewing}>
            {previewing ? "Hide preview" : "Preview in grid"}
          </button>
        )}
        {pending && (
          <>
            <button className="btn primary small" disabled={!canApprove || busy !== null || (op.requires_acknowledgement && !ack)}
              onClick={() => run("approve", () => onApprove(op, ack, key))}>
              {busy === "approve" ? "Applying…" : "Approve & apply"}
            </button>
            <button className="btn small danger" disabled={!canApprove || busy !== null} onClick={() => run("reject", () => onReject(op))}>Reject</button>
          </>
        )}
        {(op.out_of_date || op.status === "STALE" || (op.status === "FAILED" && op.details?.builder)) && (
          <button className="btn small" disabled={!canApprove || busy !== null} onClick={() => run("refresh", () => onRefresh(op))}>
            {busy === "refresh" ? "Preparing…" : "Prepare again for current version"}
          </button>
        )}
      </div>
      {!canApprove && pending && <div className="small-print">Your role can view proposals but not approve them.</div>}
    </section>
  );
}
