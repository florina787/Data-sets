import { ReactNode } from "react";

export const PROVENANCE: Record<string, { label: string; cls: string }> = {
  tool: { label: "Executed tool", cls: "bg-navy-100 text-navy-800 border-navy-600/30" },
  deterministic: { label: "Deterministic", cls: "bg-cream-200 text-navy-800 border-cream-300" },
  fixture: { label: "Fixture proposal", cls: "bg-amber-100 text-amber-700 border-amber-700/30" },
  seeded_decision: { label: "Selected demo decision", cls: "bg-amber-100 text-amber-700 border-amber-700/30" },
  live_ai: { label: "Live AI output", cls: "bg-leaf-100 text-leaf-700 border-leaf-600/30" },
  human: { label: "Human action", cls: "bg-white text-navy-800 border-navy-600/40" },
  injected_fault: { label: "Injected fault (demo)", cls: "bg-brick-100 text-brick-700 border-brick-700/30" },
};

export function Provenance({ kind }: { kind: string }) {
  const p = PROVENANCE[kind] ?? { label: kind, cls: "bg-cream-200 text-navy-800 border-cream-300" };
  return <span className={`inline-block whitespace-nowrap rounded border px-1.5 py-0.5 text-[11px] font-semibold ${p.cls}`}>{p.label}</span>;
}

const STATUS_STYLE: Record<string, string> = {
  passed: "bg-leaf-100 text-leaf-700", deployed: "bg-leaf-100 text-leaf-700", healthy: "bg-leaf-100 text-leaf-700",
  done: "bg-leaf-100 text-leaf-700", resolved: "bg-leaf-100 text-leaf-700", approved: "bg-leaf-100 text-leaf-700",
  succeeded: "bg-leaf-100 text-leaf-700", order_created: "bg-leaf-100 text-leaf-700", ok: "bg-leaf-100 text-leaf-700",
  failed: "bg-brick-100 text-brick-700", blocked: "bg-brick-100 text-brick-700", error: "bg-brick-100 text-brick-700",
  open: "bg-brick-100 text-brick-700", "rolled-back": "bg-amber-100 text-amber-700", rejected: "bg-brick-100 text-brick-700",
  invalidated: "bg-cream-200 text-navy-600", superseded: "bg-cream-200 text-navy-600", stopped: "bg-cream-200 text-navy-600",
  pending: "bg-cream-200 text-navy-600", skipped: "bg-cream-200 text-navy-600",
  waiting: "bg-amber-100 text-amber-700", "awaiting-approval": "bg-amber-100 text-amber-700",
  "awaiting-release-approval": "bg-amber-100 text-amber-700", "clarification-needed": "bg-amber-100 text-amber-700",
  "requirements-review": "bg-amber-100 text-amber-700", mitigated: "bg-amber-100 text-amber-700",
  paused: "bg-amber-100 text-amber-700", running: "bg-navy-100 text-navy-800", active: "bg-navy-100 text-navy-800",
};

export function Status({ value }: { value: string | null | undefined }) {
  const v = value ?? "unknown";
  return (
    <span className={`inline-block whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-semibold ${STATUS_STYLE[v] ?? "bg-cream-200 text-navy-800"}`}>
      {v}
    </span>
  );
}

export function Card({ title, actions, children, className = "" }: { title?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`card ${className}`}>
      {(title || actions) && (
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          {title && <h2 className="text-base font-semibold text-navy-900">{title}</h2>}
          {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
        </div>
      )}
      {children}
    </section>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="rounded-lg border border-dashed border-cream-300 bg-cream-50 p-4 text-sm text-navy-600">{children}</p>;
}

export function Notice({ kind = "info", children }: { kind?: "info" | "warn" | "error" | "ok"; children: ReactNode }) {
  const cls = {
    info: "border-navy-600/30 bg-navy-100 text-navy-900",
    warn: "border-amber-700/30 bg-amber-100 text-amber-700",
    error: "border-brick-700/30 bg-brick-100 text-brick-700",
    ok: "border-leaf-600/30 bg-leaf-100 text-leaf-700",
  }[kind];
  return <div role={kind === "error" ? "alert" : "status"} className={`rounded-lg border px-3 py-2 text-sm ${cls}`}>{children}</div>;
}

export function ActionMessage({ message }: { message: { kind: "ok" | "error"; text: string } | null }) {
  if (!message) return null;
  return <Notice kind={message.kind === "ok" ? "ok" : "error"}>{message.text}</Notice>;
}

export function Short({ value, n = 10 }: { value: string | null | undefined; n?: number }) {
  if (!value) return <span className="text-navy-600">-</span>;
  return <code className="mono rounded bg-cream-200 px-1 text-navy-900" title={value}>{value.slice(0, n)}</code>;
}

export function DiffView({ diff }: { diff: string }) {
  return (
    <pre className="max-h-[560px] overflow-auto rounded-lg border border-cream-300 bg-navy-950 p-3 text-xs leading-relaxed text-cream-100" aria-label="Unified diff">
      {diff.split("\n").map((line, i) => {
        let cls = "";
        if (line.startsWith("+++") || line.startsWith("---")) cls = "text-cream-300 font-semibold";
        else if (line.startsWith("+")) cls = "bg-leaf-700/40 text-[#c9f2d6]";
        else if (line.startsWith("-")) cls = "bg-brick-700/40 text-[#ffd5d5]";
        else if (line.startsWith("@@")) cls = "text-[#9ab8f0]";
        else if (line.startsWith("diff --git")) cls = "mt-2 block border-t border-navy-700 pt-2 font-semibold text-cream-50";
        return <span key={i} className={`block whitespace-pre ${cls}`}>{line || " "}</span>;
      })}
    </pre>
  );
}

export function Pre({ children, label }: { children: ReactNode; label?: string }) {
  return (
    <pre aria-label={label} className="max-h-[480px] overflow-auto whitespace-pre-wrap break-words rounded-lg border border-cream-300 bg-cream-50 p-3 font-mono text-xs text-navy-900">
      {children}
    </pre>
  );
}

export function Time({ value }: { value: string | null | undefined }) {
  if (!value) return <span className="text-navy-600">-</span>;
  const d = new Date(value);
  return <time dateTime={value} title={value}>{d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}</time>;
}
