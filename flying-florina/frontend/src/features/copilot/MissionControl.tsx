import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Ban, History, Paperclip, RotateCcw, Send, Settings2, Sparkles } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { AgentGraph } from "@/components/AgentGraph";
import { AgentTimeline } from "@/components/AgentTimeline";
import { BrandMark } from "@/components/Brand";
import { Badge, Card, ErrorBox, statusTone } from "@/components/ui";
import { Workspace } from "@/components/Workspace";
import { get, post, upload } from "@/lib/api";
import { time } from "@/lib/format";
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

export function useRunPolling(runId: string | null) {
  return useQuery({
    queryKey: ["run", runId],
    enabled: !!runId,
    queryFn: () => get<RunView>(`/api/workflows/${runId}`),
    refetchInterval: (q) => (q.state.data?.data.finished ? false : 350),
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
  return (
    <article className="space-y-3" aria-busy={running} data-testid="run-card" data-status={run.status} data-workflow={run.workflow}>
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl rounded-br-sm bg-purple px-4 py-2 text-sm text-white shadow-sm">{run.query}</div>
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
          {run.finished && <Workspace blocks={run.state.workspace} onQuery={onQuery} runId={run.run_id} />}
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
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
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

  return (
    <div className="grid gap-6 xl:grid-cols-[1fr_280px]">
      <div className="mx-auto w-full max-w-4xl space-y-5">
        <div className="flex flex-col items-center gap-3 pt-2 text-center">
          <BrandMark size={72} />
          <h1 className="text-2xl font-bold tracking-tight">Ask Flying_Florina</h1>
          <p className="muted max-w-2xl text-sm">
            From legacy systems to trusted industrial intelligence. Ask. Analyze. Modernize. Govern. Act—with approval. Every answer is computed from synthetic data by local rules and agents; consequential actions wait for a human.
          </p>
        </div>

        <form
          className="panel p-3 shadow-sm"
          onSubmit={(e) => {
            e.preventDefault();
            ask(query);
          }}
        >
          <label htmlFor="prompt" className="sr-only">
            Ask a question
          </label>
          <textarea
            id="prompt"
            data-testid="prompt"
            rows={3}
            className="w-full resize-y bg-transparent p-2 text-[15px] outline-none"
            placeholder="e.g. Investigate AC-204 vibration anomaly, check maintenance evidence, parts and available technicians, and draft recovery options."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) ask(query);
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
            <span className="muted text-xs">
              as <b>{actor?.persona}</b> · <span className="kbd">Ctrl</span>+<span className="kbd">Enter</span>
            </span>
            <button type="submit" className="btn btn-primary ml-auto" disabled={busy || !query.trim()} data-testid="ask">
              <Send className="h-4 w-4" /> Ask
            </button>
          </div>
          {showOpts && (
            <div className="mt-2 flex flex-wrap items-center gap-4 rounded-lg bg-[var(--panel-2)] p-2 text-xs">
              <label className="flex items-center gap-1.5">
                <input type="checkbox" checked={opts.pacing} onChange={(e) => setOpts({ ...opts, pacing: e.target.checked })} />
                Demo pacing (adds a disclosed 350 ms pause per step so the timeline is easy to follow)
              </label>
              <label className="flex items-center gap-1.5">
                Inject failure in step
                <select className="input !py-0.5 text-xs" value={opts.inject} onChange={(e) => setOpts({ ...opts, inject: e.target.value })} aria-label="Inject failure in step">
                  <option value="">none</option>
                  {["telemetry", "retrieval", "parts", "scheduling", "scenario_run", "trend"].map((s) => (
                    <option key={s} value={s}>
                      {s} (fails once, then retries)
                    </option>
                  ))}
                </select>
              </label>
            </div>
          )}
        </form>

        {runIds.length === 0 && (
          <div>
            <div className="muted mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider">
              <Sparkles className="h-3.5 w-3.5" /> Sample questions (all functional)
            </div>
            <div className="grid gap-2 md:grid-cols-2" data-testid="samples">
              {SAMPLES.map((s) => (
                <button key={s} className="panel px-3 py-2 text-left text-sm hover:border-purple" onClick={() => ask(s)} disabled={busy}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {error ? <ErrorBox error={error} /> : null}
        <div className="space-y-8">
          {runIds.map((id) => (
            <RunCard key={id} runId={id} onQuery={ask} />
          ))}
        </div>
        <div ref={endRef} />
        {runIds.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {SAMPLES.slice(0, 4).map((s) => (
              <button key={s} className="btn btn-ghost !text-xs" onClick={() => ask(s)} disabled={busy}>
                {s.slice(0, 60)}...
              </button>
            ))}
          </div>
        )}
      </div>

      <aside className="space-y-3" aria-label="Session history">
        <Card
          title={
            <span className="flex items-center gap-1.5">
              <History className="h-4 w-4" /> Session history
            </span>
          }
          actions={
            <button className="btn btn-ghost !py-0.5 text-xs" onClick={resetRuns}>
              New session
            </button>
          }
        >
          {(sessions.data?.data ?? []).length === 0 && <div className="muted text-xs">No sessions yet for this persona.</div>}
          <ul className="space-y-2">
            {(sessions.data?.data ?? []).map((s) => (
              <li key={s.id} className="text-xs">
                <button
                  className={`w-full rounded-lg border px-2 py-1.5 text-left ${s.id === sessionId ? "border-purple" : "border-token"}`}
                  onClick={() => {
                    resetRuns();
                    setSession(s.id);
                    s.runs.forEach((r) => pushRun(r.id));
                  }}
                >
                  <div className="truncate font-medium">{s.title}</div>
                  <div className="muted">
                    {s.runs.length} run(s) · {time(s.updated)}
                  </div>
                </button>
              </li>
            ))}
          </ul>
        </Card>
      </aside>
    </div>
  );
}
