import { useState } from "react";
import { post, waitForJob } from "../api";
import { ActionMessage, Card, Empty, Notice, Provenance, Status } from "../components/ui";
import { can, roleHint, useApp } from "../context";
import { useAction, usePoll } from "../hooks";

const FLAGSHIP = "Launch a weekend Ontario campaign: buy two eligible FreshSip beverages and receive one free, once per customer, while stock lasts.";

function NewBrief() {
  const { user, system, setRunId, refreshAll } = useApp();
  const [title, setTitle] = useState("FreshSip Ontario weekend campaign");
  const [text, setText] = useState(FLAGSHIP);
  const [mode, setMode] = useState("demo");
  const action = useAction();
  const allowed = can(user, "brief.submit");
  const liveOk = system?.live_mode?.available;
  return (
    <Card title="Submit a marketing brief">
      <form className="space-y-3" onSubmit={(e) => {
        e.preventDefault();
        action.run(async () => {
          const { run_id, job_id } = await post("/api/runs", { title, brief: text, mode });
          setRunId(run_id);
          refreshAll();
          await waitForJob(job_id);
          refreshAll();
        }, "Brief submitted. The Brief Analyst has finished its analysis.");
      }}>
        <div>
          <label htmlFor="title" className="label">Title</label>
          <input id="title" className="mt-1 w-full rounded-md border border-cream-300 px-2 py-1.5 text-sm" value={title} onChange={(e) => setTitle(e.target.value)} />
        </div>
        <div>
          <label htmlFor="brief" className="label">Brief (treated as untrusted input)</label>
          <textarea id="brief" rows={3} className="mt-1 w-full rounded-md border border-cream-300 px-2 py-1.5 text-sm" value={text} onChange={(e) => setText(e.target.value)} />
        </div>
        <fieldset className="flex flex-wrap items-center gap-4 text-sm">
          <legend className="label mb-1">Mode</legend>
          <label className="flex items-center gap-1"><input type="radio" name="mode" checked={mode === "demo"} onChange={() => setMode("demo")} /> DEMO (deterministic, no API key)</label>
          <label className={`flex items-center gap-1 ${liveOk ? "" : "text-navy-600"}`}>
            <input type="radio" name="mode" checked={mode === "live"} onChange={() => setMode("live")} /> LIVE (Anthropic)
          </label>
          {!liveOk && <span className="text-xs text-navy-600">{system?.live_mode?.reason}. A LIVE run fails visibly at analysis; no scripted output is substituted.</span>}
        </fieldset>
        <div className="flex flex-wrap items-center gap-3">
          <button className="btn-primary" disabled={!allowed || action.busy}>{action.busy ? "Submitting… (waiting for analysis)" : "Submit brief"}</button>
          {!allowed && <span className="text-xs text-navy-600">{roleHint("brief.submit")}</span>}
        </div>
        <ActionMessage message={action.message} />
      </form>
    </Card>
  );
}

function Clarification({ q, runId, onDone }: { q: any; runId: string; onDone: () => void }) {
  const { user } = useApp();
  const [choice, setChoice] = useState(q.options[0]);
  const [rationale, setRationale] = useState("");
  const action = useAction();
  const allowed = can(user, "clarification.decide");
  return (
    <li className="rounded-lg border border-cream-300 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-xs font-semibold">{q.id}</span>
        <span className="font-semibold">{q.topic}</span>
        {q.required ? <span className="rounded bg-navy-100 px-1.5 text-[11px] font-semibold">Required before {q.blocks}</span> : null}
        <Status value={q.status === "resolved" ? "resolved" : "open"} />
        {q.evidence?.policy_gap && <span className="rounded bg-brick-100 px-1.5 text-[11px] font-semibold text-brick-700">Policy gap</span>}
        <Provenance kind={q.detected_by === "live_ai" ? "live_ai" : "deterministic"} />
      </div>
      <p className="mt-1 text-sm">{q.question}</p>
      {q.evidence?.gap_note && <p className="mt-1 text-xs text-brick-700">Gap: {q.evidence.gap_note}</p>}
      {q.evidence?.retrieved?.length > 0 && (
        <details className="mt-1 text-xs">
          <summary className="cursor-pointer text-navy-700">Retrieved sources ({q.evidence.retrieved.length})</summary>
          <ul className="mt-1 space-y-1">
            {q.evidence.retrieved.map((r: any) => (
              <li key={r.ref} className="rounded bg-cream-50 p-2"><span className="font-semibold">{r.ref}</span> {r.heading}: <span className="text-navy-600">{r.excerpt}</span></li>
            ))}
          </ul>
        </details>
      )}
      {q.status === "resolved" ? (
        <div className="mt-2 flex flex-wrap items-center gap-2 rounded bg-leaf-100 px-2 py-1 text-sm">
          <span className="font-semibold">Decision:</span> {q.decision}
          <Provenance kind={q.decision_source === "seeded_demo" ? "seeded_decision" : "human"} />
          <span className="text-xs text-navy-600">by {q.decided_by}{q.rationale ? ` · ${q.rationale}` : ""}</span>
        </div>
      ) : (
        <form className="mt-2 flex flex-wrap items-end gap-2" onSubmit={(e) => {
          e.preventDefault();
          action.run(async () => {
            await post(`/api/runs/${runId}/clarifications/${q.id}`, { decision: choice, rationale });
            onDone();
          });
        }}>
          <label className="text-xs">Decision
            <select className="ml-1 rounded border border-cream-300 px-1 py-1 text-sm" value={choice} onChange={(e) => setChoice(e.target.value)}>
              {q.options.map((o: string) => <option key={o}>{o}</option>)}
            </select>
          </label>
          <label className="text-xs">Rationale
            <input className="ml-1 w-56 rounded border border-cream-300 px-1 py-1 text-sm" value={rationale} onChange={(e) => setRationale(e.target.value)} />
          </label>
          <button className="btn-ghost" disabled={!allowed || action.busy} title={allowed ? undefined : roleHint("clarification.decide")}>Record decision</button>
          <ActionMessage message={action.message} />
        </form>
      )}
    </li>
  );
}

export default function Brief() {
  const { runId, user, refreshAll } = useApp();
  const { data, refresh, error } = usePoll<any>(runId ? `/api/runs/${runId}` : null, 3000);
  const seeded = useAction();
  const gate = useAction();
  const cont = useAction();
  const open = data?.clarifications?.filter((c: any) => c.required && c.status !== "resolved") ?? [];
  const analysis = data?.brief?.analysis;
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Brief intake</h1>
      <NewBrief />
      {!runId ? <Empty>No run selected.</Empty> : error ? <Notice kind="error">{error}</Notice> : !data ? <Empty>Loading…</Empty> : (
        <>
          <Card title={<>Brief v{data.brief.version} · <span className="font-mono text-sm">{runId}</span></>} actions={<Status value={data.run.status} />}>
            <blockquote className="border-l-4 border-leaf-500 bg-cream-50 px-3 py-2 text-sm">{data.brief.text}</blockquote>
            {data.run.error && <div className="mt-2"><Notice kind="error">{data.run.error}</Notice></div>}
            {analysis ? (
              <div className="mt-3 grid gap-3 text-sm md:grid-cols-3">
                <div><div className="label">Objective</div><p>{analysis.objective}</p></div>
                <div><div className="label">Constraints</div><ul className="list-disc pl-5">{analysis.constraints.map((c: string) => <li key={c}>{c}</li>)}</ul></div>
                <div><div className="label">Stakeholders</div><ul className="list-disc pl-5">{analysis.stakeholders.map((c: string) => <li key={c}>{c}</li>)}</ul></div>
                <div className="md:col-span-3 flex items-center gap-2 text-xs text-navy-600"><Provenance kind={data.brief.analysis_source === "live_ai" ? "live_ai" : "deterministic"} /> {analysis.method ?? "Live model analysis (validated against a schema)"}</div>
              </div>
            ) : <p className="mt-2 text-sm text-navy-600">Analysis not available yet.</p>}
          </Card>
          <Card title={`Clarification decisions (${open.length} open)`} actions={
            <>
              <button className="btn-ghost" disabled={!can(user, "clarification.decide") || seeded.busy || open.length === 0}
                title={can(user, "clarification.decide") ? "Records the seeded answers, labelled as selected demo decisions" : roleHint("clarification.decide")}
                onClick={() => seeded.run(async () => { await post(`/api/runs/${runId}/clarifications/apply-seeded`); refresh(); }, "Seeded demo decisions recorded and labelled.")}>
                Apply seeded demo decisions
              </button>
              <button className="btn-ghost" disabled={!can(user, "run.control") || gate.busy}
                title={can(user, "run.control") ? "Asks the server to start implementation now" : roleHint("run.control")}
                onClick={() => gate.run(async () => { await post(`/api/runs/${runId}/request-implementation`); })}>
                Try to start implementation
              </button>
              <button className="btn-primary" disabled={!can(user, "run.advance") || cont.busy}
                title={can(user, "run.advance") ? "Resumes the workflow; gates re-check recorded decisions" : roleHint("run.advance")}
                onClick={() => cont.run(async () => { const { job_id } = await post(`/api/runs/${runId}/continue`); await waitForJob(job_id); refresh(); refreshAll(); }, "Workflow advanced to the next human gate.")}>
                {cont.busy ? "Running agents…" : "Continue workflow"}
              </button>
            </>
          }>
            <div className="mb-2 space-y-2">
              <ActionMessage message={seeded.message} />
              {gate.message && <Notice kind={gate.message.kind === "error" ? "warn" : "ok"}>{gate.message.kind === "error" ? `Blocked by server: ${gate.message.text}` : gate.message.text}</Notice>}
              <ActionMessage message={cont.message} />
            </div>
            {data.clarifications.length === 0 ? <Empty>No ambiguities recorded yet.</Empty> : (
              <ul className="space-y-2">{data.clarifications.map((q: any) => <Clarification key={q.id} q={q} runId={runId} onDone={refresh} />)}</ul>
            )}
          </Card>
        </>
      )}
    </div>
  );
}
