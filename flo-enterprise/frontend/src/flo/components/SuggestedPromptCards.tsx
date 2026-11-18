import { ArrowUpRight, Briefcase, Building2, Gauge, LineChart, Map, PieChart, Scale, ShieldAlert, TrendingUp, Users } from "lucide-react";

const ICONS = [Building2, TrendingUp, Users, ShieldAlert, PieChart, Briefcase, Scale, Gauge, LineChart, Map];

export function SuggestedPromptCards({ prompts, onPick, disabled }: { prompts: string[]; onPick: (p: string) => void; disabled?: boolean }) {
  return (
    <ul className="grid gap-2 sm:grid-cols-2 xl:grid-cols-5" aria-label="Suggested questions">
      {prompts.map((p, i) => {
        const Icon = ICONS[i % ICONS.length];
        return (
          <li key={p} className="flo-rise" style={{ animationDelay: `${60 + i * 35}ms` }}>
            <button disabled={disabled} onClick={() => onPick(p)} data-prompt={i}
              className="group flex h-full w-full items-start gap-2 rounded-xl border border-line bg-card/70 p-3 text-left text-[13px] transition-colors hover:border-gold/60 hover:bg-card disabled:opacity-50">
              <Icon className="mt-0.5 h-4 w-4 shrink-0 text-gold/80" aria-hidden />
              <span className="flex-1 leading-snug text-ink/90">{p}</span>
              <ArrowUpRight className="h-3.5 w-3.5 shrink-0 text-muted opacity-0 transition-opacity group-hover:opacity-100" aria-hidden />
            </button>
          </li>
        );
      })}
    </ul>
  );
}
