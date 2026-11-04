import { Info } from "lucide-react";
import { cn } from "@/components/ui";
import type { Persona } from "../types";

export function PersonaSelector({ personas, value, onChange, note, compact = false }: {
  personas: Persona[]; value: string; onChange: (id: string) => void; note?: string; compact?: boolean;
}) {
  return (
    <div className="space-y-2">
      <div role="radiogroup" aria-label="Persona" className={cn("flex gap-1.5", compact ? "overflow-x-auto scroll-thin pb-1" : "flex-wrap justify-center")}>
        {personas.map((p) => (
          <button key={p.id} role="radio" aria-checked={value === p.id} onClick={() => onChange(p.id)} title={p.description}
            className={cn("whitespace-nowrap rounded-full border px-3 py-1 text-xs transition-colors",
              value === p.id ? "border-gold bg-gold/10 text-gold" : "border-line text-muted hover:border-gold/50 hover:text-ink")}>
            {compact ? p.short : p.label}
            {p.aligned_with_identity && <><span className="ml-1 text-[10px] text-pos" aria-hidden>●</span><span className="sr-only"> (matches your sign-in)</span></>}
          </button>
        ))}
      </div>
      {note && !compact && (
        <p className="flex items-center justify-center gap-1 text-[11px] text-muted"><Info className="h-3 w-3" />{note}</p>
      )}
    </div>
  );
}
