import { Bot, Copy, ExternalLink, User } from "lucide-react";
import { Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Link } from "react-router-dom";
import { useApp } from "@/app/AppState";
import { Badge, Button, ErrorState, SentimentBadge, Skeleton } from "@/components/common/ui";
import { useAsync } from "@/hooks/useAsync";
import { humanize, score } from "@/lib/format";
import { cn } from "@/lib/utils";
import { api } from "@/services/api";

interface ConversationPayload {
  conversation: Record<string, any>;
  messages: { message_id: string; turn_index: number; speaker_role: string; text: string; act: string; sentiment: string; sentiment_score: number;
    empathy: boolean; resolution: string | null; timestamp: string; source_reference: string; noise_token_count: number }[];
}

const SENT_DOT: Record<string, string> = { negative: "bg-neg", positive: "bg-pos", neutral: "bg-neu", mixed: "bg-mix" };

export function TranscriptViewer({ conversationId, highlight = [], compact = false }: { conversationId: string; highlight?: string[]; compact?: boolean }) {
  const { data, error, loading, reload } = useAsync(() => api.get<ConversationPayload>(`/api/conversations/${conversationId}`), [conversationId]);
  const { ask, setSelectedConversation } = useApp();
  if (loading) return <div className="space-y-3">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-14" />)}</div>;
  if (error || !data) return <ErrorState message={error?.message ?? "Not found"} onRetry={reload} />;
  const c = data.conversation;
  const cust = data.messages.filter((m) => m.speaker_role === "customer").map((m) => ({ turn: m.turn_index, score: m.sentiment_score, text: m.text }));
  const hl = new Set(highlight);
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-1.5">
        <Badge tone="indigo">{c.topic_label}</Badge>
        {c.product && <Badge>{c.product}</Badge>}
        <Badge>{c.domain}</Badge>
        <SentimentBadge value={c.sentiment} />
        <Badge tone="cyan">{c.agent_id}</Badge>
        <Badge>{String(c.start_timestamp).slice(0, 10)}</Badge>
        {c.dataset_source !== "original" && <Badge tone="warning">synthetic demo</Badge>}
      </div>
      <div className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
        {[["Messages", c.message_count], ["Escalation requests", c.escalation_requests], ["Closing action", humanize(c.final_resolution)],
          ["Action fits issue", c.resolution_relevant === null ? "n/a" : c.resolution_relevant ? "yes" : "no"]].map(([k, v]) => (
          <div key={k as string} className="rounded-lg border border-line bg-white/[0.02] p-2.5"><p className="label">{k}</p><p className="mt-1 text-ink">{v as any}</p></div>
        ))}
      </div>
      {!compact && cust.length > 1 && (
        <div className="rounded-xl border border-line bg-white/[0.02] p-3" aria-label="Customer sentiment by turn">
          <p className="label mb-2">Customer sentiment by turn</p>
          <ResponsiveContainer width="100%" height={110}>
            <LineChart data={cust} margin={{ top: 4, right: 8, left: -24, bottom: 0 }}>
              <XAxis dataKey="turn" tickLine={false} axisLine={false} />
              <YAxis domain={[-1, 1]} ticks={[-1, 0, 1]} tickLine={false} axisLine={false} />
              <ReferenceLine y={0} stroke="rgba(148,163,184,0.25)" />
              <Tooltip contentStyle={{ background: "#17233C", border: "1px solid rgba(148,163,184,0.2)", borderRadius: 10, fontSize: 12 }}
                formatter={(v: number) => score(v)} labelFormatter={(l) => `Turn ${l}`} />
              <Line type="monotone" dataKey="score" stroke="#22D3EE" strokeWidth={2} dot={{ r: 3 }} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
      <ol className="space-y-2.5">
        {data.messages.map((m) => {
          const isCust = m.speaker_role === "customer";
          return (
            <li key={m.message_id} id={m.message_id} className={cn("flex gap-2.5", isCust ? "" : "flex-row-reverse")}>
              <div className={cn("mt-1 grid h-7 w-7 shrink-0 place-items-center rounded-full", isCust ? "bg-indigo-soft text-indigo" : "bg-cyan-soft text-cyan")}>
                {isCust ? <User className="h-3.5 w-3.5" aria-label="Customer" /> : <Bot className="h-3.5 w-3.5" aria-label="Agent" />}
              </div>
              <div className={cn("max-w-[85%] rounded-2xl border px-3.5 py-2.5 text-sm",
                isCust ? "rounded-tl-sm border-line bg-white/[0.03]" : "rounded-tr-sm border-cyan/15 bg-cyan/[0.05]",
                hl.has(m.message_id) && "ring-2 ring-violet/70")}>
                <p className="leading-relaxed text-ink">{m.text}</p>
                <div className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-[10px] text-faint">
                  <span className="font-mono">T{String(m.turn_index).padStart(2, "0")}</span>
                  <span className="flex items-center gap-1"><span className={cn("h-1.5 w-1.5 rounded-full", SENT_DOT[m.sentiment] ?? "bg-neu")} />{m.sentiment} {isCust && score(m.sentiment_score)}</span>
                  <span>{humanize(m.act)}</span>
                  {m.empathy && <span className="text-pos">empathy</span>}
                  {m.noise_token_count > 0 && <span title="Random filler tokens present in the source text were removed">{m.noise_token_count} filler tokens removed</span>}
                  <span className="font-mono" title="Source file and line">{m.source_reference}</span>
                </div>
              </div>
            </li>
          );
        })}
      </ol>
      <div className="flex flex-wrap gap-2 border-t border-line pt-3">
        <Button size="sm" variant="primary" onClick={() => { setSelectedConversation(conversationId); ask(`How did customer sentiment change over the course of conversation ${conversationId}?`); }}>
          Analyse sentiment trajectory
        </Button>
        <Button size="sm" variant="outline" onClick={() => navigator.clipboard?.writeText(conversationId)}><Copy className="h-3.5 w-3.5" />Copy ID</Button>
        <Link to={`/explorer/${conversationId}`} className="focus-ring inline-flex h-8 items-center gap-1.5 rounded-xl px-3 text-xs text-muted hover:text-ink">
          <ExternalLink className="h-3.5 w-3.5" />Open in Explorer
        </Link>
      </div>
    </div>
  );
}
