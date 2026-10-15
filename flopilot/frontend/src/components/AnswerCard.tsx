import { Chart } from "./Chart";
import { ProposalCard } from "./ProposalCard";
import { RichText } from "./RichText";
import type { AssistantResult, Operation, Source } from "../lib/types";

interface Props {
  result: AssistantResult;
  operations: Record<string, Operation>;
  canApprove: boolean;
  previewOpId: string | null;
  onSource: (s: Source) => void;
  onPrompt: (prompt: string) => void;
  onPreview: (op: Operation | null) => void;
  onApprove: (op: Operation, acknowledge: boolean, key: string) => Promise<void>;
  onReject: (op: Operation) => Promise<void>;
  onRefresh: (op: Operation) => Promise<void>;
  onRetry?: () => void;
}

export function AnswerCard(props: Props) {
  const { result: r } = props;
  const primary = r.results?.[0];
  const table = primary && Array.isArray(primary.rows) && ["aggregate", "variance", "period_change"].includes(primary.kind) ? primary : null;
  const hasHow = r.method || (r.assumptions?.length ?? 0) > 0 || (r.warnings?.length ?? 0) > 0 || r.missing_treatment;
  return (
    <div className={`bot-card ${r.type === "error" ? "error" : ""}`}>
      <RichText text={r.text} />

      {r.clarification && (
        <div className="meta-row" role="group" aria-label="Choose an option">
          {r.clarification.options.map((o) => <button key={o.label} className="btn small" onClick={() => props.onPrompt(o.prompt)}>{o.label}</button>)}
        </div>
      )}

      {r.chart && <Chart spec={r.chart} />}
      {table && !r.chart && <ResultTable result={table} />}

      {r.operations?.map((op) => {
        const live = props.operations[op.id] ?? op;
        return (
          <ProposalCard key={op.id} op={live} canApprove={props.canApprove} previewing={props.previewOpId === op.id}
            onPreview={props.onPreview} onApprove={props.onApprove} onReject={props.onReject} onRefresh={props.onRefresh} />
        );
      })}

      {(r.sources?.length ?? 0) > 0 && (
        <div className="meta-row">
          <span className="meta-label">Sources</span>
          {r.sources!.map((s) => (
            <button key={s.id} className="chip link" onClick={() => props.onSource(s)} title={`${s.label} · version ${s.version}${s.status !== "current" ? ` · ${s.status}` : ""}`}>
              {s.label}{s.status === "stale" ? " (out of date)" : ""}
            </button>
          ))}
        </div>
      )}

      {hasHow && (
        <details className="how">
          <summary>How this was calculated</summary>
          <ul>
            {r.method && <li><strong>Method:</strong> {r.method}</li>}
            {r.missing_treatment && <li><strong>Missing data:</strong> {r.missing_treatment}</li>}
            {(r.filters?.length ?? 0) > 0 && <li><strong>Filters:</strong> {(r.filters as { column: string; op: string; value: unknown }[]).map((f) => `${f.column} ${f.op} ${JSON.stringify(f.value)}`).join("; ")}</li>}
            {r.assumptions?.map((a) => <li key={a}><strong>Assumption:</strong> {a}</li>)}
            {r.warnings?.map((w) => <li key={w}><strong>Note:</strong> {w}</li>)}
          </ul>
        </details>
      )}

      {(r.follow_ups?.length ?? 0) > 0 && (
        <div className="meta-row">
          {r.follow_ups!.map((f) => <button key={f.label} className="chip link" onClick={() => props.onPrompt(f.prompt)}>{f.label}</button>)}
        </div>
      )}
      {r.notes?.map((n) => <div key={n} className="small-print">ℹ {n}</div>)}
      {r.type === "error" && r.retryable && props.onRetry && <div className="actions"><button className="btn small" onClick={props.onRetry}>Try again</button></div>}
      {r.engine && (
        <div className="engine-note">
          {r.engine === "deterministic-demo" ? "Demo mode: deterministic rules, no AI model." : r.engine.startsWith("llm:") ? `Interpreted by ${r.engine.slice(4)}; numbers checked against calculations.` : "Computed by FloPilot's calculation tools."}
          {r.usage && r.usage.tokens_in > 0 ? ` · ${r.usage.tokens_in + r.usage.tokens_out} tokens, est. $${r.usage.cost_estimate_usd.toFixed(4)} (estimate)` : ""}
          {r.grounding?.ungrounded?.length ? ` · ${r.grounding.ungrounded.length} unverified number(s) removed` : ""}
        </div>
      )}
    </div>
  );
}

function ResultTable({ result }: { result: any }) {
  const rows = (result.rows as any[]).slice(0, 15);
  if (result.kind === "variance") {
    return (
      <table className="result-table">
        <thead><tr><th>{result.group_by[0] ?? "Group"}</th><th>{result.actual}</th><th>{result.budget}</th><th>Variance</th></tr></thead>
        <tbody>{rows.map((r) => <tr key={String(r.group)}><td>{r.group.join(" / ")}</td><td className="num">{fmt(r.actual)}</td><td className="num">{fmt(r.budget)}</td><td className="num">{fmt(r.value)}</td></tr>)}</tbody>
      </table>
    );
  }
  if (!result.group_by?.length) return null;
  return (
    <table className="result-table">
      <thead><tr><th>{result.group_by.join(" / ")}</th><th>{result.function ?? "value"} of {result.measure ?? "rows"}</th><th>Rows</th></tr></thead>
      <tbody>{rows.map((r) => <tr key={String(r.group)}><td>{r.group.join(" / ")}</td><td className="num">{fmt(r.value)}</td><td className="num">{r.rows ?? ""}</td></tr>)}</tbody>
    </table>
  );
}

function fmt(v: unknown): string {
  return typeof v === "number" ? v.toLocaleString("en-US", { maximumFractionDigits: 2 }) : v === null || v === undefined ? "—" : String(v);
}
