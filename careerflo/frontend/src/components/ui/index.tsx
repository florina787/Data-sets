import { cva, type VariantProps } from "class-variance-authority";
import { forwardRef, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode, type TextareaHTMLAttributes } from "react";
import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

const button = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-full text-sm font-medium transition active:scale-[.98] disabled:opacity-50 disabled:pointer-events-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet/50",
  {
    variants: {
      variant: {
        primary: "bg-ink text-white hover:bg-ink/90 dark:bg-white dark:text-ink",
        violet: "bg-violet text-white hover:bg-violet/90",
        outline: "bg-white ring-1 ring-black/10 hover:bg-slate-50 dark:bg-white/5 dark:ring-white/15 dark:hover:bg-white/10",
        ghost: "hover:bg-black/[.04] dark:hover:bg-white/10",
      },
      size: { sm: "h-8 px-3 text-[13px]", md: "h-10 px-4", lg: "h-12 px-6 text-[15px]", icon: "h-9 w-9" },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
);

type BtnProps = ButtonHTMLAttributes<HTMLButtonElement> & VariantProps<typeof button> & { loading?: boolean };
export const Button = forwardRef<HTMLButtonElement, BtnProps>(({ className, variant, size, loading, children, ...p }, ref) => (
  <button ref={ref} className={cn(button({ variant, size }), className)} disabled={loading || p.disabled} {...p}>
    {loading && <Loader2 className="h-4 w-4 animate-spin" aria-hidden />}
    {children}
  </button>
));

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(({ className, ...p }, ref) => (
  <input ref={ref} className={cn("h-10 w-full rounded-full bg-white px-4 text-sm ring-1 ring-black/10 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-violet/40 dark:bg-white/5 dark:ring-white/15", className)} {...p} />
));

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(({ className, ...p }, ref) => (
  <textarea ref={ref} className={cn("w-full rounded-2xl bg-white p-4 text-sm ring-1 ring-black/10 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-violet/40 dark:bg-white/5 dark:ring-white/15", className)} {...p} />
));

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={cn("card p-6", className)}>{children}</div>;
}

const pill = cva("inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11.5px] font-medium", {
  variants: {
    tone: {
      neutral: "bg-slate-100 text-slate-600 dark:bg-white/10 dark:text-slate-300",
      violet: "bg-violet/10 text-violet", sky: "bg-sky/15 text-sky-700 dark:text-sky",
      emerald: "bg-emerald/10 text-emerald-700 dark:text-emerald", amber: "bg-amber/15 text-amber-700", coral: "bg-coral/15 text-red-700",
    },
  },
  defaultVariants: { tone: "neutral" },
});
export function Pill({ tone, className, children }: VariantProps<typeof pill> & { className?: string; children: ReactNode }) {
  return <span className={cn(pill({ tone }), className)}>{children}</span>;
}

export function Chip({ active, onClick, children, icon }: { active?: boolean; onClick?: () => void; children: ReactNode; icon?: ReactNode }) {
  return (
    <button onClick={onClick} className={cn("inline-flex h-8 items-center gap-1.5 rounded-full px-3 text-[12.5px] ring-1 transition",
      active ? "bg-sky/15 text-sky-700 ring-sky/50 dark:text-sky" : "bg-white text-slate-600 ring-black/10 hover:ring-black/20 dark:bg-white/5 dark:text-slate-300 dark:ring-white/15")}>
      {icon}{children}
    </button>
  );
}

export function Label({ children }: { children: ReactNode }) {
  return <label className="mb-1.5 block text-[12.5px] font-medium text-slate-600 dark:text-slate-300">{children}</label>;
}

export function Empty({ art, title, body, action }: { art?: ReactNode; title: string; body?: string; action?: ReactNode }) {
  return (
    <div className="mx-auto flex max-w-sm flex-col items-center py-16 text-center">
      {art}
      <h3 className="mt-6 text-[15px] font-semibold">{title}</h3>
      {body && <p className="muted mt-1.5 text-sm">{body}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function ErrorNote({ error }: { error: unknown }) {
  if (!error) return null;
  const msg = error instanceof Error ? error.message : String(error);
  return <p role="alert" className="rounded-2xl bg-coral/10 px-4 py-3 text-sm text-red-700 dark:text-red-300">{msg}</p>;
}
