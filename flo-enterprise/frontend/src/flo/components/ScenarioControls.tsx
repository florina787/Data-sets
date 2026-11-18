import { Play } from "lucide-react";
import { useState } from "react";
import { Button, cn } from "@/components/ui";
import type { MessageContext } from "../types";

const PRESETS = [["base", "Base"], ["bull", "Bull"], ["bear", "Bear"], ["severe_stress", "Severe stress"]] as const;

/** Scenario inputs travel as structured context; the scenario agent and engine compute every number. */
export function ScenarioControls({ initial, onRun, disabled }: { initial?: { preset?: string; equity_shock?: number; rate_shock_bps?: number };
  onRun: (q: string, c: MessageContext) => void; disabled?: boolean }) {
  const [preset, setPreset] = useState(initial?.preset ?? "bear");
  const [eq, setEq] = useState(Math.round((initial?.equity_shock ?? -0.2) * 100));
  const [rate, setRate] = useState(initial?.rate_shock_bps ?? 0);
  return (
    <section aria-label="Scenario controls" className="rounded-xl border border-line bg-card p-3.5">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <h3 className="text-sm font-semibold">Scenario simulation</h3>
        <div role="radiogroup" aria-label="Scenario preset" className="ml-auto flex flex-wrap gap-1">
          {PRESETS.map(([id, label]) => (
            <button key={id} role="radio" aria-checked={preset === id} onClick={() => setPreset(id)}
              className={cn("rounded-full border px-2.5 py-0.5 text-xs", preset === id ? "border-gold text-gold" : "border-line text-muted hover:text-ink")}>{label}</button>
          ))}
        </div>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="text-xs text-muted">Equity shock: <b className="tabular-nums text-ink">{eq}%</b>
          <input type="range" min={-40} max={20} step={1} value={eq} onChange={(e) => setEq(Number(e.target.value))} className="mt-1 w-full accent-[#D4AF37]" /></label>
        <label className="text-xs text-muted">Rate shock: <b className="tabular-nums text-ink">{rate > 0 ? "+" : ""}{rate} bps</b>
          <input type="range" min={-200} max={300} step={25} value={rate} onChange={(e) => setRate(Number(e.target.value))} className="mt-1 w-full accent-[#D4AF37]" /></label>
      </div>
      <div className="mt-2 flex items-center gap-2">
        <p className="text-[11px] text-muted">Outputs are deterministic and conditional on these assumptions; they are not forecasts.</p>
        <Button size="sm" variant="primary" className="ml-auto" disabled={disabled}
          onClick={() => onRun(`Run the ${preset.replace("_", " ")} scenario with equity ${eq}% and rates ${rate >= 0 ? "+" : ""}${rate} bps.`,
            { intent: "scenario", scenario: { preset, equity_shock: eq / 100, rate_shock_bps: rate } })}>
          <Play className="h-3.5 w-3.5" />Run scenario</Button>
      </div>
    </section>
  );
}
