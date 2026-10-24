import { RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { CatMark } from "../components/CatMark";
import { TopBar } from "../components/Shell";
import { Button, Card, CardHeader } from "../components/ui";
import { useApp } from "../stores/app";

interface Summary {
  count: number;
  mean?: number;
  p50?: number;
  p95?: number;
  min?: number;
  max?: number;
}
interface Metrics {
  live: Record<string, Summary>;
  history: { summary: Record<string, Summary>; daily: Record<string, { day: string; mean: number; count: number }[]>; per_model: Record<string, Record<string, Summary>> };
  resources: { system_cpu_percent: number; system_ram_used_gb: number; system_ram_total_gb: number; backend_rss_mb: number; backend_cpu_percent: number; gpu: { name: string; util_percent: number; mem_used_mb: number; mem_total_mb: number }[] | null };
  counts: { sessions_by_mode: Record<string, number>; question_categories: Record<string, number>; messages: number };
  practice: { role: string; category: string; score: number; at: string }[];
  embedding_cache_hits: number;
}

const AXIS = { stroke: "#D6B79B", fontSize: 11, tickLine: false };
const TT = { contentStyle: { background: "#FFFFFF", border: "1px solid #EFE2D2", borderRadius: 10, fontSize: 12, color: "#4A2C1C" } };

const LATENCY: [string, string][] = [
  ["asr.partial_ms", "ASR partial"],
  ["asr.final_ms", "ASR final"],
  ["question.detect_ms", "Question detection"],
  ["rag.retrieval_ms", "Retrieval"],
  ["llm.first_token_ms", "First token"],
  ["llm.total_ms", "Total response"],
  ["vision.ocr_ms", "OCR"],
  ["vision.analysis_ms", "Screen analysis"],
  ["audio.capture_delay_ms", "Audio capture delay"],
];

function fmt(v: number | undefined, unit = "ms") {
  if (v == null) return "–";
  if (unit === "ms" && v >= 1000) return `${(v / 1000).toFixed(2)} s`;
  return `${v.toFixed(unit === "ms" ? 0 : 1)} ${unit}`;
}

function Empty({ text }: { text: string }) {
  return <p className="px-5 pb-5 text-sm text-caramel">{text}</p>;
}

export function Analytics() {
  const { api } = useApp();
  const [m, setM] = useState<Metrics | null>(null);
  const load = useCallback(async () => {
    if (api) setM(await api.get<Metrics>("/api/metrics?days=30"));
  }, [api]);
  useEffect(() => {
    void load();
    const t = setInterval(() => void load(), 5000);
    return () => clearInterval(t);
  }, [load]);

  if (!m) {
    return (
      <div className="flex h-full flex-col items-center justify-center">
        <CatMark size={56} mood="thinking" />
      </div>
    );
  }
  const s = { ...m.history.summary, ...Object.fromEntries(Object.entries(m.live).filter(([k]) => !m.history.summary[k])) };
  const latencyRows = LATENCY.filter(([k]) => s[k]?.count).map(([k, label]) => ({ label, p50: s[k].p50 ?? 0, p95: s[k].p95 ?? 0, n: s[k].count }));
  const daily = (m.history.daily["llm.total_ms"] ?? []).map((d) => ({ day: d.day.slice(5), seconds: +(d.mean / 1000).toFixed(2), n: d.count }));
  const models = Object.entries(m.history.per_model).map(([model, v]) => ({
    model,
    tps: v["llm.tokens_per_s"]?.mean ?? 0,
    ft: v["llm.first_token_ms"]?.p50 ?? 0,
    n: v["llm.total_ms"]?.count ?? 0,
  }));
  const cats = Object.entries(m.counts.question_categories).map(([k, v]) => ({ k: k.replace("_", " "), v }));
  const modes = Object.entries(m.counts.sessions_by_mode).map(([k, v]) => ({ k, v }));
  const practice = m.practice.map((p, i) => ({ i: i + 1, score: p.score }));
  const ret = s["rag.top_score"];

  return (
    <div className="flex h-full flex-col">
      <TopBar
        title="Analytics"
        subtitle="Measured on this computer over the last 30 days. Empty charts mean nothing has been measured yet."
        actions={
          <Button size="sm" variant="ghost" onClick={() => void load()}>
            <RefreshCw size={14} /> Refresh
          </Button>
        }
      />
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto grid max-w-6xl gap-4 px-6 py-6 md:grid-cols-4">
          {[
            ["Sessions", Object.values(m.counts.sessions_by_mode).reduce((a, b) => a + b, 0).toString()],
            ["Messages", m.counts.messages.toString()],
            ["Median first token", fmt(s["llm.first_token_ms"]?.p50)],
            ["Median tokens/s", s["llm.tokens_per_s"]?.p50 != null ? s["llm.tokens_per_s"].p50!.toFixed(1) : "–"],
          ].map(([k, v]) => (
            <Card key={k} className="p-4">
              <p className="text-xs text-caramel">{k}</p>
              <p className="mt-1 text-2xl font-semibold text-bark tabular-nums">{v}</p>
            </Card>
          ))}

          <Card className="md:col-span-2">
            <CardHeader title="Pipeline latency" subtitle="p50 and p95 in milliseconds" />
            {latencyRows.length ? (
              <div className="h-72 p-3">
                <ResponsiveContainer>
                  <BarChart data={latencyRows} layout="vertical" margin={{ left: 40 }}>
                    <CartesianGrid stroke="#EFE2D2" horizontal={false} />
                    <XAxis type="number" {...AXIS} />
                    <YAxis type="category" dataKey="label" width={130} {...AXIS} stroke="#75462D" />
                    <Tooltip {...TT} />
                    <Bar dataKey="p50" fill="#99613E" radius={[0, 4, 4, 0]} />
                    <Bar dataKey="p95" fill="#D6B79B" radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <Empty text="No latency measured yet. Ask a question or start the microphone." />
            )}
          </Card>

          <Card className="md:col-span-2">
            <CardHeader title="Response time per day" subtitle="Mean total response time (s)" />
            {daily.length ? (
              <div className="h-72 p-3">
                <ResponsiveContainer>
                  <LineChart data={daily}>
                    <CartesianGrid stroke="#EFE2D2" vertical={false} />
                    <XAxis dataKey="day" {...AXIS} />
                    <YAxis {...AXIS} />
                    <Tooltip {...TT} />
                    <Line type="monotone" dataKey="seconds" stroke="#75462D" strokeWidth={2} dot={{ r: 3, fill: "#75462D" }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <Empty text="No answers measured yet." />
            )}
          </Card>

          <Card className="md:col-span-2">
            <CardHeader title="Model performance" />
            {models.length ? (
              <table className="m-5 mt-3 w-[calc(100%-2.5rem)] text-sm">
                <thead>
                  <tr className="text-left text-xs text-caramel">
                    <th className="pb-2 font-medium">Model</th>
                    <th className="pb-2 font-medium">Answers</th>
                    <th className="pb-2 font-medium">Median first token</th>
                    <th className="pb-2 font-medium">Mean tokens/s</th>
                  </tr>
                </thead>
                <tbody>
                  {models.map((r) => (
                    <tr key={r.model} className="border-t border-cream text-bark">
                      <td className="py-1.5">{r.model}</td>
                      <td className="tabular-nums">{r.n}</td>
                      <td className="tabular-nums">{fmt(r.ft)}</td>
                      <td className="tabular-nums">{r.tps ? r.tps.toFixed(1) : "–"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <Empty text="No model runs recorded yet." />
            )}
          </Card>

          <Card className="md:col-span-2">
            <CardHeader title="Question categories" subtitle="Intents of questions you asked" />
            {cats.length ? (
              <div className="h-56 p-3">
                <ResponsiveContainer>
                  <BarChart data={cats}>
                    <XAxis dataKey="k" {...AXIS} />
                    <YAxis allowDecimals={false} {...AXIS} />
                    <Tooltip {...TT} />
                    <Bar dataKey="v" name="questions" fill="#B87848" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <Empty text="Spoken and classified questions will be counted here." />
            )}
          </Card>

          <Card className="md:col-span-2">
            <CardHeader title="Retrieval quality" subtitle="Top passage score of grounded answers (cosine/keyword blend)" />
            {ret?.count ? (
              <div className="grid grid-cols-3 gap-3 p-5 text-sm">
                <div>
                  <p className="text-xs text-caramel">Median</p>
                  <p className="text-xl font-semibold text-bark">{ret.p50?.toFixed(3)}</p>
                </div>
                <div>
                  <p className="text-xs text-caramel">Lowest</p>
                  <p className="text-xl font-semibold text-bark">{ret.min?.toFixed(3)}</p>
                </div>
                <div>
                  <p className="text-xs text-caramel">Retrievals</p>
                  <p className="text-xl font-semibold text-bark">{ret.count}</p>
                </div>
                <p className="col-span-3 text-xs text-caramel">Embedding cache hits this run: {m.embedding_cache_hits}</p>
              </div>
            ) : (
              <Empty text="Select a knowledge collection and ask a question to measure retrieval." />
            )}
          </Card>

          <Card className="md:col-span-2">
            <CardHeader title="Practice performance" subtitle="Scores of evaluated practice answers" />
            {practice.length ? (
              <div className="h-56 p-3">
                <ResponsiveContainer>
                  <LineChart data={practice}>
                    <CartesianGrid stroke="#EFE2D2" vertical={false} />
                    <XAxis dataKey="i" {...AXIS} />
                    <YAxis domain={[0, 10]} {...AXIS} />
                    <Tooltip {...TT} />
                    <Line type="monotone" dataKey="score" stroke="#99613E" strokeWidth={2} dot={{ r: 3, fill: "#99613E" }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <Empty text="No practice answers evaluated yet." />
            )}
          </Card>

          <Card className="md:col-span-2">
            <CardHeader title="Sessions by mode" />
            {modes.length ? (
              <ul className="space-y-2 p-5">
                {modes.map((r) => (
                  <li key={r.k} className="flex items-center gap-3 text-sm text-bark">
                    <span className="w-28 capitalize">{r.k}</span>
                    <div className="h-2 flex-1 rounded-full bg-cream">
                      <div className="h-2 rounded-full bg-caramel" style={{ width: `${(100 * r.v) / Math.max(...modes.map((x) => x.v))}%` }} />
                    </div>
                    <span className="w-8 text-right tabular-nums">{r.v}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <Empty text="No sessions yet." />
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
