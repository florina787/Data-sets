import type { ReactNode } from "react";
import type { DataStatus } from "../lib/api";
import { Sparkline } from "./charts";

const STATUS_HELP: Record<DataStatus, string> = {
  LIVE: "Streamed within the provider's freshness window",
  DELAYED: "Exchange-delayed quote",
  CACHED: "Served from cache; older than the freshness window",
  HISTORICAL: "End-of-day / archived history",
  SYNTHETIC: "Generated test data with no market meaning",
  HYPOTHETICAL: "Scenario output, not a fact",
};

export function StatusBadge({ status }: { status: DataStatus }) {
  return <span className={`badge ${status}`} title={STATUS_HELP[status]}>{status}</span>;
}

export function Panel({ title, right, children, className = "" }: { title?: ReactNode; right?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`panel ${className}`}>
      {title && <h2>{title}{right && <span className="right">{right}</span>}</h2>}
      {children}
    </section>
  );
}

export function KpiCard({ label, change, value, sub, spark, focus }: {
  label: string; change?: string; value: string; sub?: string; spark?: number[]; focus?: boolean;
}) {
  const neg = change?.startsWith("-");
  return (
    <div className={`kpi ${focus ? "focus" : ""}`}>
      <span className="pill">{label}{change && <span className={neg ? "down" : "up"}>{neg ? "↓" : "↑"} {change.replace(/^[+-]/, "")}</span>}</span>
      <div className="row"><span>{sub}</span>{spark && <Sparkline values={spark} color="rgba(255,255,255,.75)" />}</div>
      <div className="big num">{value}</div>
    </div>
  );
}

export function Loading() { return <div className="skeleton" aria-busy="true" aria-label="Loading" />; }
export function ErrorBox({ error }: { error: string }) { return <div className="error" role="alert">Could not load: {error}</div>; }

export function SyntheticNotice({ status }: { status?: DataStatus }) {
  if (status !== "SYNTHETIC") return null;
  return (
    <div className="callout" role="note">
      Everything on this page comes from the <b>SYNTHETIC</b> engineering dataset. Tickers, prices and results are generated,
      not real markets, and say nothing about future returns.
    </div>
  );
}
