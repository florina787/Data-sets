import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { AgentActivityPanel, LangGraphVisualizer } from "../components/agents";
import { ChristinaChatPanel } from "../components/ChristinaChatPanel";
import { FacilityMap } from "../components/FacilityMap";
import {
  AppointmentCard, BookingApprovalModal, RequisitionChecklist, SERVICES, SearchForm, WaitTimeComparison,
  defaultForm, formToParams, serviceLabel, type SearchFormValue,
} from "../components/search";
import { Alert, Card, DemoBanner, Empty, ErrorText, PageHeader, Pill, Spinner, Stat, fmtDate } from "../components/ui";
import { useApp } from "../hooks/AppContext";
import { useAsync } from "../hooks/useAsync";
import { endpoints, type Recommendation, type WorkflowResult } from "../services/api";

function useRunSearch() {
  const { setLastSearch, scenario } = useApp();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const run = async (v: SearchFormValue) => {
    setBusy(true); setError(null);
    try {
      const r = await endpoints.search(formToParams(v, scenario));
      setLastSearch(r);
      return r;
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); return null; } finally { setBusy(false); }
  };
  return { run, busy, error };
}

function ExpansionPrompt({ result }: { result: WorkflowResult }) {
  const { setLastSearch } = useApp();
  const [busy, setBusy] = useState(false);
  const q = result.pending_question;
  if (!q || q.type !== "SEARCH_RADIUS_EXPANSION") return null;
  const decide = async (radius: number | null) => {
    setBusy(true);
    try {
      const r: any = await endpoints.decide(q.approval_id, radius ? { decision: "APPROVED", radius_km: radius } : { decision: "REJECTED" });
      if (r.workflow) setLastSearch(r.workflow);
    } finally { setBusy(false); }
  };
  return (
    <Alert tone="info" title="No verified appointment in this radius — expand the search?">
      <p className="mb-2">The workflow is paused for your approval (Human Approval Agent). Facility counts below are directory counts, not availability.</p>
      <div className="flex flex-wrap gap-2">
        {q.options?.map((o) => <button key={o.radius_km} className="btn-primary px-3 py-1" disabled={busy} onClick={() => void decide(o.radius_km)}>Search {o.radius_km} km ({o.facilities_offering_service} facilities)</button>)}
        <button className="btn-ghost px-3 py-1" disabled={busy} onClick={() => void decide(null)}>No thanks</button>
      </div>
    </Alert>
  );
}

export function SearchResults({ result }: { result: WorkflowResult }) {
  const { reducedMotion } = useApp();
  const [booking, setBooking] = useState<Recommendation | null>(null);
  const [highlight, setHighlight] = useState<string | null>(null);
  if (result.workflow_status === "SAFETY_INTERRUPTED") {
    return <Alert tone="danger" title="Routine search paused for your safety">{result.explanation}</Alert>;
  }
  if (result.workflow_status === "NEEDS_INPUT") {
    return <Alert tone="warn">More information is needed: {result.missing_fields.join(", ")}. Try a GTA city or postal code such as “Toronto” or “M5V”.</Alert>;
  }
  const confirmed = result.recommendations.filter((r) => r.tier === "CONFIRMED_ALTERNATIVE");
  const unverified = result.recommendations.filter((r) => r.tier !== "CONFIRMED_ALTERNATIVE");
  const ws = result.wait_summary;
  return (
    <div className="space-y-5">
      {result.notice && <DemoBanner />}
      <ExpansionPrompt result={result} />
      {result.unavailable_sources.length > 0 && <Alert tone="warn" title="An availability source is unreachable">{result.unavailable_sources.join(", ")} failed after bounded retries (Recovery Agent). Affected facilities show contact details only, marked UNKNOWN.</Alert>}
      {result.errors.length > 0 && <ErrorText error={result.errors.join(" · ")} />}
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Stat label="Verified alternatives" value={ws.confirmed_count} tone="ok" />
        <Stat label="Unverified possibilities" value={ws.unverified_count} tone="warn" hint="need provider contact" />
        <Stat label="Earliest verified" value={ws.best_confirmed_days != null ? `${ws.best_confirmed_days} days` : "—"} />
        <Stat label="Potential days saved" value={ws.potential_days_saved ?? "—"} tone="teal" hint={ws.existing_wait_days != null ? `vs. ${ws.existing_wait_days}-day current wait` : "no current appointment given"} />
      </div>
      {result.explanation && <Card><p className="text-sm">{result.explanation}</p><p className="mt-2 text-xs text-slate-500">Build {result.build_version} · workflow {result.workflow_id} · {result.duration_ms} ms · trace {result.trace_id?.slice(0, 12) ?? "—"}</p></Card>}
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)]">
        <div className="space-y-5">
          <Card title="Verified alternatives">
            {confirmed.length ? <div className="space-y-3">{confirmed.map((r) => <AppointmentCard key={r.slot_id} rec={r} highlight={highlight === r.facility_id} onBook={setBooking} />)}</div> : <Empty>No verified openings. See unverified possibilities below or expand the radius.</Empty>}
          </Card>
          <Card title={<span>Unverified possibilities <Pill tone="warn">not confirmed</Pill></span>}>
            {unverified.length ? <div className="space-y-3">{unverified.map((r) => <AppointmentCard key={r.slot_id} rec={r} highlight={highlight === r.facility_id} onBook={setBooking} />)}</div> : <Empty>None.</Empty>}
          </Card>
          <Card title="Wait-time comparison"><WaitTimeComparison result={result} /></Card>
        </div>
        <div className="space-y-5">
          <Card title="Interactive map">
            <FacilityMap cards={result.facility_cards} center={result.latitude != null ? { lat: result.latitude, lon: result.longitude! } : null} radiusKm={result.radius_km} highlightId={highlight} onSelect={setHighlight} />
          </Card>
          <Card title="Agent workflow"><LangGraphVisualizer trace={result.agent_trace} reducedMotion={reducedMotion} /></Card>
          <Card title="Requisition checklist"><RequisitionChecklist cards={result.facility_cards} service={result.requested_service} /></Card>
          <Card title="Sources">
            <ul className="space-y-1 text-xs">{result.source_references.map((s, i) => <li key={i}><Pill>{s.kind}</Pill> {s.title}</li>)}</ul>
          </Card>
        </div>
      </div>
      {booking && <BookingApprovalModal rec={booking} searchWorkflowId={result.workflow_id} onClose={() => setBooking(null)} />}
    </div>
  );
}

export function SearchPage() {
  const { service } = useParams();
  const { lastSearch } = useApp();
  const [form, setForm] = useState<SearchFormValue>(defaultForm(service || "MRI"));
  const { run, busy, error } = useRunSearch();
  useEffect(() => { if (service) setForm((f) => ({ ...defaultForm(service), location: f.location })); }, [service]);
  const label = service ? serviceLabel(service) : "Healthcare Services";
  const show = lastSearch && (!service || lastSearch.requested_service === service) ? lastSearch : null;
  return (
    <div>
      <PageHeader title={service ? `${label} — find earlier options` : "Find Healthcare Services"} subtitle="Search participating facilities, compare verified openings with unverified possibilities and check requisition requirements." />
      <Card className="mb-5"><SearchForm value={form} onChange={setForm} onSubmit={() => void run(form)} busy={busy} compact /></Card>
      <ErrorText error={error} />
      {busy && <Spinner label="Agents are searching, verifying and ranking…" />}
      {show ? <SearchResults result={show} /> : !busy && <Empty>Choose a service and location to start. Results include the source and last verification time for every opening.</Empty>}
    </div>
  );
}

export function DashboardPage() {
  const { data, error } = useAsync(() => endpoints.dashboard(), []);
  const { lastSearch } = useApp();
  const [form, setForm] = useState<SearchFormValue>(defaultForm());
  const { run, busy, error: sErr } = useRunSearch();
  return (
    <div className="space-y-5">
      <PageHeader title="Dashboard" subtitle="Smarter healthcare access. Shorter waits. Better choices." />
      <DemoBanner />
      <ErrorText error={error} />
      {data && (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          <Stat label="Participating facilities" value={data.participating_facilities} hint="fictional demo facilities" />
          <Stat label="Verified available appointments" value={data.verified_available_appointments} tone="ok" hint={`build ${data.build_version}`} />
          <Stat label="Observed wait (MRI, median)" value={data.observed_wait_days_median_by_service.MRI ? `${data.observed_wait_days_median_by_service.MRI.median_days} d` : "—"} hint={data.observed_wait_days_median_by_service.MRI ? `n=${data.observed_wait_days_median_by_service.MRI.n}, synthetic — not representative` : undefined} />
          <Stat label="Potential days saved" value={data.potential_days_saved.mean != null ? Math.round(data.potential_days_saved.mean) : "—"} tone="teal" hint={`mean of ${data.potential_days_saved.searches_with_savings} searches this session`} />
          <Stat label="Active searches" value={data.active_searches} />
        </div>
      )}
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
        <div className="space-y-5">
          <Card title="Search for an earlier appointment">
            <SearchForm value={form} onChange={setForm} onSubmit={() => void run(form)} busy={busy} />
            <ErrorText error={sErr} />
          </Card>
          {lastSearch ? (
            <>
              <Card title="Interactive GTA map">
                <FacilityMap cards={lastSearch.facility_cards} center={lastSearch.latitude != null ? { lat: lastSearch.latitude, lon: lastSearch.longitude! } : null} radiusKm={lastSearch.radius_km} />
              </Card>
              <Card title="Appointment comparison" actions={<Link className="text-sm font-semibold text-brand" to="/search">Full results →</Link>}>
                <WaitTimeComparison result={lastSearch} />
              </Card>
              <Card title="AI recommendations"><p className="text-sm">{lastSearch.explanation}</p>
                <div className="mt-3 space-y-2">{lastSearch.recommendations.slice(0, 3).map((r) => <AppointmentCard key={r.slot_id} rec={r} />)}</div>
              </Card>
            </>
          ) : <Empty>Run a search or ask Christina to see the map, comparison and AI recommendations here.</Empty>}
        </div>
        <Card><ChristinaChatPanel /></Card>
      </div>
    </div>
  );
}

export function ChristinaPage() {
  const { lastSearch, reducedMotion } = useApp();
  return (
    <div>
      <PageHeader title="Ask Christina" subtitle="Your virtual healthcare access assistant. Christina helps with appointment logistics and administrative questions — not medical assessment." />
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <Card><ChristinaChatPanel tall /></Card>
        <Card title="Live agent workflow">{lastSearch ? <LangGraphVisualizer trace={lastSearch.agent_trace} reducedMotion={reducedMotion} /> : <p className="muted">When Christina runs a search, each agent lights up here.</p>}</Card>
      </div>
    </div>
  );
}

export function FacilitiesPage() {
  const [svc, setSvc] = useState("");
  const { data, error, loading } = useAsync(() => endpoints.facilities(`?limit=200${svc ? `&service=${svc}` : ""}`), [svc]);
  return (
    <div>
      <PageHeader title="Nearby Facilities" subtitle="Directory of participating facilities (fictional demonstration data)." actions={
        <select className="input w-56" value={svc} onChange={(e) => setSvc(e.target.value)} aria-label="Filter by service"><option value="">All services</option>{SERVICES.map((s) => <option key={s.code} value={s.code}>{s.label}</option>)}</select>} />
      <DemoBanner text="FICTIONAL DEMONSTRATION FACILITIES — phone numbers and links are not real" />
      <ErrorText error={error} />
      {loading ? <Spinner /> : (
        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {data?.items.map((f: any) => (
            <article key={f.id} className="card p-4 text-sm">
              <div className="font-semibold">{f.name}</div>
              <div className="text-slate-600">{f.neighbourhood}, {f.city} · {f.phone}</div>
              <div className="mt-1 flex flex-wrap gap-1">{f.services.map((s: string) => <Pill key={s} tone="brand">{serviceLabel(s)}</Pill>)}</div>
              <div className="mt-1 flex flex-wrap gap-1 text-xs">
                <Pill tone={f.funding === "private_pay_demo" ? "warn" : "teal"}>{f.funding === "private_pay_demo" ? "private-pay" : "may be publicly covered"}</Pill>
                {f.wheelchair_accessible && <Pill>♿ accessible</Pill>}<Pill>{f.booking_capability.replace("_", " ")}</Pill><Pill>source {f.integration_id}</Pill>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}

export function MapPage() {
  const { lastSearch } = useApp();
  return (
    <div>
      <PageHeader title="Interactive Map" subtitle="Facilities from your latest search, coloured by verification status." />
      {lastSearch ? <Card><FacilityMap cards={lastSearch.facility_cards} center={lastSearch.latitude != null ? { lat: lastSearch.latitude, lon: lastSearch.longitude! } : null} radiusKm={lastSearch.radius_km} /></Card>
        : <Empty>Run a search first (<Link className="text-brand underline" to="/search">Find Healthcare Services</Link>).</Empty>}
    </div>
  );
}

export function ComparePage() {
  const { lastSearch } = useApp();
  const { data } = useAsync(() => endpoints.dashboard(), []);
  return (
    <div className="space-y-5">
      <PageHeader title="Compare Wait Times" />
      {lastSearch ? <Card title={`Your latest search: ${serviceLabel(lastSearch.requested_service)} near ${lastSearch.search_location}`}><WaitTimeComparison result={lastSearch} /></Card> : <Empty>Run a search to compare options.</Empty>}
      {data && (
        <Card title="Next verified slot by service (synthetic dataset)">
          <table className="w-full text-sm"><thead><tr className="text-left text-xs uppercase text-slate-500"><th>Service</th><th>Median days</th><th>Sample size</th></tr></thead>
            <tbody>{Object.entries(data.observed_wait_days_median_by_service).map(([k, v]: any) => <tr key={k} className="border-t border-slate-100"><td className="py-1.5">{v.label}</td><td>{v.median_days}</td><td>{v.n}</td></tr>)}</tbody></table>
          <p className="mt-2 text-xs text-slate-500">{data.wait_time_qualification}</p>
        </Card>
      )}
    </div>
  );
}

export function TrackerPage() {
  const { data, reload, error } = useAsync(() => endpoints.bookings(), []);
  return (
    <div>
      <PageHeader title="Appointment Tracker" subtitle="Booking handoffs you approved. A handoff is not a booking — status changes to confirmed only from a verifiable provider confirmation." />
      <ErrorText error={error} />
      {!data?.items.length ? <Empty>No booking handoffs yet.</Empty> : (
        <div className="space-y-3">
          {data.items.map((b: any) => (
            <Card key={b.id} title={<span>{b.handoff?.facility_name ?? b.facility_id} <Pill tone={b.is_confirmed_booking ? "ok" : "warn"}>{b.status}</Pill></span>}>
              <div className="text-sm">{fmtDate(b.handoff?.slot_local)} · created {fmtDate(b.created_at)}</div>
              {b.handoff?.steps && <ol className="ml-5 mt-2 list-decimal text-sm">{b.handoff.steps.map((s: string, i: number) => <li key={i}>{s}</li>)}</ol>}
              {b.status === "HANDOFF_PREPARED" && <button className="btn-ghost mt-3" onClick={async () => { await endpoints.patientReported(b.id); void reload(); }}>I booked this with the provider</button>}
              {b.status === "PATIENT_REPORTED_BOOKED" && <p className="mt-2 text-xs text-slate-500">Self-reported by you — not verified by the provider.</p>}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

export function NotificationsPage() {
  const { data, error } = useAsync(() => endpoints.notifications(), []);
  return (
    <div>
      <PageHeader title="Notifications" subtitle="In-app only. Messages never include health details." />
      <ErrorText error={error} />
      {data && <div className="mb-3 flex flex-wrap gap-2 text-xs">{Object.entries(data.channels).map(([k, v]: any) => <Pill key={k} tone={v === "implemented" ? "ok" : "slate"}>{k}: {v}</Pill>)}</div>}
      {!data?.items.length ? <Empty>No notifications. Enable notification consent in Patient Preferences.</Empty> : <ul className="space-y-2">{data.items.map((n: any) => <li key={n.id} className="card p-3 text-sm"><b>{n.title}</b> — {n.body}<div className="text-xs text-slate-500">{fmtDate(n.created_at)}</div></li>)}</ul>}
    </div>
  );
}

export function HistoryPage({ saved = false }: { saved?: boolean }) {
  const { data, reload } = useAsync(() => endpoints.history(saved), [saved]);
  return (
    <div>
      <PageHeader title={saved ? "Saved Searches" : "Search History"} subtitle="Only service, coarse location and radius are stored — never your messages." />
      {!data?.items.length ? <Empty>Nothing here yet.</Empty> : (
        <table className="card w-full overflow-hidden text-sm"><thead className="bg-canvas text-left text-xs uppercase text-slate-500"><tr><th className="p-2">When</th><th>Service</th><th>Location</th><th>Radius</th><th>Status</th><th /></tr></thead>
          <tbody>{data.items.map((h: any) => (
            <tr key={h.id} className="border-t border-slate-100"><td className="p-2">{fmtDate(h.created_at)}</td><td>{serviceLabel(h.service)}</td><td>{h.location}</td><td>{h.radius_km} km</td><td><Pill>{h.status}</Pill></td>
              <td>{!h.saved && <button className="text-xs font-semibold text-brand" onClick={async () => { await endpoints.saveSearch(h.id); void reload(); }}>Save</button>}</td></tr>))}
          </tbody></table>
      )}
    </div>
  );
}

export function RequisitionPage() {
  const { lastSearch } = useApp();
  const { data } = useAsync(() => endpoints.knowledgeDocs(), []);
  return (
    <div className="space-y-5">
      <PageHeader title="Requisition Checklist" subtitle="Administrative guidance from the approved knowledge base. MedAccess AI cannot issue requisitions or guarantee coverage." />
      <Card title="Before you contact a provider"><RequisitionChecklist cards={lastSearch?.facility_cards ?? []} service={lastSearch?.requested_service ?? null} /></Card>
      {data && <Card title={`Knowledge base (version ${data.kb_version})`}>
        <ul className="space-y-2 text-sm">{data.documents.map((d: any) => <li key={d.document_id}><b>{d.title}</b> <span className="text-xs text-slate-500">{d.provider} · v{d.version} · retrieved {d.retrieval_date}</span> {d.stale && <Pill tone="warn">review overdue</Pill>} {d.access_classification === "synthetic_demo" && <Pill>fictional</Pill>}</li>)}</ul>
      </Card>}
    </div>
  );
}

export function PreferencesPage() {
  const { data, setData } = useAsync(() => endpoints.prefs(), []);
  const consents = useAsync(() => endpoints.consents(), []);
  const [msg, setMsg] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  if (!data) return <Spinner />;
  const set = (k: string, v: unknown) => setData({ ...data, [k]: v });
  return (
    <div className="space-y-5">
      <PageHeader title="Patient Preferences" />
      {msg && <Alert tone="ok">{msg}</Alert>}
      <Card title="Search defaults">
        <div className="grid gap-3 text-sm md:grid-cols-2">
          <label>Default radius <select className="input" value={data.default_radius_km} onChange={(e) => set("default_radius_km", Number(e.target.value))}>{[2, 3, 5, 10, 25, 50, 100].map((r) => <option key={r} value={r}>{r} km</option>)}</select></label>
          <label>Language <select className="input" value={data.language} onChange={(e) => set("language", e.target.value)}><option value="en-CA">English (Canada)</option><option value="fr-CA">Français (Canada) — UI translation planned</option></select></label>
          {["prefer_transit", "needs_wheelchair_access", "include_private_pay", "notifications_in_app"].map((k) => (
            <label key={k} className="flex items-center gap-2"><input type="checkbox" checked={!!data[k]} onChange={(e) => set(k, e.target.checked)} />{k.replace(/_/g, " ")}</label>
          ))}
        </div>
        <button className="btn-primary mt-4" onClick={async () => { await endpoints.savePrefs(data); setMsg("Preferences saved."); }}>Save preferences</button>
      </Card>
      <Card title="Consent">
        <div className="space-y-2 text-sm">
          {["notifications", "voice", "data_sharing"].map((c) => {
            const cur = consents.data?.[c]?.granted;
            return <div key={c} className="flex items-center justify-between gap-2"><span>{c.replace("_", " ")}: <b>{cur ? "granted" : "not granted"}</b></span>
              <button className="btn-ghost px-3 py-1" onClick={async () => { await endpoints.setConsent(c, !cur); void consents.reload(); }}>{cur ? "Revoke" : "Grant"}</button></div>;
          })}
        </div>
      </Card>
      <Card title="Delete my data">
        <p className="muted">Removes your search history, booking handoffs, consents and notifications. The redacted audit trail is retained per policy.</p>
        {!confirmDelete ? <button className="btn-danger mt-3" onClick={() => setConfirmDelete(true)}>Delete my data…</button> : (
          <div className="mt-3 flex gap-2"><button className="btn-danger" onClick={async () => { const r: any = await endpoints.deleteMyData(); setMsg(`Deleted: ${JSON.stringify(r.deleted)}`); setConfirmDelete(false); }}>Confirm deletion</button><button className="btn-ghost" onClick={() => setConfirmDelete(false)}>Cancel</button></div>
        )}
      </Card>
    </div>
  );
}

export function AgentActivityPage() {
  const { lastSearch, can } = useApp();
  const metrics = useAsync(() => (can("agents:read") ? endpoints.agentMetrics() : Promise.resolve(null)), []);
  return (
    <div className="space-y-5">
      <PageHeader title="AI Agent Activity" subtitle="Safe, redacted explanations of what each agent did in your latest workflow." />
      <Card title="Latest workflow">{lastSearch ? <AgentActivityPanel trace={lastSearch.agent_trace} /> : <Empty>No workflow yet.</Empty>}</Card>
      {metrics.data && (
        <Card title="Agent metrics (measured, all workflows)">
          <table className="w-full text-sm"><thead className="text-left text-xs uppercase text-slate-500"><tr><th>Agent</th><th>Executions</th><th>Failures</th><th>Success</th><th>Avg ms</th></tr></thead>
            <tbody>{metrics.data.agents.map((a: any) => <tr key={a.agent} className="border-t border-slate-100"><td className="py-1">{a.agent}</td><td>{a.executions}</td><td>{a.failures}</td><td>{a.success_rate != null ? `${(a.success_rate * 100).toFixed(1)}%` : "—"}</td><td>{a.avg_ms}</td></tr>)}</tbody></table>
        </Card>
      )}
    </div>
  );
}

export function AgentGraphPage() {
  const { lastSearch, reducedMotion } = useApp();
  const g = useAsync(() => endpoints.graph(), []);
  const [Diagram, setDiagram] = useState<null | typeof import("../components/sdlc").ArchitectureDiagram>(null);
  useEffect(() => { void import("../components/sdlc").then((m) => setDiagram(() => m.ArchitectureDiagram)); }, []);
  return (
    <div className="space-y-5">
      <PageHeader title="Agent Workflow Graph" subtitle="The LangGraph StateGraph that orchestrates every search, rendered from the compiled graph." />
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)]">
        <Card title="Latest run">{lastSearch ? <LangGraphVisualizer trace={lastSearch.agent_trace} reducedMotion={reducedMotion} /> : <Empty>Run a search to animate the graph.</Empty>}</Card>
        <Card title="Compiled graph">{g.data && Diagram ? <Diagram code={g.data.mermaid} /> : <Spinner />}
          {g.data && <p className="mt-2 text-xs text-slate-500">{g.data.nodes.length} nodes · {g.data.edges.length} edges ({g.data.edges.filter((e: any) => e.conditional).length} conditional)</p>}
        </Card>
      </div>
    </div>
  );
}

export function SettingsPage() {
  const { reducedMotion, setReducedMotion, voiceEnabled, setVoiceEnabled, scenario, setScenario, can } = useApp();
  return (
    <div className="space-y-5">
      <PageHeader title="Settings" />
      <Card title="Accessibility & voice">
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={reducedMotion} onChange={(e) => setReducedMotion(e.target.checked)} /> Reduce motion (Christina animations off)</label>
        <label className="mt-2 flex items-center gap-2 text-sm"><input type="checkbox" checked={voiceEnabled} onChange={(e) => setVoiceEnabled(e.target.checked)} /> Voice features enabled for this session</label>
      </Card>
      <Card title="Demo scenarios">
        <p className="muted mb-2">Reproducible demonstrations. Scenarios only affect synthetic adapters.</p>
        <div className="flex flex-wrap gap-2">
          {[[null, "Normal"], ["provider_outage", "Provider API failure"], ["provider_flaky", "Flaky provider (retry succeeds)"]].map(([k, l]) => (
            <button key={String(k)} className={scenario === k ? "btn-primary" : "btn-ghost"} onClick={() => setScenario(k)}>{l}</button>
          ))}
        </div>
        <ul className="mt-3 list-inside list-disc text-sm text-slate-600">
          <li>MRI long wait: search MRI · Toronto · 25 km · current appointment 90 days.</li>
          <li>CT earlier appointment: CT · North York · 10 km.</li><li>Blood test nearby: Blood test · M5V · 3 km.</li>
          <li>Specialist expanded radius: Specialist · Toronto · 5 km → approve expansion.</li>
          <li>No eligible appointment: Mammography · Toronto · 2 km.</li><li>Requisition not accepted: compare Lakeshore (network form only) in MRI results.</li>
          {can("sdlc:read") && <li>AI-SDLC defect detection, approvals and anomaly simulation: open the AI-SDLC Command Center.</li>}
        </ul>
      </Card>
      <Card title="About"><p className="text-sm">MedAccess AI prototype. Christina is a virtual AI assistant, not a licensed physician. All facilities and appointments are fictional demonstration data.</p></Card>
    </div>
  );
}
