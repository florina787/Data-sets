import { Waves } from "lucide-react";
import { useState } from "react";
import { Card, CardHeader, PageHeader } from "@/components/common/ui";
import { AskButton, Chart, DashboardShell, useDashboard, WindowSelect } from "@/components/dashboard/Dashboard";

export default function Sentiment() {
  const [win, setWin] = useState("last_month");
  const { data, loading, error, reload } = useDashboard("sentiment", win);
  const r = data?.results.rank_negative_topics;
  return (
    <DashboardShell loading={loading} error={error} reload={reload}
      header={<PageHeader title="Sentiment Intelligence" icon={<Waves className="h-5 w-5" />}
        subtitle="Which topics carry negative customer sentiment — by count and by rate, with confidence intervals."
        actions={<div className="flex gap-2"><WindowSelect value={win} onChange={setWin} /><AskButton question="What were the top 5 topics most associated with negative customer sentiment in the last month represented in the dataset?" /></div>} />}>
      {data && (
        <div className="space-y-5">
          <Chart d={data} id="_neg_kpis" />
          <div className="grid gap-4 xl:grid-cols-2">
            <Chart d={data} id="negative_topics" />
            <Chart d={data} id="negative_rate_ci" />
            <Chart d={data} id="sentiment_by_group" className="xl:col-span-2" />
            <Chart d={data} id="sentiment_distribution" />
            <Chart d={data} id="sentiment_trend" />
            <Chart d={data} id="topic_frequency" />
            <Card>
              <CardHeader title="How to read this" subtitle={data.scope.window.explanation} />
              <ul className="space-y-1.5 px-5 pb-5 pt-3 text-xs leading-relaxed text-muted">
                {[...(r?.method_notes ?? []), ...(r?.uncertainty_notes ?? [])].map((n) => <li key={n}>• {n}</li>)}
              </ul>
            </Card>
          </div>
        </div>
      )}
    </DashboardShell>
  );
}
