import { BrainCircuit, Calculator, Coins, Route } from "lucide-react";
import { Badge, Tip } from "@/components/common/ui";
import { humanize, num } from "@/lib/format";
import type { ChatResponse } from "@/types/api";

const MODE_LABEL: Record<string, string> = { auto: "Auto", analytics_only: "Analytics only", hybrid_ai: "Hybrid AI" };
const METHOD_LABEL: Record<string, string> = {
  policy: "policy rule", rules: "high-precision rule", rules_weak: "broad keyword rule", semantic: "semantic match", llm: "model", clarify: "clarification",
};

/** Tokens: "—" (none used), a number, or "not reported" — never a zero standing in for missing metadata. */
export function tokenText(total: number | null | undefined, modelCalls: number | undefined): string {
  if (!modelCalls) return "0 (no model call)";
  if (total === null || total === undefined) return "not reported";
  return num(total);
}

export function RoutingStrip({ r }: { r: ChatResponse }) {
  const rt = r.routing;
  const tu = r.token_usage;
  const ir = r.model_metadata?.intent_routing as { method?: string; reason?: string; rule?: string } | undefined;
  if (!rt) return null;
  const zero = rt.route === "analytics_only";
  return (
    <div data-testid="routing-strip" className="flex flex-wrap items-start gap-x-4 gap-y-2 rounded-xl border border-line bg-white/[0.02] px-3.5 py-2.5 text-[11px]">
      <div className="flex min-w-0 flex-1 items-start gap-2">
        {zero ? <Calculator className="mt-0.5 h-3.5 w-3.5 shrink-0 text-pos" aria-hidden /> : <BrainCircuit className="mt-0.5 h-3.5 w-3.5 shrink-0 text-violet" aria-hidden />}
        <div className="min-w-0">
          <p className="text-ink">
            <span className="font-semibold">{zero ? "Zero-LLM route" : "Hybrid AI route"}</span>
            <span className="text-faint"> · mode {MODE_LABEL[rt.requested_mode] ?? rt.requested_mode}</span>
          </p>
          <p className="mt-0.5 leading-relaxed text-muted">{rt.reason}</p>
        </div>
      </div>
      {ir?.method && (
        <Tip content={ir.reason ?? ""}>
          <span className="flex items-center gap-1.5"><Route className="h-3.5 w-3.5 text-cyan" aria-hidden />
            <span className="text-muted">Intent via <span className="text-ink">{METHOD_LABEL[ir.method] ?? humanize(ir.method)}</span></span></span>
        </Tip>
      )}
      {tu && (
        <Tip content={tu.model_calls ? `${tu.model_calls} model call(s), ${tu.cache_hits} cached. ${tu.complete ? "" : `${tu.unreported_calls} call(s) returned no usage metadata, so the total is incomplete.`} Estimated cost: ${tu.estimated_cost_usd === null ? "not available" : `$${tu.estimated_cost_usd.toFixed(5)}`}.` : "No model was called for this answer."}>
          <span className="flex items-center gap-1.5" data-testid="token-usage"><Coins className="h-3.5 w-3.5 text-mix" aria-hidden />
            <span className="text-muted">Tokens <span className="text-ink">{tokenText(tu.total_tokens, tu.model_calls)}</span>
              {tu.model_calls > 0 && <span className="text-faint"> · {tu.model_calls} call{tu.model_calls > 1 ? "s" : ""}</span>}
              {!tu.complete && tu.model_calls > 0 && <Badge tone="warning" className="ml-1">incomplete</Badge>}</span></span>
        </Tip>
      )}
    </div>
  );
}
