import { useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Ban, BrainCircuit, History, Loader2, Paperclip, Plus, RotateCcw, Send, Settings2, Sparkles } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { AgentGraph } from "@/components/AgentGraph";
import { AgentTimeline } from "@/components/AgentTimeline";
import { BrandMark } from "@/components/Brand";
import { FourQuestionCards } from "@/components/QwenBlocks";
import { Badge, Card, ErrorBox, Skeleton, statusTone } from "@/components/ui";
import { Workspace } from "@/components/Workspace";
import { get, post, upload } from "@/lib/api";
import { useSession } from "@/lib/store";
import type { RunView } from "@/lib/types";

export const SAMPLES = [
  "Investigate abnormal vibration on AC-204, retrieve maintenance evidence, check parts and draft a maintenance plan.",
  "Compare 24-hour and 48-hour delay scenarios for a replacement part.",
  "Why did aircraft downtime rise in October? Show causes, trend and confidence limits.",
  "Assess this legacy Oracle schema and recommend a non-invasive modernization path.",
  "Generate a read-only API and MCP adapter for the approved parts inventory view.",
  "Show me all blocked agent actions and explain the governing policy.",
  "Create an executive modernization pitch with costs, risks and a 90-day pilot roadmap.",
  "Show which maintenance documents are stale or missing provenance.",
  "Compare aircraft maintenance recovery options using verified inventory availability.",
  "Export restricted maintenance records to my personal email.",
];

/** Flying Florina 3.0 suggested questions: each runs a real, planned harness workflow. */
export const SUGGESTED_3 = [
  "Show global component shortages.",
  "Which components have the highest predicted maintenance demand?",
  "Forecast hydraulic pump demand for the next 90 days.",
  "Show supplier delays on the global map.",
  "Explain this component's degradation trend.",
  "Compare two maintenance planning scenarios.",
  "What evidence supports this forecast?",
  "Show the agent execution graph.",
  "What happened in my previous investigation?",
  "Analyze this prerecorded drone video.",
  "Show historical forecast accuracy.",
  "Which software dependencies could be affected by this change?",
];

type Conversation = { id: string; title: string; updated: string; summary: string | null; turns: number | null };

function MemoryPanel({ onOpen }: { onOpen: (id: string) => void }) {
  const qc = useQueryClient();
  const convs = useQuery({ queryKey: ["memory-convs"], queryFn: () => get<Conversation[]>("/api/memory/conversations") });
  const del = async (id: string) => {
    await post(`/api/memory/conversations/${id}/delete`);
    qc.invalidateQueries({ queryKey: ["memory-convs"] });
    qc.invalidateQueries({ queryKey: ["sessions"] });
  };
  const rows = convs.data?.data ?? [];
  return (
    <div className="panel p-4" data-testid="memory-panel">
      <p className="label mb-1 flex items-center gap-1.5"><History className="h-3 w-3" />Recent sessions · saved memory</p>
      <p className="mb-2 text-[11px] text-faint">Stored locally in SQLite; survives restarts. Only a bounded summary is sent to Qwen.</p>
      {!rows.length ? <p className="text-xs text-faint">No sessions yet.</p> : (
        <ul className="max-h-56 space-y-1 overflow-y-auto">
          {rows.slice(0, 12).map((c) => (
            <li key={c.id} className="flex items-start gap-2 rounded-lg px-2 py-1.5 text-xs hover:bg-white/[0.04]">
              <button className="min-w-0 flex-1 text-left" onClick={() => onOpen(c.id)} title={c.summary ?? ""}>
                <span className="block truncate">{c.title}</span>
                <span className="block truncate text-faint">{c.summary ?? ""}</span>
              </button>
              <button className="shrink-0 text-faint hover:text-neg" onClick={() => del(c.id)} aria-label={`Delete conversation ${c.title}`}>Delete</button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function useRunPolling(runId: string | null) {
  return useQuery({
    queryKey: ["run", runId],
    enabled: !!runId,
    queryFn: () => get<RunView>(`/api/workflows/${runId}`),
    refetchInterval: (q) => (q.state.data?.data.finished ? false : 400),
  });
}

function RunCard({ runId, onQuery }: { runId: string; onQuery: (q: string) => void }) {
  const { data, error, refetch } = useRunPolling(runId);
  const [showGraph, setShowGraph] = useState(false);
  const qc = useQueryClient();
  if (error) return <ErrorBox error={error} onRetry={() => refetch()} />;
  const run = data?.data;
  if (!run) return null;
  const running = !run.finished;
  const hasWorkspace = (run.state.workspace ?? []).length > 0;
  const explaining = !!(run.state as unknown as { pending_explanation?: boolean }).pending_explanation;
  return (
    <article className="space-y-3" aria-busy={running} data-testid="run-card" data-status={run.status} data-workflow={run.workflow}>
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl rounded-br-sm bg-gradient-to-r from-indigo to-violet px-4 py-2 text-sm text-white shadow-sm">{run.query}</div>
      </div>
      <div className="flex items-start gap-3">
        <BrandMark size={32} />
        <div className="min-w-0 flex-1 space-y-3">
          <Card
            title={
              <span className="flex flex-wrap items-center gap-2">
                <span>Workflow: {run.workflow.replace(/_/g, " ")}</span>
                <Badge tone={statusTone(run.status)}>{run.status.replace(/_/g, " ")}</Badge>
                {run.state.intent?.confidence !== undefined && <Badge tone="gray">route confidence {run.state.intent.confidence}</Badge>}
                {run.state.timing?.total_ms !== undefined && <Badge tone="gray">{run.state.timing.total_ms} ms</Badge>}
                {run.replay_of && <Badge tone="purple">replay of {run.replay_of}</Badge>}
                {(run.state as unknown as { route?: { method?: string; family?: string | null; follow_up?: boolean } }).route?.method && (
                  <Badge tone="gold" title="Hybrid router stage that chose this workflow">
                    routed by {(run.state as unknown as { route: { method: string } }).route.method}
                    {(run.state as unknown as { route: { family?: string | null } }).route.family ? ` · ${(run.state as unknown as { route: { family: string } }).route.family}` : ""}
                    {(run.state as unknown as { route: { follow_up?: boolean } }).route.follow_up ? " · follow-up" : ""}
                  </Badge>
                )}
              </span>
            }
            subtitle="Live execution log from the workflow engine (persisted events, real timestamps)."
            actions={
              <>
                {run.graph && (
                  <button className="btn btn-ghost !py-1 text-xs" onClick={() => setShowGraph((v) => !v)} aria-expanded={showGraph}>
                    {showGraph ? "Hide graph" : "Show agent graph"}
                  </button>
                )}
                {running ? (
                  <button className="btn btn-ghost !py-1 text-xs" onClick={() => post(`/api/workflows/${run.run_id}/cancel`).then(() => refetch())}>
                    <Ban className="h-3.5 w-3.5" /> Cancel
                  </button>
                ) : (
                  <button
                    className="btn btn-ghost !py-1 text-xs"
                    onClick={async () => {
                      const r = await post<RunView>(`/api/workflows/${run.run_id}/replay`);
                      useSession.getState().pushRun(r.data.run_id);
                      qc.invalidateQueries({ queryKey: ["sessions"] });
                    }}
                  >
                    <RotateCcw className="h-3.5 w-3.5" /> Replay
                  </button>
                )}
              </>
            }
          >
            {showGraph && run.graph && (
              <div className="mb-3">
                <AgentGraph graph={run.graph} events={run.events} height={260} />
              </div>
            )}
            <AgentTimeline events={run.events} compact={!running} />
          </Card>
          {explaining && (
            <div role="status" className="panel flex items-center gap-3 p-4 text-sm" data-testid="qwen-writing">
              <BrainCircuit className="h-4 w-4 text-cyan" aria-hidden /><Loader2 className="h-4 w-4 animate-spin text-cyan" aria-hidden />
              Local Qwen is writing the explanation from the verified evidence below; the Evidence Challenger will check it before it appears.
            </div>
          )}
          {!hasWorkspace && running && <div className="panel space-y-3 p-4"><Skeleton className="h-4 w-1/3" /><Skeleton className="h-16" /><div className="grid grid-cols-4 gap-3">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-16" />)}</div></div>}
          {hasWorkspace && <Workspace blocks={run.state.workspace} onQuery={onQuery} runId={run.run_id} />}
        </div>
      </div>
    </article>
  );
}

type SessionRow = { id: string; title: string; updated: string; runs: { id: string; query: string; workflow: string; status: string; created: string }[] };

export function MissionControl() {
  const { actor, sessionId, runIds, setSession, pushRun, resetRuns } = useSession();
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [opts, setOpts] = useState({ pacing: false, inject: "" });
  const [showOpts, setShowOpts] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const qc = useQueryClient();
  const sessions = useQuery({ queryKey: ["sessions", actor?.id], queryFn: () => get<SessionRow[]>("/api/sessions") });

  useEffect(() => {
    if (runIds.length) endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [runIds.length]);

  const ask = async (q: string) => {
    if (!q.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      const options: Record<string, unknown> = {};
      if (opts.pacing) options.step_delay_ms = 350;
      if (opts.inject) options.inject_failure = opts.inject;
      const r = await post<RunView>("/api/chat/query", { query: q, session_id: sessionId, wait: false, persona: actor?.persona, options });
      setSession(r.data.session_id);
      pushRun(r.data.run_id);
      setQuery("");
      qc.invalidateQueries({ queryKey: ["sessions"] });
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };

  const onFile = async (f: File | undefined) => {
    if (!f) return;
    setError(null);
    try {
      const r = await upload<{ kind: string; filename: string; import_id: string }>("/api/legacy/import", f);
      await ask(`Assess this legacy schema (${r.data.filename}, ${r.data.kind}) and recommend a non-invasive modernization path.`);
    } catch (e) {
      setError(e);
    } finally {
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const fleet = useQuery({ queryKey: ["fleet-hero", actor?.id], queryFn: () => get<{ total_aircraft: number; available_pct: number; aog_count: number; open_work_orders: number }>("/api/fleet/overview"), retry: 0 });
  const f = fleet.data?.data;
  return (
    <div className="mx-auto w-full max-w-5xl space-y-6">
      {runIds.length === 0 ? (
        <div className="pt-2 sm:pt-6">
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }} className="flex flex-col items-center text-center">
            <BrandMark size={64} />
            <Badge tone="purple"><Sparkles className="h-3 w-3" />Agentic · evidence-backed · local Qwen · human-approved</Badge>
            <h1 className="gradient-title mt-4 text-3xl font-semibold tracking-tight sm:text-5xl">What should we understand about our aerospace operations?</h1>
            <p className="muted mx-auto mt-3 max-w-2xl text-sm sm:text-base">
              Ask in plain language. Specialist agents query verified synthetic data, your local Qwen model explains the evidence, an Evidence Challenger checks every number, and humans approve every consequential action.
            </p>
          </motion.div>
        </div>
      ) : (
        <div className="flex items-center justify-between">
          <h1 className="text-lg font-semibold">Flying Florina Chat</h1>
          <button className="btn btn-ghost !py-1 text-xs" onClick={resetRuns}><Plus className="h-3.5 w-3.5" />New session</button>
        </div>
      )}
      <motion.form initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.1 }}
        className="panel glow p-3"
        onSubmit={(e) => {
          e.preventDefault();
          ask(query);
        }}
      >
        <label htmlFor="prompt" className="sr-only">Ask a question</label>
        <textarea
          id="prompt"
          data-testid="prompt"
          rows={runIds.length ? 2 : 3}
          className="w-full resize-y bg-transparent p-2 text-[15px] outline-none"
          placeholder="Ask about component shortages, forecasts, suppliers, digital twins, aircraft health, recovery, modernization…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !e.ctrlKey && !e.metaKey) {
              e.preventDefault();
              ask(query);
            }
          }}
        />
        <div className="flex flex-wrap items-center gap-2 border-t border-token pt-2">
          <input ref={fileRef} type="file" accept=".sql,.json,.yaml,.yml,.csv,.xml,.zip" className="hidden" onChange={(e) => onFile(e.target.files?.[0])} data-testid="chat-upload" />
          <button type="button" className="btn btn-ghost !py-1 text-xs" onClick={() => fileRef.current?.click()} title="Upload SQL DDL, OpenAPI, CSV, OData XML or a ZIP of sources (parsed, never executed)">
            <Paperclip className="h-4 w-4" /> Attach metadata
          </button>
          <button type="button" className="btn btn-ghost !py-1 text-xs" onClick={() => setShowOpts((v) => !v)} aria-expanded={showOpts}>
            <Settings2 className="h-4 w-4" /> Run options
          </button>
          <span className="muted text-xs">as <b>{actor?.persona}</b> · <span className="kbd">Enter</span> to send</span>
          <button type="submit" className="btn btn-primary ml-auto" disabled={busy || !query.trim()} data-testid="ask"><Send className="h-4 w-4" /> Ask</button>
        </div>
        {showOpts && (
          <div className="mt-2 flex flex-wrap items-center gap-4 rounded-lg bg-white/[0.03] p-2 text-xs">
            <label className="flex items-center gap-1.5">
              <input type="checkbox" checked={opts.pacing} onChange={(e) => setOpts({ ...opts, pacing: e.target.checked })} />
              Demo pacing (adds a disclosed 350 ms pause per step)
            </label>
            <label className="flex items-center gap-1.5">
              Inject failure in step
              <select className="input !py-0.5 text-xs" value={opts.inject} onChange={(e) => setOpts({ ...opts, inject: e.target.value })} aria-label="Inject failure in step">
                <option value="">none</option>
                {["telemetry", "retrieval", "parts", "scheduling", "scenario_run", "trend"].map((st) => <option key={st} value={st}>{st} (fails once, then retries)</option>)}
              </select>
            </label>
          </div>
        )}
      </motion.form>

      {runIds.length === 0 && (
        <>
          <div>
            <p className="label mb-2 text-center">Flying Florina 3.0 · predictive intelligence</p>
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3" data-testid="suggested-3">
              {SUGGESTED_3.map((q) => (
                <button key={q} onClick={() => ask(q)} disabled={busy} className="glass edge-glow px-3 py-2.5 text-left text-xs transition hover:border-cyan/50">{q}</button>
              ))}
            </div>
          </div>
          <p className="label -mb-3 text-center">Four signature questions (2.0)</p>
          <FourQuestionCards onAsk={ask} disabled={busy} />
          <div className="flex flex-wrap justify-center gap-2" data-testid="samples">
            {SAMPLES.map((q) => (
              <button key={q} onClick={() => ask(q)} disabled={busy} className="rounded-full border border-token bg-white/[0.02] px-3 py-1.5 text-xs muted transition hover:border-indigo/40 hover:text-[var(--text)]">{q}</button>
            ))}
          </div>
          <div className="grid gap-4 md:grid-cols-[1.4fr_1fr]">
            <div className="panel p-4">
              <p className="label mb-3">Synthetic data in scope</p>
              {fleet.isLoading ? <Skeleton className="h-16" /> : f ? (
                <div className="grid grid-cols-4 gap-3 text-center">
                  {[["Aircraft", f.total_aircraft], ["In service", `${f.available_pct}%`], ["AOG", f.aog_count], ["Open WOs", f.open_work_orders]].map(([k, v]) => (
                    <div key={k as string}><p className="num text-lg font-semibold">{v as string}</p><p className="text-[11px] text-faint">{k}</p></div>
                  ))}
                  <p className="col-span-4 text-[11px] text-faint">Fictional fleet · seed 20261024 · data as of 2026-10-23</p>
                </div>
              ) : <p className="text-xs text-faint">Fleet data is withheld for this persona (PUBLIC only).</p>}
            </div>
            <MemoryPanel onOpen={(id) => { const se = (sessions.data?.data ?? []).find((x) => x.id === id); resetRuns(); setSession(id); se?.runs.forEach((r) => pushRun(r.id)); }} />
          </div>
        </>
      )}

      {error ? <ErrorBox error={error} /> : null}
      <div className="space-y-8">
        {runIds.map((id) => <RunCard key={id} runId={id} onQuery={ask} />)}
      </div>
      <div ref={endRef} />
      {runIds.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {SAMPLES.slice(0, 4).map((q) => (
            <button key={q} className="rounded-full border border-token px-3 py-1.5 text-xs muted hover:border-indigo/40 hover:text-[var(--text)]" onClick={() => ask(q)} disabled={busy}>{q.slice(0, 64)}…</button>
          ))}
        </div>
      )}
    </div>
  );
}
