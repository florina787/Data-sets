import { Clock3 } from "lucide-react";
import { Badge } from "@/components/ui";

export function DataFreshnessIndicator({ asOf, refreshedAt, synthetic, sources, compact = false }: {
  asOf?: string | null; refreshedAt?: string | null; synthetic?: boolean; sources?: string[]; compact?: boolean;
}) {
  if (!asOf && !refreshedAt) return null;
  const refreshed = refreshedAt ? new Date(refreshedAt.endsWith("Z") || refreshedAt.includes("+") ? refreshedAt : `${refreshedAt}Z`) : null;
  return (
    <span className="inline-flex flex-wrap items-center gap-1.5 text-[11px] text-muted" title={sources?.length ? `Sources: ${sources.join(", ")}` : undefined}>
      <Clock3 className="h-3 w-3" aria-hidden />
      {asOf && <span>Data as of <b className="font-medium text-ink/80">{asOf}</b></span>}
      {refreshed && !compact && <span>· computed {refreshed.toLocaleTimeString()}</span>}
      {synthetic && <Badge tone="gold">synthetic</Badge>}
    </span>
  );
}
