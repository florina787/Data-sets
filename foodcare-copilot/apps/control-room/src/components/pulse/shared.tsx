import { useEffect, useState } from "react";
import { api } from "../../api";
import { useApp } from "../../context";

export type Provenance = "verified" | "operational_record" | "modeled" | "synthetic" | "mixed" | null;
export type Evidence = { label: string; ref: string; provenance: Provenance; as_of: string | null };
export type Priority = {
  id: string; severity: "high" | "medium" | "low"; score: number; title: string; why: string; areas: string[];
  evidence: Evidence[]; owner: string; next_step: string; jerry_question: string; link: string; metric: string | null;
  provenance: Provenance; as_of: string | null;
};
export type Health = { key: string; label: string; question: string; value: string; status: Status; explanation: string;
  provenance: Provenance; as_of: string | null; link: string };
export type Status = "good" | "watch" | "attention" | "unknown";

const PROV: Record<string, { text: string; cls: string; title: string }> = {
  verified: { text: "Verified", cls: "border-leaf-500/70 text-leaf-700", title: "Verified enterprise data" },
  operational_record: { text: "Operational record", cls: "border-teal/70 text-teal-soft", title: "Recorded by this app (inspections, incidents, deployments, agent runs)" },
  modeled: { text: "Modelled", cls: "border-royal-400/70 text-royal-400", title: "A modelled scenario with uncertainty, not a forecast of real events" },
  synthetic: { text: "Synthetic", cls: "border-champagne/70 text-champagne", title: "Synthetic demonstration data, not real business results" },
  mixed: { text: "Mixed sources", cls: "border-surface-line text-ink-muted", title: "Combines several kinds of source" },
};

export function ProvenanceChip({ kind }: { kind: Provenance }) {
  if (!kind) return null;
  const p = PROV[kind];
  return <span className={`chip ${p.cls}`} title={p.title} data-provenance={kind}>{p.text}</span>;
}

const STATUS: Record<Status, { dot: string; text: string; label: string }> = {
  good: { dot: "bg-leaf-500", text: "text-leaf-700", label: "Good" },
  watch: { dot: "bg-risk-amber", text: "text-amber-700", label: "Watch" },
  attention: { dot: "bg-risk", text: "text-brick-700", label: "Needs attention" },
  unknown: { dot: "bg-ink-faint", text: "text-ink-muted", label: "No data" },
};

export function StatusDot({ status }: { status: Status }) {
  const s = STATUS[status] ?? STATUS.unknown;
  return (
    <span className={`inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap text-xs font-medium ${s.text}`}>
      <span aria-hidden className={`h-2 w-2 rounded-full ${s.dot}`} />{s.label}
    </span>
  );
}

export function freshness(iso: string | null | undefined): string {
  if (!iso) return "date unknown";
  const d = new Date(iso.length === 10 ? `${iso}T00:00:00Z` : iso);
  if (Number.isNaN(d.getTime())) return iso;
  const mins = Math.round((Date.now() - d.getTime()) / 60000);
  if (iso.length === 10) return `as of ${iso}`;
  if (mins < 2) return "just now";
  if (mins < 60) return `${mins} min ago`;
  if (mins < 60 * 24) return `${Math.round(mins / 60)} h ago`;
  return `as of ${iso.slice(0, 10)}`;
}

export const SEVERITY: Record<string, string> = {
  high: "border-risk/60 bg-brick-100/60 text-brick-700", medium: "border-risk-amber/50 bg-amber-100/50 text-amber-700",
  low: "border-surface-line bg-elevated text-ink-muted",
};

/** Lens → business areas shown first. A lens never changes permissions. */
export const LENS_FOCUS: Record<string, string[]> = {
  cto: ["Technology", "Global network", "Supply chain"], executive: ["Sales", "Finance", "Supply chain"],
  factory: ["Quality", "Supply chain"], quality: ["Quality", "Compliance & food safety"],
  supply: ["Supply chain", "Global network"], sales: ["Sales", "Marketing", "Online sales"],
  admin: ["Technology", "Online sales"],
};

export function sortForLens<T extends { areas: string[]; score: number }>(items: T[], lens: string | undefined): T[] {
  const focus = LENS_FOCUS[lens ?? "cto"] ?? [];
  const boost = (p: T) => (p.areas.some((a) => focus.includes(a)) ? 15 : 0);
  return [...items].sort((a, b) => b.score + boost(b) - (a.score + boost(a)));
}

/** The user's lens, kept in sync with the header switcher. */
export function useLens(): string | undefined {
  const { user } = useApp();
  const [lens, setLens] = useState<string>();
  useEffect(() => {
    if (!user) return setLens(undefined);
    api("/api/me/lens").then((s) => setLens(s.lens)).catch(() => undefined);
    const on = (e: Event) => setLens((e as CustomEvent).detail);
    window.addEventListener("lens:changed", on);
    return () => window.removeEventListener("lens:changed", on);
  }, [user?.username]);
  return lens;
}

export function Skeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div className="space-y-2" aria-busy="true" aria-label="Loading">
      {Array.from({ length: lines }).map((_, i) => <div key={i} className="skeleton h-4" style={{ width: `${90 - i * 12}%` }} />)}
    </div>
  );
}

export function SignInPrompt({ what }: { what: string }) {
  return (
    <div className="panel max-w-xl">
      <div className="eyebrow">Welcome to Flo &amp; Jerry 3.0</div>
      <h1 className="mt-2 text-2xl font-semibold text-ink">Choose a demo account to see {what}.</h1>
      <p className="mt-2 text-sm text-ink-muted">Use <b>Signed in as</b> in the top-right corner. Each account sees only its own decisions,
        investigations and inspections. Your workspace lens (CTO, CEO, factory, quality, supply chain, sales or administrator)
        changes what is shown first; your account role decides what you are allowed to do.</p>
    </div>
  );
}
