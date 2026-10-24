// shadcn/ui-style primitives (cva + tailwind-merge), restricted to the VEENA palette.
import { cva, type VariantProps } from "class-variance-authority";
import { clsx, type ClassValue } from "clsx";
import { forwardRef, type ButtonHTMLAttributes, type HTMLAttributes, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from "react";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const button = cva(
  "inline-flex items-center justify-center gap-2 rounded-xl font-medium transition-colors disabled:pointer-events-none disabled:opacity-50 select-none whitespace-nowrap",
  {
    variants: {
      variant: {
        primary: "bg-caramel text-white hover:bg-mocha active:bg-bark shadow-[var(--shadow-soft)]",
        secondary: "bg-white text-bark border border-cream hover:bg-ivory hover:border-sand",
        ghost: "text-mocha hover:bg-ivory hover:text-bark",
        subtle: "bg-ivory text-bark hover:bg-cream",
        danger: "bg-white text-bark border border-mocha hover:bg-bark hover:text-white",
      },
      size: {
        sm: "h-8 px-3 text-sm",
        md: "h-10 px-4 text-sm",
        lg: "h-12 px-6 text-base",
        icon: "h-9 w-9",
      },
    },
    defaultVariants: { variant: "secondary", size: "md" },
  },
);

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof button> {}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(({ className, variant, size, type = "button", ...props }, ref) => (
  <button ref={ref} type={type} className={cn(button({ variant, size }), className)} {...props} />
));
Button.displayName = "Button";

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("rounded-[var(--radius-card)] border border-cream bg-white shadow-[var(--shadow-soft)]", className)} {...props} />;
}

export function CardHeader({ title, subtitle, actions, className }: { title: ReactNode; subtitle?: ReactNode; actions?: ReactNode; className?: string }) {
  return (
    <div className={cn("flex items-start justify-between gap-4 px-5 pt-5", className)}>
      <div>
        <h3 className="text-[15px] font-semibold text-espresso">{title}</h3>
        {subtitle && <p className="mt-0.5 text-sm text-caramel">{subtitle}</p>}
      </div>
      {actions}
    </div>
  );
}

const badge = cva("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium", {
  variants: {
    tone: {
      neutral: "bg-ivory text-mocha border border-cream",
      strong: "bg-bark text-white",
      accent: "bg-cream text-bark",
      outline: "border border-sand text-mocha",
    },
  },
  defaultVariants: { tone: "neutral" },
});

export function Badge({ className, tone, ...props }: HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badge>) {
  return <span className={cn(badge({ tone }), className)} {...props} />;
}

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(({ className, ...props }, ref) => (
  <input
    ref={ref}
    className={cn(
      "h-10 w-full rounded-xl border border-cream bg-white px-3 text-sm text-bark placeholder:text-sand focus:border-ginger focus:outline-none",
      className,
    )}
    {...props}
  />
));
Input.displayName = "Input";

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(({ className, ...props }, ref) => (
  <textarea
    ref={ref}
    className={cn(
      "w-full resize-none rounded-xl border border-cream bg-white px-3 py-2.5 text-sm text-bark placeholder:text-sand focus:border-ginger focus:outline-none",
      className,
    )}
    {...props}
  />
));
Textarea.displayName = "Textarea";

export function Select({ className, children, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      className={cn("h-10 w-full rounded-xl border border-cream bg-white px-3 text-sm text-bark focus:border-ginger focus:outline-none", className)}
      {...props}
    >
      {children}
    </select>
  );
}

export function Switch({ checked, onChange, label, description, disabled }: { checked: boolean; onChange: (v: boolean) => void; label: string; description?: string; disabled?: boolean }) {
  return (
    <label className={cn("flex w-full items-start justify-between gap-4", disabled && "opacity-50")}>
      <span className="min-w-0">
        <span className="block text-sm font-medium text-bark">{label}</span>
        {description && <span className="mt-0.5 block text-xs text-caramel">{description}</span>}
      </span>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={label}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={cn("relative mt-0.5 h-6 w-11 shrink-0 rounded-full transition-colors", checked ? "bg-caramel" : "bg-cream")}
      >
        <span className={cn("absolute top-0.5 left-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform", checked ? "translate-x-5" : "translate-x-0")} />
      </button>
    </label>
  );
}

/** Status indicator using brown shades and shapes instead of traffic-light colours. */
export function StatusDot({ state, label }: { state: "ok" | "busy" | "off" | "problem"; label?: string }) {
  const shape = {
    ok: "h-2.5 w-2.5 rounded-full bg-caramel",
    busy: "h-2.5 w-2.5 rounded-full border-2 border-ginger border-t-transparent animate-spin",
    off: "h-2.5 w-2.5 rounded-full border-2 border-sand",
    problem: "h-2.5 w-2.5 rotate-45 bg-espresso",
  }[state];
  return (
    <span className="inline-flex shrink-0 items-center gap-1.5 text-xs whitespace-nowrap text-mocha">
      <span className={cn(shape, "shrink-0")} aria-hidden />
      {label && <span>{label}</span>}
    </span>
  );
}

export function Section({ title, children, className }: { title: string; children: ReactNode; className?: string }) {
  return (
    <section className={className}>
      <h4 className="mb-2 text-[11px] font-semibold uppercase tracking-[0.08em] text-caramel">{title}</h4>
      {children}
    </section>
  );
}

export function Kbd({ children }: { children: ReactNode }) {
  return <kbd className="rounded-md border border-cream bg-ivory px-1.5 py-0.5 font-mono text-[11px] text-mocha">{children}</kbd>;
}
