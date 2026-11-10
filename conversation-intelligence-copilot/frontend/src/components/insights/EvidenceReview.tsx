import { CheckCircle2, CircleSlash, Gavel, TriangleAlert } from "lucide-react";
import { Badge, Card, CardHeader } from "@/components/common/ui";
import { humanize } from "@/lib/format";
import type { EvidenceReview as Review } from "@/types/api";

const VERDICT_TONE = { supported: "positive", "partially supported": "warning", challenged: "negative" } as const;
const ICON = { pass: <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-pos" />, warn: <TriangleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0 text-warn" />,
  fail: <CircleSlash className="mt-0.5 h-3.5 w-3.5 shrink-0 text-neg" /> };
const NAMES: Record<string, string> = {
  excerpt_fidelity: "Quotes match source", evidence_coverage: "Claims have examples", evidence_relevance: "Examples fit the claim",
  sample_size: "Sample sizes disclosed", counter_evidence: "Counter-evidence", causal_language: "No unqualified causal claims", claim_consistency: "Named drivers are supported",
};

/** The Analytical Evidence Challenger's verdict: it argues against the answer before it is shown. */
export function EvidenceReview({ review }: { review: Review }) {
  return (
    <Card data-testid="evidence-review">
      <CardHeader icon={<Gavel className="h-4 w-4" />} title="Evidence review"
        subtitle="An adversarial check of this answer: quotes re-read from the database, coverage, sample sizes, counter-evidence and causal wording."
        actions={<Badge tone={VERDICT_TONE[review.verdict]}>{review.verdict} · {review.passed}/{review.total}</Badge>} />
      <div className="grid gap-4 p-4 pt-3 md:grid-cols-2">
        <ul className="space-y-1.5 text-xs">
          {review.checks.map((c, i) => (
            <li key={`${c.check}-${i}`} className="flex gap-2">{ICON[c.status]}
              <span><span className="text-ink">{NAMES[c.check] ?? humanize(c.check)}</span> <span className="text-faint">— {c.detail}</span></span></li>
          ))}
        </ul>
        <div className="space-y-3 text-xs">
          {review.counter_evidence.length > 0 && (
            <div><p className="label mb-1">What does not fit the claim</p>
              <ul className="space-y-1 text-muted">{review.counter_evidence.map((x) => <li key={x}>• {x}</li>)}</ul></div>
          )}
          {review.challenges.length > 0 && (
            <div><p className="label mb-1">Challenges raised</p>
              <ul className="space-y-1 text-ink/85">{review.challenges.map((x) => <li key={x}>• {x}</li>)}</ul></div>
          )}
          {review.replaced_explanation && <p className="rounded-lg border border-neg/30 bg-neg/[0.06] p-2 text-ink/90">The model's explanation named unsupported drivers and was replaced by the deterministic narrative.</p>}
        </div>
      </div>
    </Card>
  );
}
