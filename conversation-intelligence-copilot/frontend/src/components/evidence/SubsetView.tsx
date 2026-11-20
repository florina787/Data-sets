import { ChevronRight } from "lucide-react";
import { useApp } from "@/app/AppState";
import { EmptyState, ErrorState, SentimentBadge, Skeleton, Stat } from "@/components/common/ui";
import { useAsync } from "@/hooks/useAsync";
import { humanize, num } from "@/lib/format";
import { api } from "@/services/api";
import type { SubsetQuery } from "./EvidenceContext";

export function SubsetView({ query, onOpen }: { query: SubsetQuery; onOpen: (id: string) => void }) {
  const { datasetMode } = useApp();
  const { data, error, loading, reload } = useAsync(
    () => api.analytics("list_conversations", { params: { limit: 50 }, topics: query.topics, products: query.products, sentiments: query.sentiments,
      window: query.window ?? null, dataset_mode: datasetMode }),
    [JSON.stringify(query), datasetMode],
  );
  if (loading) return <div className="space-y-2">{Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-12" />)}</div>;
  if (error || !data) return <ErrorState message={error?.message ?? "Failed"} onRetry={reload} />;
  const total = data.metrics.find((m) => m.id === "conversations_in_scope")?.value as number;
  const neg = data.metrics.find((m) => m.id === "negative_in_scope")?.value as number;
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-2">
        <Stat label="Conversations" value={num(total)} hint={data.scope.window.label} />
        <Stat label="Negative" value={num(neg)} tone="negative" />
        <Stat label="Shown" value={num(data.table?.rows.length ?? 0)} hint="most negative first" />
      </div>
      {!data.table?.rows.length ? <EmptyState title="No conversations match" /> : (
        <ul className="divide-y divide-line rounded-xl border border-line">
          {data.table.rows.map((r) => (
            <li key={r.conversation_id}>
              <button onClick={() => onOpen(r.conversation_id)} className="focus-ring flex w-full items-center gap-3 px-3 py-2.5 text-left text-sm hover:bg-white/[0.03]">
                <span className="font-mono text-xs text-cyan">{r.conversation_id}</span>
                <span className="min-w-0 flex-1 truncate text-muted">{r.topic_label} · {r.product ?? "—"} · {r.agent_id}</span>
                <span className="hidden text-xs text-faint sm:inline">{humanize(r.final_resolution)}</span>
                <SentimentBadge value={r.sentiment} />
                <ChevronRight className="h-4 w-4 text-faint" aria-hidden />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
