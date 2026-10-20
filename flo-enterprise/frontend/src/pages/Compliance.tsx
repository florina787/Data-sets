import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createColumnHelper } from "@tanstack/react-table";
import { useState } from "react";
import { DataTable } from "@/components/DataTable";
import { Badge, Button, Card, ErrorState, Input, Label, PageHeader, Select, Spinner, Stat, Tabs } from "@/components/ui";
import { api } from "@/lib/api";
import { useApp } from "@/lib/app";

const ch = createColumnHelper<any>();
type Tab = "search" | "change" | "controls" | "exceptions" | "report" | "upload";

export default function Compliance() {
  const [tab, setTab] = useState<Tab>("search");
  return (
    <div className="space-y-4">
      <PageHeader title="Regulatory & Risk Intelligence" subtitle="Reference material is illustrative and configurable; applicability to any entity must be determined by Legal/Compliance. The AI does not make legal or regulatory determinations." />
      <Tabs value={tab} onChange={setTab} tabs={[{ id: "search", label: "Policy search" }, { id: "change", label: "Regulatory change comparison" }, { id: "controls", label: "Control mapping" },
        { id: "exceptions", label: "Exception management" }, { id: "report", label: "Audit report" }, { id: "upload", label: "Ingest document" }]} />
      {tab === "search" && <PolicySearch />}{tab === "change" && <Change />}{tab === "controls" && <Controls />}
      {tab === "exceptions" && <Exceptions />}{tab === "report" && <Report />}{tab === "upload" && <Upload />}
    </div>
  );
}

function PolicySearch() {
  const [q, setQ] = useState("What approvals are required for AI-drafted client communications?");
  const m = useMutation({ mutationFn: () => api("/api/ask", { method: "POST", json: { question: q } }) });
  return (
    <Card className="space-y-3 p-4">
      <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); m.mutate(); }}><Input value={q} onChange={(e) => setQ(e.target.value)} aria-label="Policy question" /><Button variant="primary" type="submit">Research</Button></form>
      {m.isPending && <Spinner />}{m.error && <ErrorState error={m.error} />}
      {m.data && <div className="space-y-2"><p className="whitespace-pre-wrap text-sm">{m.data.text}</p>
        <ol className="text-xs text-muted">{m.data.citations.map((c: any, i: number) => <li key={i}>[{i + 1}] {c.title} v{c.version} — {c.section}</li>)}</ol></div>}
    </Card>
  );
}

function Change() {
  const [ids, setIds] = useState({ old: "DOC-003", new: "DOC-004" });
  const q = useQuery({ queryKey: ["cmp", ids], queryFn: () => api(`/api/docs/compare?old=${ids.old}&new=${ids.new}`) });
  return (
    <Card className="space-y-3 p-4">
      <div className="flex gap-2"><Input value={ids.old} onChange={(e) => setIds({ ...ids, old: e.target.value })} aria-label="Old document id" className="max-w-[140px]" />
        <Input value={ids.new} onChange={(e) => setIds({ ...ids, new: e.target.value })} aria-label="New document id" className="max-w-[140px]" /></div>
      {q.isLoading ? <Spinner /> : q.error ? <ErrorState error={q.error} /> : (
        <div className="space-y-3"><div className="text-sm">{q.data.old.title} v{q.data.old.version} → {q.data.new.title} v{q.data.new.version}</div>
          {q.data.sections.map((s: any) => (
            <div key={s.section} className="rounded-md border border-line p-3"><div className="mb-1 flex items-center gap-2 text-sm font-medium">{s.section}<Badge tone={s.status === "unchanged" ? "neutral" : "warn"}>{s.status}</Badge></div>
              {s.added.map((a: string, i: number) => <p key={`a${i}`} className="text-xs text-pos">+ {a}</p>)}{s.removed.map((a: string, i: number) => <p key={`r${i}`} className="text-xs text-crit">− {a}</p>)}</div>))}
          <p className="text-xs text-muted">{q.data.note}</p></div>)}
    </Card>
  );
}

function Controls() {
  const q = useQuery({ queryKey: ["controls"], queryFn: () => api("/api/compliance/controls") });
  if (q.isLoading) return <Spinner />;
  if (q.error) return <ErrorState error={q.error} />;
  return <div className="space-y-2"><p className="text-xs text-muted">{q.data.note}</p><DataTable label="Controls" data={q.data.controls} columns={[ch.accessor("id", { header: "Control" }), ch.accessor("name", { header: "Name" }),
    ch.accessor("domain", { header: "Domain" }), ch.accessor("framework_refs", { header: "Reference mapping", cell: (c) => c.getValue().join("; ") }), ch.accessor("frequency", { header: "Frequency" }),
    ch.accessor("events_total", { header: "Exceptions" }), ch.accessor("events_open", { header: "Open" }), ch.accessor("events_high", { header: "High/critical" })]} /></div>;
}

function Exceptions() {
  const { can } = useApp();
  const qc = useQueryClient();
  const [sel, setSel] = useState<string | null>(null);
  const q = useQuery({ queryKey: ["events"], queryFn: () => api("/api/compliance/events") });
  const ev = useQuery({ queryKey: ["evidence", sel], queryFn: () => api(`/api/compliance/events/${sel}/evidence`), enabled: !!sel });
  const upd = useMutation({ mutationFn: (status: string) => api(`/api/compliance/events/${sel}/status`, { method: "POST", json: { status, note: "Updated from FLO compliance workspace" } }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["events"] }); qc.invalidateQueries({ queryKey: ["evidence"] }); } });
  if (q.isLoading) return <Spinner />;
  if (q.error) return <ErrorState error={q.error} />;
  return (
    <div className="grid gap-4 xl:grid-cols-[1.4fr_1fr]">
      <DataTable label="Compliance exceptions" data={q.data.events} onRowClick={(r: any) => setSel(r.id)} columns={[ch.accessor("id", { header: "ID" }), ch.accessor("event_type", { header: "Type" }),
        ch.accessor("severity", { header: "Severity", cell: (c) => <Badge tone={["high", "critical"].includes(c.getValue()) ? "crit" : "warn"}>{c.getValue()}</Badge> }),
        ch.accessor("status", { header: "Status" }), ch.accessor("control_id", { header: "Control" }), ch.accessor("opened_at", { header: "Opened" }), ch.accessor("business_unit", { header: "Unit" })]} />
      {sel && <Card className="space-y-2 p-4">{ev.isLoading ? <Spinner /> : ev.error ? <ErrorState error={ev.error} /> : (<>
        <h3 className="font-semibold">{ev.data.event.id} · {ev.data.event.event_type}</h3><p className="text-sm">{ev.data.event.description}</p>
        <div className="text-xs">Control {ev.data.control.id}: {ev.data.control.name} ({ev.data.control.framework_refs.join("; ")})</div>
        {can("compliance:write") && <div className="flex items-center gap-2"><Label>Status</Label><Select value={ev.data.event.status} onChange={(e) => upd.mutate(e.target.value)} aria-label="Exception status">
          <option value="open">open</option><option value="in_review">in review</option><option value="closed">closed</option></Select></div>}
        <div className="text-xs font-semibold">Related policies</div><ul className="text-xs">{ev.data.related_policies.map((p: any, i: number) => <li key={i}>{p.title} — {p.section}</li>)}</ul>
        <div className="text-xs font-semibold">Audit trail</div><ul className="text-xs text-muted">{ev.data.audit_trail.map((a: any, i: number) => <li key={i}>{a.ts.slice(0, 19)} {a.actor} {a.action} {JSON.stringify(a.details)}</li>)}</ul>
        <div className="text-[11px] text-muted">Evidence collected {ev.data.collected_at}</div></>)}</Card>}
    </div>
  );
}

function Report() {
  const q = useQuery({ queryKey: ["creport"], queryFn: () => api("/api/compliance/report") });
  if (q.isLoading) return <Spinner />;
  if (q.error) return <ErrorState error={q.error} />;
  const r = q.data;
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Audit chain" value={r.audit_chain.valid ? "Valid" : "BROKEN"} tone={r.audit_chain.valid ? "good" : "crit"} sub={`${r.audit_chain.events_checked} events verified`} />
        <Stat label="Open exceptions" value={r.exceptions.open} sub={`of ${r.exceptions.total}`} />
        <Stat label="Approvals executed" value={r.approvals.executed} sub={`${r.approvals.pending} pending · ${r.approvals.invalidated} invalidated`} />
        <Stat label="Policy version" value={<span className="text-base">{r.policy_version}</span>} />
      </div>
      <Card className="p-4"><h3 className="mb-2 text-sm font-semibold">Policy decisions by action / outcome</h3>
        <div className="grid grid-cols-2 gap-1 text-xs md:grid-cols-4">{Object.entries(r.policy_decisions).sort().map(([k, v]) => <div key={k}>{k.replace("|", " → ")}: <b>{v as number}</b></div>)}</div>
        <Button size="sm" className="mt-3" onClick={() => { const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([JSON.stringify(r, null, 2)], { type: "application/json" })); a.download = "flo-audit-report.json"; a.click(); }}>Export report (JSON)</Button>
      </Card>
    </div>
  );
}

function Upload() {
  const [file, setFile] = useState<File | null>(null);
  const [meta, setMeta] = useState({ doc_id: "DOC-NEW-001", title: "", classification: "internal", access_groups: "all-staff", doc_type: "policy" });
  const m = useMutation({ mutationFn: () => { const fd = new FormData(); fd.append("file", file!); Object.entries(meta).forEach(([k, v]) => fd.append(k, v)); return api("/api/docs/upload", { method: "POST", body: fd }); } });
  return (
    <Card className="space-y-3 p-4">
      <p className="text-xs text-muted">Pipeline: validation (malware/file checks) → parsing (PDF, DOCX, XLSX, CSV, Markdown) → classification (public docs with PII auto-upgraded) → chunking → injection screening (high severity is quarantined) → embedding → ACL metadata.</p>
      <div className="grid gap-2 md:grid-cols-3">
        {(["doc_id", "title", "access_groups", "doc_type"] as const).map((k) => <div key={k}><Label>{k}</Label><Input value={meta[k]} onChange={(e) => setMeta({ ...meta, [k]: e.target.value })} /></div>)}
        <div><Label>classification</Label><Select value={meta.classification} onChange={(e) => setMeta({ ...meta, classification: e.target.value })}>{["public", "internal", "confidential", "restricted"].map((c) => <option key={c}>{c}</option>)}</Select></div>
        <div><Label>file</Label><input type="file" accept=".pdf,.docx,.xlsx,.csv,.md,.txt" onChange={(e) => setFile(e.target.files?.[0] ?? null)} className="text-xs" /></div>
      </div>
      <Button variant="primary" disabled={!file || !meta.title || m.isPending} onClick={() => m.mutate()}>Ingest</Button>
      {m.error && <ErrorState error={m.error} />}
      {m.data && <div className="text-sm">Ingested {m.data.id}: status <Badge tone={m.data.status === "active" ? "good" : "crit"}>{m.data.status}</Badge> classification {m.data.classification}{m.data.injection_flags.length ? ` · ${m.data.injection_flags.length} injection flag(s)` : ""}</div>}
    </Card>
  );
}
