import type { ReactNode } from "react";

import type { AvailabilityStatus } from "../services/api";

export function Card({ title, actions, children, className = "" }: { title?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`card min-w-0 p-5 ${className}`}>
      {(title || actions) && (
        <header className="mb-3 flex flex-wrap items-center justify-between gap-2">
          {title && <h2 className="h2">{title}</h2>}
          {actions}
        </header>
      )}
      {children}
    </section>
  );
}

export function Stat({ label, value, hint, tone = "brand" }: { label: string; value: ReactNode; hint?: string; tone?: "brand" | "teal" | "ok" | "warn" | "danger" }) {
  const color = { brand: "text-brand", teal: "text-teal", ok: "text-ok", warn: "text-warn", danger: "text-danger" }[tone];
  return (
    <div className="card p-4">
      <div className="text-xs font-semibold uppercase tracking-wide text-slate-600">{label}</div>
      <div className={`mt-1 text-2xl font-bold ${color}`}>{value}</div>
      {hint && <div className="mt-1 text-xs text-slate-500">{hint}</div>}
    </div>
  );
}

const STATUS_STYLE: Record<string, { cls: string; label: string }> = {
  VERIFIED_AVAILABLE: { cls: "bg-green-50 text-ok border-green-200", label: "Verified" },
  ADVERTISED_UNVERIFIED: { cls: "bg-amber-50 text-[#9A4500] border-amber-200", label: "Advertised · unverified" },
  CONTACT_REQUIRED: { cls: "bg-orange-50 text-[#9A4500] border-orange-200", label: "Contact required" },
  UNAVAILABLE: { cls: "bg-slate-100 text-slate-600 border-slate-200", label: "Unavailable" },
  UNKNOWN: { cls: "bg-red-50 text-danger border-red-200", label: "Unknown" },
  DEMO_SIMULATED: { cls: "bg-violet-50 text-violet-800 border-violet-200", label: "Demo data" },
};

export function AvailabilityBadge({ status, simulated }: { status: AvailabilityStatus | string; simulated?: boolean }) {
  const s = STATUS_STYLE[status] ?? STATUS_STYLE.UNKNOWN;
  return (
    <span className="inline-flex flex-wrap items-center gap-1">
      <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-semibold ${s.cls}`}>
        {status === "VERIFIED_AVAILABLE" ? "✓ " : status === "UNKNOWN" ? "? " : ""}{s.label}
      </span>
      {simulated && <span className={`inline-flex rounded-full border px-2 py-0.5 text-[10px] font-bold ${STATUS_STYLE.DEMO_SIMULATED.cls}`}>DEMO_SIMULATED</span>}
    </span>
  );
}

export function Pill({ children, tone = "slate" }: { children: ReactNode; tone?: "slate" | "brand" | "teal" | "ok" | "warn" | "danger" }) {
  const cls = {
    slate: "bg-slate-100 text-slate-700", brand: "bg-brand-50 text-brand-700", teal: "bg-teal-50 text-teal-700",
    ok: "bg-green-50 text-ok", warn: "bg-amber-50 text-[#9A4500]", danger: "bg-red-50 text-danger",
  }[tone];
  return <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${cls}`}>{children}</span>;
}

export function DemoBanner({ text = "DEMONSTRATION DATA — NOT LIVE APPOINTMENT AVAILABILITY" }: { text?: string }) {
  return (
    <div role="note" className="rounded-xl border border-violet-200 bg-violet-50 px-4 py-2 text-center text-xs font-bold tracking-wide text-violet-800">
      {text}
    </div>
  );
}

export function Alert({ tone = "warn", title, children }: { tone?: "warn" | "danger" | "ok" | "info"; title?: string; children: ReactNode }) {
  const cls = {
    warn: "border-amber-300 bg-amber-50 text-[#7A3A00]", danger: "border-red-300 bg-red-50 text-[#8E1F1F]",
    ok: "border-green-300 bg-green-50 text-[#1B5E20]", info: "border-brand-100 bg-brand-50 text-brand-800",
  }[tone];
  return (
    <div role={tone === "danger" ? "alert" : "status"} className={`rounded-xl border px-4 py-3 text-sm ${cls}`}>
      {title && <div className="mb-0.5 font-semibold">{title}</div>}
      {children}
    </div>
  );
}

export function Spinner({ label = "Loading" }: { label?: string }) {
  return (
    <span role="status" className="inline-flex items-center gap-2 text-sm text-slate-600">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-brand border-t-transparent" aria-hidden="true" />
      {label}
    </span>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="rounded-xl border border-dashed border-slate-300 p-6 text-center text-sm text-slate-600">{children}</div>;
}

export function Json({ value }: { value: unknown }) {
  return <pre className="code max-h-80">{JSON.stringify(value, null, 2)}</pre>;
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="h1">{title}</h1>
        {subtitle && <p className="muted mt-1 max-w-3xl">{subtitle}</p>}
      </div>
      {actions}
    </div>
  );
}

export function ErrorText({ error }: { error: string | null }) {
  return error ? <Alert tone="danger">{error}</Alert> : null;
}

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("en-CA", { timeZone: "America/Toronto", dateStyle: "medium", timeStyle: "short" });
}

export function fmtAge(iso: string | null | undefined): string {
  if (!iso) return "unknown";
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (mins < 60) return `${mins} min ago`;
  const h = Math.round(mins / 60);
  return h < 48 ? `${h} h ago` : `${Math.round(h / 24)} days ago`;
}
