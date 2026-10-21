import type { ButtonHTMLAttributes, ReactNode } from "react";
import { AlertTriangle, Info, Loader2 } from "lucide-react";

export function Card({ children, className = "", title, subtitle, actions, id }: { children: ReactNode; className?: string; title?: ReactNode; subtitle?: ReactNode; actions?: ReactNode; id?: string }) {
  return (
    <section id={id} className={`rounded-[10px] border border-line bg-card shadow-[0_1px_2px_rgba(23,43,77,0.06)] ${className}`}>
      {(title || actions) && (
        <header className="flex flex-wrap items-start justify-between gap-2 border-b border-line px-5 py-3">
          <div className="min-w-0">
            {title && <h2 className="text-[15px] font-semibold text-ink">{title}</h2>}
            {subtitle && <p className="text-xs text-muted">{subtitle}</p>}
          </div>
          {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className="p-5">{children}</div>
    </section>
  );
}

type BtnProps = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "ghost" | "danger"; size?: "sm" | "md" };
export function Button({ variant = "secondary", size = "md", className = "", ...p }: BtnProps) {
  const base = "inline-flex items-center gap-1.5 rounded-md font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50";
  const sz = size === "sm" ? "px-2.5 py-1 text-xs" : "px-3.5 py-1.5 text-sm";
  const v = {
    primary: "bg-teal text-white hover:bg-[#066b76]",
    secondary: "border border-line bg-white text-ink hover:bg-app",
    ghost: "text-teal hover:bg-teal-light",
    danger: "border border-red text-red bg-white hover:bg-red-light",
  }[variant];
  return <button type="button" className={`${base} ${sz} ${v} ${className}`} {...p} />;
}

export function Badge({ children, tone = "neutral", title }: { children: ReactNode; tone?: "neutral" | "teal" | "amber" | "red" | "green" | "dark"; title?: string }) {
  const t = {
    neutral: "bg-app text-muted border-line",
    teal: "bg-teal-light text-teal border-[#bfe0e2]",
    amber: "bg-amber-light text-amber border-[#ecd3ad]",
    red: "bg-red-light text-red border-[#e8c3c6]",
    green: "bg-green-light text-green border-[#bfdcc9]",
    dark: "bg-sidebar text-white border-sidebar",
  }[tone];
  return <span title={title} className={`inline-flex items-center gap-1 whitespace-nowrap rounded border px-1.5 py-0.5 text-[11px] font-medium ${t}`}>{children}</span>;
}

export function Stat({ label, value, sub, tone }: { label: string; value: ReactNode; sub?: ReactNode; tone?: "red" | "green" | "amber" }) {
  const c = tone === "red" ? "text-red" : tone === "green" ? "text-green" : tone === "amber" ? "text-amber" : "text-ink";
  return (
    <div className="rounded-[10px] border border-line bg-card px-4 py-3">
      <div className="text-xs font-medium text-muted">{label}</div>
      <div className={`tnum mt-1 text-2xl font-semibold ${c}`}>{value}</div>
      {sub && <div className="tnum mt-0.5 text-xs text-muted">{sub}</div>}
    </div>
  );
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-md border border-dashed border-line bg-app/50 px-6 py-8 text-center">
      <Info className="mb-2 h-5 w-5 text-muted" aria-hidden />
      <div className="text-sm font-medium text-ink">{title}</div>
      {children && <div className="mt-1 max-w-md text-xs text-muted">{children}</div>}
    </div>
  );
}

export function ErrorBox({ children, onRetry }: { children: ReactNode; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex items-start gap-2 rounded-md border border-[#e8c3c6] bg-red-light px-3 py-2 text-sm text-red">
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
      <div className="flex-1">{children}</div>
      {onRetry && <Button size="sm" variant="danger" onClick={onRetry}>Retry</Button>}
    </div>
  );
}

export function Notice({ children, tone = "amber" }: { children: ReactNode; tone?: "amber" | "teal" | "neutral" }) {
  const t = tone === "amber" ? "border-[#ecd3ad] bg-amber-light text-[#7a4805]" : tone === "teal" ? "border-[#bfe0e2] bg-teal-light text-[#05555e]" : "border-line bg-app text-muted";
  return (
    <div className={`flex items-start gap-2 rounded-md border px-3 py-2 text-xs ${t}`}>
      <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
      <div>{children}</div>
    </div>
  );
}

export function Spinner({ label = "Loading" }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-sm text-muted" role="status">
      <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> {label}
    </div>
  );
}

export function Monogram({ size = 28 }: { size?: number }) {
  return (
    <span aria-hidden className="inline-flex shrink-0 items-center justify-center rounded-full bg-teal font-semibold text-white" style={{ width: size, height: size, fontSize: size * 0.45 }}>F</span>
  );
}

export function PageHeader({ title, description, actions }: { title: string; description?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-xl font-semibold text-ink">{title}</h1>
        {description && <p className="mt-0.5 max-w-3xl text-sm text-muted">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return (
    <label className="flex flex-col gap-1 text-xs font-medium text-muted">
      {label}
      {children}
      {hint && <span className="font-normal">{hint}</span>}
    </label>
  );
}

export const inputCls = "rounded-md border border-line bg-white px-2.5 py-1.5 text-sm text-ink placeholder:text-[#8a94a3]";

export function Table({ head, rows, caption, compact = true }: { head: ReactNode[]; rows: ReactNode[][]; caption?: string; compact?: boolean }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-sm">
        {caption && <caption className="sr-only">{caption}</caption>}
        <thead>
          <tr className="border-b border-line text-left text-xs text-muted">
            {head.map((h, i) => <th key={i} scope="col" className={`whitespace-nowrap font-medium ${compact ? "px-2 py-1.5" : "px-3 py-2"}`}>{h}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-b border-line/70 last:border-0 hover:bg-app/60">
              {r.map((c, j) => <td key={j} className={`tnum align-top ${compact ? "px-2 py-1.5" : "px-3 py-2"}`}>{c}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Swatch({ color, pattern }: { color: string; pattern?: boolean }) {
  return <span aria-hidden className="inline-block h-2.5 w-2.5 shrink-0 rounded-sm" style={{ background: pattern ? `repeating-linear-gradient(45deg, ${color}, ${color} 2px, #fff 2px, #fff 4px)` : color }} />;
}
