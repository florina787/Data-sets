import { useEffect, useRef, useState } from "react";
import { api, dsPath } from "../lib/api";
import { useApp, useData } from "../lib/state";
import { fmtDate, fmtInt, fmtPct } from "../lib/format";
import { Badge, Button, Card, ErrorBox, Field, Notice, PageHeader, Spinner, Stat, Table, inputCls } from "../components/ui";

function Imports() {
  const { refreshDatasets, status, dataset } = useApp();
  const [jobs, setJobs] = useState<any[]>([]);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [path, setPath] = useState("twcs/twcs.csv");
  const [seed, setSeed] = useState("");
  const [limit, setLimit] = useState("200");
  const fileRef = useRef<HTMLInputElement>(null);
  const load = () => api<any>("/api/imports/jobs").then((r) => setJobs(r.jobs)).catch(() => undefined);
  useEffect(() => {
    load();
    const t = setInterval(() => { load(); }, 1500);
    return () => clearInterval(t);
  }, []);
  const active = jobs.some((j) => ["queued", "running"].includes(j.status));
  useEffect(() => { if (!active) refreshDatasets(); }, [active]);
  const run = async (fn: () => Promise<any>, label: string) => {
    setErr(null); setMsg(null);
    try { const r = await fn(); setMsg(`${label} queued (${r.job_id}).`); load(); } catch (e: any) { setErr(e.message); }
  };
  const opts = { seed: seed ? Number(seed) : undefined };
  return (
    <Card title="Data sources and imports" subtitle="Target: Kaggle “Customer Support on Twitter” (thoughtvector/customer-support-on-twitter), file twcs.csv. Imports run as background jobs.">
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="space-y-2">
          <div className="text-sm font-medium">Upload the downloaded CSV</div>
          <input ref={fileRef} type="file" accept=".csv,text/csv" className="text-xs" aria-label="CSV file" />
          <Button size="sm" variant="primary" onClick={() => run(async () => {
            const f = fileRef.current?.files?.[0];
            if (!f) throw new Error("Choose twcs.csv first.");
            const form = new FormData(); form.append("file", f); if (seed) form.append("seed", seed);
            return api("/api/imports/upload", { form });
          }, "Upload import")}>Upload and import</Button>
          <p className="text-[11px] text-muted">Size-limited and schema-validated before the job starts.</p>
        </div>
        <div className="space-y-2">
          <Field label="Import from a local path (inside the server import directory)"><input className={inputCls} value={path} onChange={(e) => setPath(e.target.value)} /></Field>
          <Button size="sm" onClick={() => run(() => api("/api/imports/local", { body: { path, ...opts } }), "Local import")}>Import local file</Button>
        </div>
        <div className="space-y-2">
          <div className="text-sm font-medium">Download with kagglehub</div>
          <Button size="sm" onClick={() => run(() => api("/api/imports/kaggle", { body: opts }), "Kaggle download")}>Download and import from Kaggle</Button>
          <p className="text-[11px] text-muted">Requires network access to Kaggle (and credentials if Kaggle asks for them).</p>
        </div>
      </div>
      <div className="mt-3 flex flex-wrap items-end gap-3">
        <Field label="Sampling seed (optional)"><input className={`${inputCls} w-36`} value={seed} onChange={(e) => setSeed(e.target.value.replace(/\D/g, ""))} placeholder="default 20240601" /></Field>
        <span className="text-xs text-muted">Up to 3,000 eligible threads are selected; the actual count is shown after import.</span>
      </div>
      {dataset && !dataset.synthetic && (
        <div className="mt-4 rounded-md border border-line p-3">
          <div className="text-sm font-medium">Connected analysis for {dataset.name}</div>
          <p className="text-xs text-muted">Runs structured extraction with the configured model ({status?.model?.configured ? status.model.model_id : "not configured"}) and caches results by content hash, model and prompt version.</p>
          <div className="mt-2 flex flex-wrap items-end gap-2">
            <Field label="Conversations to analyse"><input className={`${inputCls} w-28`} value={limit} onChange={(e) => setLimit(e.target.value.replace(/\D/g, ""))} /></Field>
            <Button size="sm" variant="primary" disabled={!status?.model?.configured} onClick={() => run(() => api(dsPath(dataset.id, "analysis-jobs"), { body: { limit: limit ? Number(limit) : null, activate: true } }), "Model analysis")}>Run model analysis</Button>
            <Button size="sm" disabled={!status?.model?.configured} onClick={() => run(() => api(dsPath(dataset.id, "translation-jobs"), { method: "POST" }), "Translation")}>Translate non-English messages</Button>
          </div>
          {!status?.model?.configured && <p className="mt-1 text-xs text-amber">Model not configured: set MODEL_PROVIDER and credentials on the backend.</p>}
        </div>
      )}
      {msg && <p className="mt-2 text-xs text-teal" role="status">{msg}</p>}
      {err && <div className="mt-2"><ErrorBox>{err}</ErrorBox></div>}
      <div className="mt-4">
        <Table head={["Job", "Kind", "Status", "Stage", "Progress", "Result / error", ""]}
          rows={jobs.map((j) => [
            <span key="i" className="font-mono text-[11px]">{j.id}</span>, j.kind,
            <Badge key="s" tone={j.status === "completed" ? "green" : j.status === "failed" ? "red" : j.status === "running" ? "teal" : "amber"}>{j.status}</Badge>,
            j.stage,
            <div key="p" className="w-28"><div className="h-1.5 rounded bg-line"><div className="h-1.5 rounded bg-teal" style={{ width: `${Math.round(j.progress * 100)}%` }} /></div><span className="text-[10px]">{fmtPct(j.progress)}</span></div>,
            <span key="r" className="text-[11px]">{j.error ?? (j.params?.result ? JSON.stringify(j.params.result) : "")}</span>,
            ["queued", "running"].includes(j.status) ? <Button key="c" size="sm" variant="danger" onClick={() => api(`/api/imports/jobs/${j.id}/cancel`, { method: "POST" }).then(load)}>Cancel</Button>
              : ["interrupted", "failed", "cancelled"].includes(j.status) ? <Button key="c" size="sm" onClick={() => api(`/api/imports/jobs/${j.id}/resume`, { method: "POST" }).then(load)}>Resume</Button> : "",
          ])} />
      </div>
    </Card>
  );
}

export function DataQuality() {
  const { dataset } = useApp();
  const q = useData<any>((id) => api(dsPath(id, "quality")));
  const d = q.data;
  const m = d?.manifest ?? {};
  return (
    <div className="space-y-4">
      <PageHeader title="Data quality and imports" description="Import manifest, reply-graph integrity, sampling coverage, unknown labels, extraction failures and redaction limits." />
      <Imports />
      {!dataset ? null : q.error ? <ErrorBox onRetry={q.reload}>{q.error}</ErrorBox> : !d ? <Spinner /> : (
        <>
          {d.dataset.synthetic && <Notice>This dataset is a synthetic fixture. It deliberately includes defects (duplicates, a cycle, missing parents, invalid rows) to exercise the pipeline.</Notice>}
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
            <Stat label="Conversations selected" value={fmtInt(m.sampling?.selected)} sub={`of ${fmtInt(m.sampling?.eligible)} eligible · requested ${fmtInt(m.sampling?.requested)}`} />
            <Stat label="Rows read" value={fmtInt(m.counts?.rows_read)} sub={`${fmtInt(m.counts?.unique_messages)} unique messages`} />
            <Stat label="Reply threads found" value={fmtInt(m.counts?.threads_total)} sub="before eligibility rules" />
            <Stat label="Branched threads (selected)" value={fmtInt(m.branching?.selected?.branched_threads)} sub={`${fmtInt(m.branching?.selected?.branch_points)} branch points`} />
            <Stat label="Partial conversations" value={fmtInt(d.missing_messages.partial_conversations)} sub="missing replies or text" />
          </div>
          <div className="grid gap-4 xl:grid-cols-2">
            <Card title="Import manifest">
              <Table head={["Field", "Value"]} rows={[
                ["Source", m.source], ["File", `${m.file_name} (${fmtInt(m.file_bytes)} bytes)`], ["SHA-256", <span key="h" className="break-all font-mono text-[11px]">{m.file_hash_sha256}</span>],
                ["Parser", m.parser_version], ["Redactor", m.redactor_version], ["Language detector", m.language_detector], ["Analysis", d.dataset.active_analysis],
                ["Sampling seed", m.sampling?.seed], ["Selection method", m.sampling?.method], ["Unit of analysis", m.unit_of_analysis],
                ["Schema columns", (m.schema?.columns ?? []).join(", ")], ["Import started", fmtDate(m.import_started_at, { dateStyle: "medium", timeStyle: "short" } as any)],
                ["Import completed", fmtDate(m.import_completed_at, { dateStyle: "medium", timeStyle: "short" } as any)],
              ]} />
            </Card>
            <Card title="Eligibility and exclusions" subtitle={`Coverage of eligible threads: ${fmtPct(m.sampling?.coverage_of_eligible)}`}>
              <ul className="mb-3 list-disc pl-5 text-xs text-muted">{(m.sampling?.eligibility_rules ?? []).map((r: string) => <li key={r}>{r}</li>)}</ul>
              <Table head={["Reason", "Threads", "Messages"]} rows={d.exclusions.map((e: any) => [e.reason.replace(/_/g, " "), fmtInt(e.threads), fmtInt(e.messages)])} />
              {m.exclusions?.cycle_component_messages ? <p className="mt-2 text-xs text-muted">{m.exclusions.cycle_component_messages} messages sit in reply cycles and form no conversation.</p> : null}
            </Card>
            <Card title="Reply graph integrity">
              <Table head={["Check", "Count"]} rows={[
                ["Messages whose parent is missing from the file", d.missing_messages.messages_with_missing_parent],
                ["Threads excluded because their start is missing", d.missing_messages.threads_excluded_for_missing_root_parent],
                ["Selected threads with reply references to absent messages", d.missing_messages.selected_threads_with_dangling_reply_refs],
                ["Messages in reply cycles", d.cycles.messages_in_cycles],
                ["Exact duplicate rows dropped", d.duplicates.exact_dropped],
                ["Conflicting duplicate ids (thread excluded)", d.duplicates.conflicting],
                ...Object.entries(d.rejected_rows).map(([k, v]) => [k.replace(/_/g, " "), v as number]),
                ["response_tweet_id vs in_response_to mismatches", m.counts?.response_reference_mismatches ?? 0],
              ]} />
            </Card>
            <Card title="Unknown labels and extraction" subtitle={`Denominator: ${d.unknown_labels.denominator} conversations`}>
              <Table head={["Field", "Unknown", "Share"]} rows={Object.entries(d.unknown_labels).filter(([k]) => k !== "denominator").map(([k, v]) => [k.replace(/_/g, " "), v as number, fmtPct((v as number) / (d.unknown_labels.denominator || 1))])} />
              <Table head={["Method", "Status", "Analyses"]} rows={d.extraction.map((e: any) => [e.method, e.status, e.count])} />
              <p className="mt-2 text-xs text-muted">Invalid evidence spans dropped: {d.invalid_evidence_spans_dropped}. Messages with unknown language: {d.unknown_language_messages}.</p>
            </Card>
            <Card title="Redaction" subtitle="Applied before storage, indexing, model calls and tracing">
              <Table head={["Type", "Redactions"]} rows={Object.entries(d.redactions).map(([k, v]) => [k, v as number])} />
              <ul className="mt-3 list-disc space-y-1 pl-5 text-xs text-muted">{d.redaction_limitations.map((l: string) => <li key={l}>{l}</li>)}</ul>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
