import { AlertOctagon, Bot, ScanSearch, User } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Badge, Card, CardHeader } from "@/components/common/ui";
import { humanize, score } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { Panel } from "@/types/api";

interface Msg {
  message_id: string; turn_index: number; speaker_role: "customer" | "agent"; phase: string; act: string; sentiment: string;
  sentiment_score: number | null; empathy: boolean; resolution: string | null; text: string; signals: string[];
}
interface Signal { kind: string; category: string; severity: "high" | "medium" | "low"; title: string; detail: string; message_ids: string[]; turns: number[] }

const SEV_TONE = { high: "negative", medium: "warning", low: "default" } as const;
const CAT_LABEL: Record<string, string> = { escalation: "Escalation signals", repeated_concern: "Repeated concerns", communication_gap: "Communication gaps", outcome: "Outcome" };
const SENT_BG: Record<string, string> = { negative: "bg-neg/70", positive: "bg-pos/70", neutral: "bg-neu/50", mixed: "bg-mix/70" };

/** Conversation X-Ray: timeline, findings and transcript share one selection (message_id), in both directions. */
export function XRayPanel({ panel }: { panel: Panel }) {
  const msgs = (panel.table?.rows ?? []) as Msg[];
  const signals = (panel.series.signals?.rows ?? []) as Signal[];
  const [activeMsg, setActiveMsg] = useState<string | null>(null);
  const [activeSig, setActiveSig] = useState<number | null>(null);
  const refs = useRef<Record<string, HTMLLIElement | null>>({});
  const scrollBox = useRef<HTMLOListElement>(null);
  const highlighted = useMemo(() => new Set(activeSig !== null ? signals[activeSig]?.message_ids ?? [] : activeMsg ? [activeMsg] : []), [activeSig, activeMsg, signals]);
  const sigForMsg = (id: string) => signals.map((s, i) => (s.message_ids.includes(id) ? i : -1)).filter((i) => i >= 0);

  const focusMessage = (id: string) => {
    setActiveMsg(id);
    setActiveSig(null);
    const el = refs.current[id];
    if (el && scrollBox.current) scrollBox.current.scrollTo({ top: el.offsetTop - scrollBox.current.offsetTop - 12, behavior: "smooth" });
  };
  const focusSignal = (i: number) => {
    setActiveSig(i);
    setActiveMsg(null);
    const first = signals[i]?.message_ids[0];
    const el = first ? refs.current[first] : null;
    if (el && scrollBox.current) scrollBox.current.scrollTo({ top: el.offsetTop - scrollBox.current.offsetTop - 12, behavior: "smooth" });
  };
  useEffect(() => { setActiveMsg(null); setActiveSig(null); }, [panel.params.conversation_id]);

  const cust = msgs.filter((m) => m.speaker_role === "customer" && m.sentiment_score !== null).map((m) => ({ turn: m.turn_index, score: m.sentiment_score, id: m.message_id }));
  const activeTurns = msgs.filter((m) => highlighted.has(m.message_id)).map((m) => m.turn_index);
  const grouped = Object.entries(signals.reduce<Record<string, number[]>>((a, s, i) => ((a[s.category] ??= []).push(i), a), {}));
  const m = Object.fromEntries(panel.metrics.map((x) => [x.id, x.value]));

  return (
    <Card data-testid="xray-panel">
      <CardHeader icon={<ScanSearch className="h-4 w-4" />} title={`Conversation X-Ray · ${panel.params.conversation_id}`}
        subtitle={`${m.topic} · ${panel.coverage.agent_id} · ${m.messages} messages · ${m.high_severity} high-severity finding(s). Click a finding, a turn or a message — the three views stay in sync.`} />
      <div className="space-y-4 p-4 pt-3">
        {/* timeline strip */}
        <div>
          <p className="label mb-1.5">Timeline (turn by turn)</p>
          <div className="flex flex-wrap gap-1" role="list" aria-label="Conversation timeline">
            {msgs.map((x) => (
              <button key={x.message_id} role="listitem" onClick={() => focusMessage(x.message_id)} data-testid={`xray-turn-${x.turn_index}`}
                aria-pressed={highlighted.has(x.message_id)} title={`T${x.turn_index} · ${x.speaker_role} · ${humanize(x.act)} · ${x.sentiment}`}
                className={cn("focus-ring relative flex h-9 w-9 flex-col items-center justify-center rounded-lg border text-[10px] transition",
                  x.speaker_role === "customer" ? "border-indigo/30" : "border-cyan/25", highlighted.has(x.message_id) ? "ring-2 ring-violet" : "opacity-90 hover:opacity-100")}>
                <span className={cn("absolute inset-x-1 bottom-1 h-1 rounded-full", SENT_BG[x.sentiment] ?? "bg-neu/50")} />
                <span className="font-mono text-ink">{x.turn_index}</span>
                <span className="text-[8px] uppercase text-faint">{x.speaker_role === "customer" ? "C" : "A"}</span>
                {x.signals.length > 0 && <span className="absolute -right-1 -top-1 h-2.5 w-2.5 rounded-full bg-neg ring-2 ring-surface" aria-label={`${x.signals.length} finding(s)`} />}
              </button>
            ))}
          </div>
          {cust.length > 1 && (
            <div className="mt-2" aria-label="Customer sentiment by turn">
              <ResponsiveContainer width="100%" height={120}>
                <LineChart data={cust} margin={{ top: 6, right: 8, left: -24, bottom: 0 }}>
                  <CartesianGrid stroke="rgba(148,163,184,0.08)" vertical={false} />
                  <XAxis dataKey="turn" type="number" domain={[0, Math.max(...msgs.map((x) => x.turn_index))]} allowDecimals={false} tickLine={false} axisLine={false} />
                  <YAxis domain={[-1, 1]} ticks={[-1, 0, 1]} tickLine={false} axisLine={false} />
                  <ReferenceLine y={0} stroke="rgba(148,163,184,0.25)" />
                  {activeTurns.map((t) => <ReferenceLine key={t} x={t} stroke="#A78BFA" strokeDasharray="3 3" />)}
                  <Tooltip contentStyle={{ background: "#17233C", border: "1px solid rgba(148,163,184,0.2)", borderRadius: 10, fontSize: 12 }}
                    formatter={(v: number) => score(v)} labelFormatter={(l) => `Turn ${l}`} />
                  <Line type="monotone" dataKey="score" stroke="#22D3EE" strokeWidth={2} isAnimationActive={false}
                    dot={(p: any) => <circle key={p.payload.id} cx={p.cx} cy={p.cy} r={highlighted.has(p.payload.id) ? 6 : 3.5} fill={highlighted.has(p.payload.id) ? "#A78BFA" : "#22D3EE"}
                      style={{ cursor: "pointer" }} onClick={() => focusMessage(p.payload.id)} />} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>

        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)]">
          {/* findings */}
          <div className="space-y-3" aria-label="X-Ray findings">
            {grouped.length === 0 && <p className="text-xs text-faint">No escalation signals, repeated concerns or communication gaps found.</p>}
            {grouped.map(([cat, idx]) => (
              <div key={cat}>
                <p className="label mb-1.5">{CAT_LABEL[cat] ?? humanize(cat)}</p>
                <ul className="space-y-1.5">
                  {idx.map((i) => {
                    const s = signals[i];
                    const on = activeSig === i || (activeMsg !== null && s.message_ids.includes(activeMsg));
                    return (
                      <li key={i}>
                        <button onClick={() => focusSignal(i)} aria-pressed={on} data-testid={`xray-signal-${s.kind}`}
                          className={cn("focus-ring w-full rounded-lg border px-3 py-2 text-left text-xs transition", on ? "border-violet/60 bg-violet/10" : "border-line bg-white/[0.02] hover:border-line/80")}>
                          <div className="flex items-center gap-1.5"><Badge tone={SEV_TONE[s.severity]}>{s.severity}</Badge><span className="font-medium text-ink">{s.title}</span></div>
                          <p className="mt-1 text-muted">{s.detail}</p>
                          <p className="mt-1 font-mono text-[10px] text-faint">turns {s.turns.join(", ")}</p>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              </div>
            ))}
            {(panel.series.phases?.rows ?? []).length > 0 && (
              <div className="rounded-lg border border-line p-2.5 text-[11px] text-muted">
                <p className="label mb-1">Mean customer sentiment by phase</p>
                {panel.series.phases.rows.map((p: any) => <span key={p.phase} className="mr-3">{humanize(p.phase)} <span className="text-ink">{score(p.mean_sentiment)}</span></span>)}
              </div>
            )}
          </div>
          {/* transcript */}
          <ol ref={scrollBox} className="relative max-h-[420px] space-y-2 overflow-y-auto rounded-xl border border-line bg-white/[0.015] p-3" aria-label="Transcript">
            {msgs.map((x) => {
              const isCust = x.speaker_role === "customer";
              const linked = sigForMsg(x.message_id);
              return (
                <li key={x.message_id} ref={(el) => { refs.current[x.message_id] = el; }} data-testid={`xray-msg-${x.message_id}`} data-highlighted={highlighted.has(x.message_id)}>
                  <button onClick={() => focusMessage(x.message_id)} className={cn("focus-ring flex w-full gap-2 rounded-xl p-1.5 text-left transition", isCust ? "" : "flex-row-reverse",
                    highlighted.has(x.message_id) && "bg-violet/10 ring-1 ring-violet/60")}>
                    <span className={cn("mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-full", isCust ? "bg-indigo-soft text-indigo" : "bg-cyan-soft text-cyan")}>
                      {isCust ? <User className="h-3 w-3" aria-label="Customer" /> : <Bot className="h-3 w-3" aria-label="Agent" />}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block text-xs leading-relaxed text-ink">{x.text}</span>
                      <span className="mt-0.5 flex flex-wrap gap-x-2 text-[10px] text-faint">
                        <span className="font-mono">T{x.turn_index}</span><span>{x.sentiment}{isCust && x.sentiment_score !== null ? ` ${score(x.sentiment_score)}` : ""}</span>
                        <span>{humanize(x.act)}</span>{x.empathy && <span className="text-pos">empathy</span>}
                        {linked.length > 0 && <span className="flex items-center gap-0.5 text-neg"><AlertOctagon className="h-2.5 w-2.5" />{linked.length} finding{linked.length > 1 ? "s" : ""}</span>}
                      </span>
                    </span>
                  </button>
                </li>
              );
            })}
          </ol>
        </div>
        <p className="text-[11px] text-faint">{panel.uncertainty_notes[0]}</p>
      </div>
    </Card>
  );
}
