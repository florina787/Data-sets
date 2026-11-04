import { Flag, ShieldCheck } from "lucide-react";
import type { MessageResponse } from "../types";

export function ImplementationRoadmap({ plan }: { plan: NonNullable<MessageResponse["implementation_plan"]> }) {
  return (
    <section aria-label="Implementation roadmap" className="space-y-2">
      <h3 className="text-sm font-semibold">{plan.title}</h3>
      <ol className="grid gap-3 lg:grid-cols-3">
        {plan.phases.map((p, i) => (
          <li key={p.window} className="flo-rise relative rounded-xl border border-line bg-card p-3.5" style={{ animationDelay: `${i * 80}ms` }}>
            <div className="mb-2 flex items-center gap-2">
              <span className="grid h-6 w-6 place-items-center rounded-full bg-gold/15 text-xs font-semibold text-gold">{i + 1}</span>
              <div><div className="text-sm font-medium">{p.name}</div><div className="text-[11px] text-muted">{p.window}</div></div>
            </div>
            <div className="space-y-2 text-xs">
              <div><div className="font-semibold">Actions</div><ul className="list-disc pl-4">{p.actions.map((a) => <li key={a}>{a}</li>)}</ul></div>
              {p.milestones.length > 0 && <div><div className="flex items-center gap-1 font-semibold"><Flag className="h-3 w-3" />Milestones</div>
                <ul className="list-disc pl-4 text-muted">{p.milestones.map((m) => <li key={m}>{m}</li>)}</ul></div>}
              {p.kpis.length > 0 && <div className="text-muted"><span className="font-semibold text-ink">KPIs: </span>{p.kpis.join(", ")}</div>}
              {p.governance_gates.length > 0 && <div className="flex items-start gap-1 text-warn"><ShieldCheck className="mt-0.5 h-3 w-3 shrink-0" />{p.governance_gates.join(" · ")}</div>}
            </div>
          </li>
        ))}
      </ol>
      <p className="text-[11px] text-muted">{plan.basis}</p>
    </section>
  );
}
