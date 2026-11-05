import { cva, type VariantProps } from "class-variance-authority";
import { clsx } from "clsx";
import { AlertTriangle, Loader2, ShieldAlert } from "lucide-react";
import { forwardRef, type ButtonHTMLAttributes, type HTMLAttributes, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes } from "react";
import { twMerge } from "tailwind-merge";
import { ApiError } from "@/lib/api";

export const cn = (...a: Parameters<typeof clsx>) => twMerge(clsx(...a));

const buttonV = cva(
  "inline-flex items-center justify-center gap-1.5 rounded-md text-sm font-medium transition-colors disabled:opacity-50 disabled:pointer-events-none",
  {
    variants: {
      variant: {
        primary: "bg-gold text-[#0B1220] hover:bg-gold/90",
        secondary: "bg-card border border-line text-ink hover:bg-line/40",
        ghost: "text-muted hover:text-ink hover:bg-line/40",
        danger: "bg-crit/90 text-white hover:bg-crit",
        blue: "bg-blue text-white hover:bg-blue/90",
      },
      size: { sm: "h-7 px-2 text-xs", md: "h-9 px-3", icon: "h-8 w-8" },
    },
    defaultVariants: { variant: "secondary", size: "md" },
  },
);
export const Button = forwardRef<HTMLButtonElement, ButtonHTMLAttributes<HTMLButtonElement> & VariantProps<typeof buttonV>>(
  ({ className, variant, size, ...p }, ref) => <button ref={ref} className={cn(buttonV({ variant, size }), className)} {...p} />,
);

export const Card = ({ className, ...p }: HTMLAttributes<HTMLDivElement>) => (
  <div className={cn("rounded-xl border border-line bg-card shadow-sm", className)} {...p} />
);

const badgeV = cva("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium border", {
  variants: {
    tone: {
      neutral: "border-line text-muted", gold: "border-gold/40 text-gold bg-gold/10", good: "border-pos/40 text-pos bg-pos/10",
      warn: "border-warn/40 text-warn bg-warn/10", crit: "border-crit/40 text-crit bg-crit/10", blue: "border-blue/40 text-blue bg-blue/10",
    },
  },
  defaultVariants: { tone: "neutral" },
});
export const Badge = ({ tone, className, ...p }: HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badgeV>) => (
  <span className={cn(badgeV({ tone }), className)} {...p} />
);

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(({ className, ...p }, ref) => (
  <input ref={ref} className={cn("h-9 w-full rounded-md border border-line bg-bg px-3 text-sm text-ink placeholder:text-muted", className)} {...p} />
));

export const Select = ({ className, ...p }: SelectHTMLAttributes<HTMLSelectElement>) => (
  <select className={cn("h-9 rounded-md border border-line bg-bg px-2 text-sm text-ink", className)} {...p} />
);

export const Label = ({ children, className }: { children: ReactNode; className?: string }) => (
  <label className={cn("text-xs font-medium text-muted", className)}>{children}</label>
);

export function Tabs<T extends string>({ tabs, value, onChange }: { tabs: { id: T; label: string }[]; value: T; onChange: (t: T) => void }) {
  return (
    <div role="tablist" className="flex flex-wrap gap-1 border-b border-line">
      {tabs.map((t) => (
        <button key={t.id} role="tab" aria-selected={value === t.id} onClick={() => onChange(t.id)}
          className={cn("px-3 py-2 text-sm -mb-px border-b-2", value === t.id ? "border-gold text-ink" : "border-transparent text-muted hover:text-ink")}>
          {t.label}
        </button>
      ))}
    </div>
  );
}

export const Spinner = ({ label = "Loading" }: { label?: string }) => (
  <div className="flex items-center gap-2 p-4 text-sm text-muted" role="status"><Loader2 className="h-4 w-4 animate-spin" />{label}…</div>
);

export function ErrorState({ error }: { error: unknown }) {
  const e = error as ApiError;
  const denied = e?.status === 403;
  return (
    <div className={cn("flex items-start gap-2 rounded-md border p-3 text-sm", denied ? "border-warn/40 bg-warn/10" : "border-crit/40 bg-crit/10")} role="alert">
      {denied ? <ShieldAlert className="h-4 w-4 text-warn mt-0.5" /> : <AlertTriangle className="h-4 w-4 text-crit mt-0.5" />}
      <div>
        <div className="font-medium">{denied ? "Access denied by policy" : "Request failed"}</div>
        <div className="text-muted">{e?.message}{e?.denials?.length ? ` — rules: ${e.denials.join(", ")}` : ""}</div>
      </div>
    </div>
  );
}

export function Stat({ label, value, sub, tone }: { label: string; value: ReactNode; sub?: ReactNode; tone?: "good" | "warn" | "crit" }) {
  return (
    <Card className="p-4">
      <div className="text-xs text-muted">{label}</div>
      <div className="mt-1 text-2xl font-semibold tracking-tight">{value}</div>
      {sub && <div className={cn("mt-1 text-xs", tone === "good" ? "text-pos" : tone === "crit" ? "text-crit" : tone === "warn" ? "text-warn" : "text-muted")}>{sub}</div>}
    </Card>
  );
}

export const PageHeader = ({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) => (
  <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
    <div>
      <h1 className="text-xl font-semibold">{title}</h1>
      {subtitle && <p className="text-sm text-muted">{subtitle}</p>}
    </div>
    {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
  </div>
);

export function Progress({ value, planned }: { value: number; planned?: number }) {
  return (
    <div className="relative h-2 w-full rounded bg-line/60" role="progressbar" aria-valuenow={value} aria-valuemin={0} aria-valuemax={100}>
      <div className={cn("h-2 rounded", planned != null && value < planned - 10 ? "bg-warn" : "bg-pos")} style={{ width: `${Math.min(100, value)}%` }} />
      {planned != null && <div className="absolute top-[-2px] h-3 w-0.5 bg-ink/70" style={{ left: `${Math.min(100, planned)}%` }} title={`planned ${planned}%`} />}
    </div>
  );
}
