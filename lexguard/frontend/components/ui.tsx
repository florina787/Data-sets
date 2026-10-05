"use client";

import { statusTone, humanize, type Tone } from "@/lib/format";
import type { ApiError } from "@/lib/api";

export function Badge({ children, tone = "neutral", title }: { children: React.ReactNode; tone?: Tone; title?: string }) {
  return <span className={`badge tone-${tone}`} title={title}>{children}</span>;
}

export function StatusPill({ status, label }: { status: string | null | undefined; label?: string }) {
  if (!status) return null;
  return <Badge tone={statusTone(status)}>{label ?? humanize(status)}</Badge>;
}

export function Tip({ text }: { text: string }) {
  return (
    <span className="tip" tabIndex={0} aria-label={text}>
      <svg width="13" height="13" viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="7" fill="none" stroke="currentColor" strokeWidth="1.4" /><path d="M8 7v4M8 4.6v.1" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" /></svg>
      <span className="tip-body" role="tooltip">{text}</span>
    </span>
  );
}

export function Kpi({ label, value, tone, hint, tip }: { label: string; value: React.ReactNode; tone?: string | null; hint?: string; tip?: string }) {
  return (
    <div className="panel kpi">
      <div className="kpi-label">{label}{tip && <Tip text={tip} />}</div>
      <div className={`kpi-value ${tone ?? ""}`}>{value}</div>
      {hint && <div className="kpi-hint">{hint}</div>}
    </div>
  );
}

export function Spinner({ label }: { label?: string }) {
  return <span className="row muted small" role="status"><span className="spinner" aria-hidden="true" />{label ?? "Loading"}</span>;
}

export function LoadingBlock({ rows = 4 }: { rows?: number }) {
  return <div className="panel-body" aria-busy="true">{Array.from({ length: rows }).map((_, i) =>
    <div key={i} className="skeleton" style={{ width: `${90 - i * 12}%` }} />)}</div>;
}

export function Empty({ title, children }: { title: string; children?: React.ReactNode }) {
  return <div className="empty"><strong>{title}</strong>{children}</div>;
}

export function ErrorBox({ error, onRetry }: { error: ApiError | Error | null; onRetry?: () => void }) {
  if (!error) return null;
  return (
    <div className="error-box row" role="alert" style={{ justifyContent: "space-between" }}>
      <span>{error.message}</span>
      {onRetry && <button className="btn btn-sm" onClick={onRetry}>Retry</button>}
    </div>
  );
}

export function Bar({ value, tone }: { value: number; tone?: Tone }) {
  return <div className={`bar ${tone ?? ""}`} role="meter" aria-valuenow={Math.round(value * 100)} aria-valuemin={0} aria-valuemax={100}>
    <span style={{ width: `${Math.max(0, Math.min(1, value)) * 100}%` }} /></div>;
}

export function PageHead({ title, description, children }: { title: string; description?: string; children?: React.ReactNode }) {
  return (
    <div className="page-head">
      <div><h1>{title}</h1>{description && <p>{description}</p>}</div>
      {children && <div className="row">{children}</div>}
    </div>
  );
}

export function Panel({ title, actions, children, bodyClass = "panel-body" }:
  { title?: React.ReactNode; actions?: React.ReactNode; children: React.ReactNode; bodyClass?: string }) {
  return (
    <section className="panel">
      {title && <div className="panel-head"><h2>{title}</h2>{actions}</div>}
      <div className={bodyClass}>{children}</div>
    </section>
  );
}
