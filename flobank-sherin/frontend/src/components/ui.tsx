import { useEffect, type ReactNode } from "react";
import { AlertTriangle, Info, Loader2, X } from "lucide-react";
import { SherinAvatar } from "./SherinAvatar";

export function Card({ children, className = "", id }: { children: ReactNode; className?: string; id?: string }) {
  return <section id={id} className={`card ${className}`}>{children}</section>;
}

export function ChartCard({ id, title, subtitle, actions, children, badges, className = "" }:
  { id?: string; title: string; subtitle?: ReactNode; actions?: ReactNode; children: ReactNode; badges?: ReactNode; className?: string }) {
  return (
    <Card id={id} className={`p-5 scroll-mt-24 fade-in ${className}`}>
      <header className="mb-2 flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="font-display text-xl font-semibold text-flo-900">{title}</h2>
          {subtitle && <p className="mt-0.5 text-sm text-muted">{subtitle}</p>}
          {badges && <div className="mt-1.5 flex flex-wrap gap-1.5">{badges}</div>}
        </div>
        {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
      </header>
      {children}
    </Card>
  );
}

const TONE: Record<string, string> = {
  green: "bg-flo-100 text-flo-800 border-flo-200", gold: "bg-gold-light text-[#7A5D1E] border-[#E8D7AE]", red: "bg-red-light text-red border-[#EFC9C6]",
  amber: "bg-amber-light text-amber border-[#EED9B5]", slate: "bg-[#EEF2F4] text-[#4A5A66] border-[#DCE3E8]", dark: "bg-flo-900 text-white border-flo-900",
};
export function Badge({ children, tone = "slate", title }: { children: ReactNode; tone?: keyof typeof TONE; title?: string }) {
  return <span title={title} className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full border px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide ${TONE[tone]}`}>{children}</span>;
}

export function DataClassBadge({ dc }: { dc: string }) {
  return dc === "synthetic"
    ? <Badge tone="gold" title="Seeded demonstration data. Not actual business performance.">Synthetic demo</Badge>
    : <Badge tone="green" title="Measured by this running system">Measured</Badge>;
}
export function BasisBadge({ basis }: { basis: string }) {
  const tone = basis === "actual" ? "slate" : basis === "forecast" ? "amber" : "amber";
  return <Badge tone={tone} title={basis === "estimated" ? "Calculated estimate, not booked cash" : basis === "forecast" ? "Projection, not a guarantee" : "Recorded value"}>{basis}</Badge>;
}

export const DECISION_TONE: Record<string, keyof typeof TONE> = { PASS: "green", REVIEW: "amber", BLOCK: "red", INSUFFICIENT_DATA: "slate" };
export function DecisionBadge({ d }: { d: string | null | undefined }) {
  if (!d) return <Badge>not evaluated</Badge>;
  return <Badge tone={DECISION_TONE[d] ?? "slate"}>{d.replace("_", " ")}</Badge>;
}
export const STATUS_TONE: Record<string, keyof typeof TONE> = {
  pending: "amber", partially_approved: "amber", escalated: "amber", changes_requested: "slate", approved: "green", rejected: "red", blocked: "red",
  insufficient_data: "slate", running: "green", awaiting_approval: "amber", completed: "green", failed: "red", queued: "slate", idle: "slate", waiting: "amber",
};
export function StatusBadge({ s }: { s: string }) { return <Badge tone={STATUS_TONE[s] ?? (s.startsWith("completed_") ? "slate" : "slate")}>{s.replace(/_/g, " ")}</Badge>; }

export function Segmented<T extends string>({ value, options, onChange, label, size = "sm" }: { value: T; options: { value: T; label: string }[]; onChange: (v: T) => void; label: string; size?: "sm" | "xs" }) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex rounded-full border border-line bg-flo-50 p-0.5">
      {options.map((o) => (
        <button key={o.value} type="button" role="radio" aria-checked={value === o.value} onClick={() => onChange(o.value)}
          className={`rounded-full ${size === "xs" ? "px-2 py-0.5 text-[11px]" : "px-3 py-1 text-xs"} font-semibold transition ${value === o.value ? "bg-flo-800 text-white shadow" : "text-muted hover:text-flo-800"}`}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Button({ children, onClick, variant = "primary", type = "button", disabled, title, className = "" }:
  { children: ReactNode; onClick?: () => void; variant?: "primary" | "ghost" | "danger" | "outline"; type?: "button" | "submit"; disabled?: boolean; title?: string; className?: string }) {
  const v = { primary: "bg-flo-800 text-white hover:bg-flo-700", ghost: "text-flo-800 hover:bg-flo-100", danger: "bg-red text-white hover:opacity-90",
    outline: "border border-line bg-white text-flo-900 hover:border-flo-600" }[variant];
  return <button type={type} title={title} disabled={disabled} onClick={onClick}
    className={`inline-flex items-center justify-center gap-1.5 rounded-full px-3.5 py-1.5 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-50 ${v} ${className}`}>{children}</button>;
}

export function Spinner({ label = "Loading" }: { label?: string }) {
  return <div className="flex items-center gap-2 p-6 text-sm text-muted" role="status"><Loader2 className="h-4 w-4 animate-spin text-flo-700" aria-hidden />{label}…</div>;
}
export function ErrorBox({ error }: { error: string | null }) {
  if (!error) return null;
  return <div role="alert" className="flex items-start gap-2 rounded-xl border border-[#EFC9C6] bg-red-light p-3 text-sm text-red"><AlertTriangle className="mt-0.5 h-4 w-4" aria-hidden />{error}</div>;
}
export function Note({ children }: { children: ReactNode }) {
  return <p className="mt-2 flex items-start gap-1.5 text-xs text-muted"><Info className="mt-0.5 h-3.5 w-3.5 shrink-0 text-flo-700" aria-hidden /><span>{children}</span></p>;
}

export function Drawer({ open, onClose, title, children, width = 640 }: { open: boolean; onClose: () => void; title: ReactNode; children: ReactNode; width?: number }) {
  useEffect(() => {
    if (!open) return;
    const k = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex justify-end" role="dialog" aria-modal="true" aria-label={typeof title === "string" ? title : "Details"}>
      <button type="button" aria-label="Close" className="absolute inset-0 bg-flo-950/30 backdrop-blur-[1px]" onClick={onClose} />
      <div className="relative h-full w-full overflow-y-auto bg-white p-6 shadow-2xl fade-in scroll-thin" style={{ maxWidth: width }}>
        <div className="mb-4 flex items-start justify-between gap-3">
          <div className="flex items-center gap-3"><SherinAvatar size="sm" /><h2 className="font-display text-xl font-semibold text-flo-900">{title}</h2></div>
          <button type="button" onClick={onClose} aria-label="Close panel" className="rounded-full p-1.5 hover:bg-flo-50"><X className="h-5 w-5" /></button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function PageHeader({ title, subtitle, children }: { title: string; subtitle?: string; children?: ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-center justify-between gap-4">
      <div className="flex items-center gap-4">
        <SherinAvatar size="lg" />
        <div>
          <h1 className="font-display text-3xl font-semibold text-flo-900">{title}</h1>
          {subtitle && <p className="text-sm text-muted">{subtitle}</p>}
        </div>
      </div>
      {children && <div className="flex flex-wrap items-center gap-2">{children}</div>}
    </div>
  );
}

export function Table({ columns, rows, empty = "No records", dense }: { columns: { key: string; label: string; align?: "right"; render?: (r: any) => ReactNode }[]; rows: any[]; empty?: string; dense?: boolean }) {
  return (
    <div className="overflow-x-auto scroll-thin">
      <table className="w-full text-sm">
        <thead><tr className="border-b border-line text-left text-[11px] uppercase tracking-wide text-muted">
          {columns.map((c) => <th key={c.key} className={`px-2 py-2 font-semibold ${c.align === "right" ? "text-right" : ""}`}>{c.label}</th>)}
        </tr></thead>
        <tbody>
          {rows.length === 0 && <tr><td colSpan={columns.length} className="px-2 py-6 text-center text-muted">{empty}</td></tr>}
          {rows.map((r, i) => (
            <tr key={r.id ?? i} className="border-b border-line/60 last:border-0 hover:bg-flo-50/60">
              {columns.map((c) => <td key={c.key} className={`px-2 ${dense ? "py-1.5" : "py-2"} align-top ${c.align === "right" ? "text-right tnum" : ""}`}>{c.render ? c.render(r) : String(r[c.key] ?? "—")}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Minimal, safe markdown: **bold**, _italic_, `code`, lists, paragraphs. No raw HTML is ever injected. */
export function Markdown({ text }: { text: string }) {
  const blocks = text.split(/\n{2,}/);
  return (
    <div className="md text-sm leading-relaxed">
      {blocks.map((b, i) => {
        const lines = b.split("\n");
        if (lines.every((l) => /^\s*[-*] /.test(l))) return <ul key={i}>{lines.map((l, j) => <li key={j}>{inline(l.replace(/^\s*[-*] /, ""))}</li>)}</ul>;
        if (lines.every((l) => /^\s*\d+\. /.test(l))) return <ol key={i}>{lines.map((l, j) => <li key={j}>{inline(l.replace(/^\s*\d+\. /, ""))}</li>)}</ol>;
        if (lines.length > 1 && /^\s*[-*] /.test(lines[1])) {
          return <div key={i}><p>{inline(lines[0])}</p><ul>{lines.slice(1).map((l, j) => <li key={j}>{inline(l.replace(/^\s*[-*] /, ""))}</li>)}</ul></div>;
        }
        return <p key={i}>{lines.map((l, j) => <span key={j}>{inline(l)}{j < lines.length - 1 && <br />}</span>)}</p>;
      })}
    </div>
  );
}
function inline(s: string): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`|_[^_]+_)/g;
  let last = 0, m: RegExpExecArray | null, k = 0;
  while ((m = re.exec(s))) {
    if (m.index > last) out.push(s.slice(last, m.index));
    const t = m[0];
    if (t.startsWith("**")) out.push(<strong key={k++} className="font-semibold text-flo-950">{t.slice(2, -2)}</strong>);
    else if (t.startsWith("`")) out.push(<code key={k++}>{t.slice(1, -1)}</code>);
    else out.push(<em key={k++}>{t.slice(1, -1)}</em>);
    last = m.index + t.length;
  }
  if (last < s.length) out.push(s.slice(last));
  return out;
}

export function DiffView({ diff }: { diff: string }) {
  return (
    <pre aria-label="Code diff" className="max-h-80 overflow-auto rounded-xl border border-line bg-[#0B1F18] p-3 text-[12px] leading-5 scroll-thin">
      {diff.split("\n").map((l, i) => (
        <div key={i} className={l.startsWith("+") && !l.startsWith("+++") ? "bg-[#12402F] text-[#9BE7C2]" : l.startsWith("-") && !l.startsWith("---") ? "bg-[#4A1F1D] text-[#F2B8B5]" : l.startsWith("@@") ? "text-[#D9B868]" : "text-[#C9D9D1]"}>{l || " "}</div>
      ))}
    </pre>
  );
}
