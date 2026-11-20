import { FlaskConical, Info } from "lucide-react";
import { Badge, Card, CardHeader, Tip } from "@/components/common/ui";
import { useEvidence } from "@/components/evidence/EvidenceContext";
import { pct } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { Panel } from "@/types/api";

interface Hyp {
  rank: number; factor: string; description: string; role: string; role_label: string; with_factor: number; without_factor: number;
  negative_rate_with: number | null; negative_rate_without: number | null; ci_with_low: number; ci_with_high: number; ci_without_low: number; ci_without_high: number;
  risk_difference: number; relative_risk: number | null; p_value: number | null; strength: string; precedes_negative_share: number | null; precedence_checked: number;
  evidence: string[];
}

const STRENGTH_TONE: Record<string, "positive" | "warning" | "default" | "negative"> = {
  "strong association": "negative", "moderate association": "warning",
};

function RateBar({ value, lo, hi, tone, label }: { value: number | null; lo: number; hi: number; tone: string; label: string }) {
  if (value === null) return <span className="text-faint">n/a</span>;
  return (
    <div className="flex items-center gap-2" aria-label={`${label}: ${pct(value, 0)} (95% CI ${pct(lo, 0)}–${pct(hi, 0)})`}>
      <div className="relative h-2.5 flex-1 rounded-full bg-white/[0.05]">
        <div className={cn("absolute inset-y-0 left-0 rounded-full", tone)} style={{ width: `${value * 100}%` }} />
        <div className="absolute top-1/2 h-3.5 -translate-y-1/2 border-x border-ink/60" style={{ left: `${lo * 100}%`, width: `${Math.max(0.5, (hi - lo) * 100)}%` }} />
      </div>
      <span className="w-9 text-right font-mono text-[11px] text-ink">{pct(value, 0)}</span>
    </div>
  );
}

export function RootCausePanel({ panel }: { panel: Panel }) {
  const { openConversation } = useEvidence();
  const rows = (panel.series.all_factors?.rows ?? panel.table?.rows ?? []) as Hyp[];
  const drivers = rows.filter((h) => h.role !== "customer_reaction");
  const symptoms = rows.filter((h) => h.role === "customer_reaction");
  const alts = panel.series.alternatives?.rows ?? [];
  const m = Object.fromEntries(panel.metrics.map((x) => [x.id, x.value]));
  const section = (title: string, hint: string, list: Hyp[]) => (
    <div>
      <p className="label mb-1.5 flex items-center gap-1">{title}<Tip content={hint}><span><Info className="h-3 w-3 text-faint" /></span></Tip></p>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-xs">
          <thead><tr className="text-left text-[10px] uppercase tracking-wide text-faint">
            <th className="py-1.5 pr-3 font-medium">Factor</th><th className="w-40 pr-3 font-medium">Negative with</th><th className="w-40 pr-3 font-medium">Negative without</th>
            <th className="pr-3 font-medium">Evidence strength</th><th className="pr-3 font-medium">Precedes negativity</th><th className="font-medium">Examples</th></tr></thead>
          <tbody className="divide-y divide-line">
            {list.map((h) => (
              <tr key={h.factor} data-testid={`rc-factor-${h.factor}`}>
                <td className="py-2 pr-3"><p className="text-ink">{h.description}</p><p className="text-[10px] text-faint">n = {h.with_factor} with · {h.without_factor} without</p></td>
                <td className="pr-3"><RateBar value={h.negative_rate_with} lo={h.ci_with_low} hi={h.ci_with_high} tone="bg-neg/70" label="Negative rate with factor" /></td>
                <td className="pr-3"><RateBar value={h.negative_rate_without} lo={h.ci_without_low} hi={h.ci_without_high} tone="bg-neu/60" label="Negative rate without factor" /></td>
                <td className="pr-3"><Badge tone={STRENGTH_TONE[h.strength] ?? "default"}>{h.strength}</Badge>
                  <p className="mt-0.5 text-[10px] text-faint">{h.risk_difference >= 0 ? "+" : ""}{(h.risk_difference * 100).toFixed(0)} pts · p {h.p_value === null ? "n/a" : h.p_value < 0.001 ? "<0.001" : h.p_value.toFixed(3)}</p></td>
                <td className="pr-3 text-muted">{h.precedes_negative_share === null ? "—" : <Tip content={`Share of ${h.precedence_checked} negative conversations with this behaviour where it occurs before the customer's last negative message. Consistent with contributing; not proof.`}><span>{pct(h.precedes_negative_share, 0)}</span></Tip>}</td>
                <td><div className="flex flex-wrap gap-1">{h.evidence.slice(0, 3).map((id) => (
                  <button key={id} onClick={() => openConversation(id)} className="focus-ring rounded-md border border-line px-1.5 py-0.5 font-mono text-[10px] text-cyan hover:bg-white/5">{id}</button>))}</div></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
  return (
    <Card data-testid="root-cause-panel">
      <CardHeader icon={<FlaskConical className="h-4 w-4" />} title={`Root cause investigation · ${m.topic}`}
        subtitle={`${m.negative_conversations} of ${m.conversations} conversations negative (${pct(Number(m.negative_rate))}). ${m.factors_tested} factors tested — associations, not proof of cause.`} />
      <div className="space-y-5 p-4 pt-3">
        {section("Candidate drivers (agent behaviour and context)", "Things the support process controls or that describe the situation. Bars show the negative rate; whiskers are 95% Wilson intervals.", drivers)}
        {symptoms.length > 0 && section("Symptoms (customer reactions)", "Escalation and urgency are expressions of negativity, so a strong association here describes the outcome, not its cause.", symptoms)}
        <div>
          <p className="label mb-1.5">Alternative explanations checked</p>
          <ul className="grid gap-2 md:grid-cols-3">{alts.map((a: any) => (
            <li key={a.alternative} className="rounded-lg border border-line bg-white/[0.02] p-2.5 text-xs"><p className="font-medium text-ink">{a.alternative}</p>
              <p className="mt-1 text-muted">{a.finding}</p><p className="mt-1 text-[10px] text-faint">{a.test}{a.p_value !== null && a.p_value !== undefined ? ` · p ${a.p_value}` : ""}</p></li>))}</ul>
        </div>
        <ul className="space-y-1 text-[11px] text-muted">{panel.uncertainty_notes.map((n) => <li key={n}>• {n}</li>)}</ul>
      </div>
    </Card>
  );
}
