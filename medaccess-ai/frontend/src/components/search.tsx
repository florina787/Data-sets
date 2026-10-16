import { useEffect, useRef, useState } from "react";

import { endpoints, type FacilityCard, type Recommendation, type WorkflowResult } from "../services/api";
import { Alert, AvailabilityBadge, Pill, fmtAge, fmtDate } from "./ui";

export const SERVICES: { code: string; label: string }[] = [
  { code: "MRI", label: "MRI" }, { code: "CT", label: "CT scan" }, { code: "ULTRASOUND", label: "Ultrasound" },
  { code: "XRAY", label: "X-ray" }, { code: "MAMMOGRAPHY", label: "Mammography" }, { code: "BLOOD_TEST", label: "Blood test" },
  { code: "URINE_TEST", label: "Urine test" }, { code: "LAB_INVESTIGATION", label: "Laboratory investigation" },
  { code: "FAMILY_PHYSICIAN", label: "Family physician" }, { code: "SPECIALIST", label: "Specialist consultation" },
];
export const RADII = [2, 3, 5, 10, 25, 50, 100];
export const serviceLabel = (c: string | null | undefined) => SERVICES.find((s) => s.code === c)?.label ?? c ?? "";

export function ServiceSelector({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <div>
      <label className="label" htmlFor="svc">Healthcare service</label>
      <select id="svc" className="input" value={value} onChange={(e) => onChange(e.target.value)}>
        {SERVICES.map((s) => <option key={s.code} value={s.code}>{s.label}</option>)}
      </select>
    </div>
  );
}

const SUGGESTIONS = ["Toronto", "North York", "Scarborough", "Etobicoke", "Mississauga", "Brampton", "Markham", "Vaughan", "Richmond Hill", "Oakville", "M5V", "M2N", "L3R"];

export function LocationSearch({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <div>
      <label className="label" htmlFor="loc">City or postal code</label>
      <input id="loc" className="input" list="loc-suggestions" value={value} placeholder="e.g. Toronto or M5V"
        autoComplete="off" onChange={(e) => onChange(e.target.value)} maxLength={80} />
      <datalist id="loc-suggestions">{SUGGESTIONS.map((s) => <option key={s} value={s} />)}</datalist>
      <p className="mt-1 text-[11px] text-slate-500">Only the postal area (first 3 characters) is used.</p>
    </div>
  );
}

export function RadiusSlider({ value, onChange }: { value: number; onChange: (v: number) => void }) {
  const idx = Math.max(0, RADII.indexOf(value));
  return (
    <div>
      <label className="label" htmlFor="radius">Search radius: <span className="text-brand">{value} km</span></label>
      <input id="radius" type="range" min={0} max={RADII.length - 1} step={1} value={idx} className="w-full accent-brand"
        aria-valuetext={`${value} kilometres`} onChange={(e) => onChange(RADII[Number(e.target.value)])} />
      <div className="flex justify-between text-[10px] text-slate-500">{RADII.map((r) => <span key={r}>{r}</span>)}</div>
    </div>
  );
}

export interface SearchFormValue {
  service: string;
  location: string;
  radius_km: number;
  existing_appointment_days: string;
  requisition_status: string;
  include_private_pay: boolean;
  needs_wheelchair_access: boolean;
  prefer_transit: boolean;
}

export const defaultForm = (service = "MRI"): SearchFormValue => ({
  service, location: "Toronto", radius_km: 25, existing_appointment_days: service === "MRI" ? "90" : "",
  requisition_status: "HAS_REQUISITION", include_private_pay: false, needs_wheelchair_access: false, prefer_transit: false,
});

export function SearchForm({ value, onChange, onSubmit, busy, compact = false }: { value: SearchFormValue; onChange: (v: SearchFormValue) => void; onSubmit: () => void; busy: boolean; compact?: boolean }) {
  const set = (patch: Partial<SearchFormValue>) => onChange({ ...value, ...patch });
  return (
    <form className="grid gap-4" onSubmit={(e) => { e.preventDefault(); onSubmit(); }} aria-label="Appointment search">
      <div className={`grid gap-4 ${compact ? "md:grid-cols-2 xl:grid-cols-4" : "md:grid-cols-2"}`}>
        <ServiceSelector value={value.service} onChange={(service) => set({ service })} />
        <LocationSearch value={value.location} onChange={(location) => set({ location })} />
        <RadiusSlider value={value.radius_km} onChange={(radius_km) => set({ radius_km })} />
        <div>
          <label className="label" htmlFor="existing">Current appointment (days away)</label>
          <input id="existing" className="input" inputMode="numeric" pattern="[0-9]*" placeholder="optional, e.g. 90"
            value={value.existing_appointment_days} onChange={(e) => set({ existing_appointment_days: e.target.value.replace(/\D/g, "").slice(0, 3) })} />
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-sm">
        <label className="flex items-center gap-2">
          <span className="font-medium">Requisition / referral:</span>
          <select className="input w-auto py-1" value={value.requisition_status} onChange={(e) => set({ requisition_status: e.target.value })} aria-label="Requisition status">
            <option value="HAS_REQUISITION">I have one</option>
            <option value="NO_REQUISITION">Not yet</option>
            <option value="UNKNOWN">Not sure</option>
          </select>
        </label>
        <label className="flex items-center gap-2"><input type="checkbox" checked={value.needs_wheelchair_access} onChange={(e) => set({ needs_wheelchair_access: e.target.checked })} /> Wheelchair access</label>
        <label className="flex items-center gap-2"><input type="checkbox" checked={value.prefer_transit} onChange={(e) => set({ prefer_transit: e.target.checked })} /> Prefer transit</label>
        <label className="flex items-center gap-2"><input type="checkbox" checked={value.include_private_pay} onChange={(e) => set({ include_private_pay: e.target.checked })} /> Include private-pay</label>
        <button type="submit" className="btn-primary ml-auto" disabled={busy || !value.location.trim()}>
          {busy ? "Searching…" : "Search appointments"}
        </button>
      </div>
    </form>
  );
}

export function formToParams(v: SearchFormValue, scenario: string | null) {
  return {
    service: v.service, location: v.location, radius_km: v.radius_km,
    existing_appointment_days: v.existing_appointment_days ? Number(v.existing_appointment_days) : null,
    requisition_status: v.requisition_status, include_private_pay: v.include_private_pay,
    needs_wheelchair_access: v.needs_wheelchair_access, prefer_transit: v.prefer_transit, scenario: scenario || null,
  };
}

export function VerificationDetails({ rec }: { rec: Recommendation }) {
  return (
    <details className="mt-2 text-xs text-slate-600">
      <summary className="cursor-pointer font-semibold text-brand">Verification details</summary>
      <dl className="mt-1 grid grid-cols-[auto,1fr] gap-x-3 gap-y-0.5">
        <dt>Source</dt><dd>{rec.source_id} {rec.is_synthetic && <Pill tone="slate">synthetic feed</Pill>}</dd>
        <dt>Last verified</dt><dd>{fmtDate(rec.last_verified_at)} ({fmtAge(rec.last_verified_at)})</dd>
        <dt>Status</dt><dd>{rec.verification_status}</dd>
        <dt>Eligibility</dt><dd>{rec.eligibility_status}</dd>
        <dt>Slot</dt><dd className="font-mono">{rec.slot_id}</dd>
      </dl>
    </details>
  );
}

export function AppointmentCard({ rec, onBook, highlight }: { rec: Recommendation; onBook?: (r: Recommendation) => void; highlight?: boolean }) {
  const confirmed = rec.tier === "CONFIRMED_ALTERNATIVE";
  return (
    <article className={`rounded-2xl border p-4 ${confirmed ? "border-green-200 bg-white" : "border-amber-200 bg-amber-50/40"} ${highlight ? "ring-2 ring-teal" : ""}`} aria-label={`${rec.facility_name}, ${rec.days_until} days away`}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <div className="text-xs font-semibold text-slate-500">#{rec.rank} · {confirmed ? "Verified alternative" : "Unverified possibility"}</div>
          <h3 className="font-semibold text-ink">{rec.facility_name}</h3>
          <div className="text-sm text-slate-600">{fmtDate(rec.start_local)} · {rec.straight_km.toFixed(1)} km · ~{rec.est_driving_minutes} min drive (est.)</div>
        </div>
        <div className="text-right">
          <div className={`text-2xl font-bold ${confirmed ? "text-ok" : "text-[#9A4500]"}`}>{rec.days_until}<span className="text-sm font-medium"> days</span></div>
          {!!rec.days_saved && confirmed && <div className="text-xs font-semibold text-teal">{rec.days_saved} days sooner</div>}
        </div>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <AvailabilityBadge status={rec.verification_status} simulated={rec.is_synthetic} />
        {rec.eligibility_status === "ELIGIBLE_WITH_CONDITIONS" && <Pill tone="warn">Conditions apply</Pill>}
        {!confirmed && <Pill tone="warn">NOT CONFIRMED — contact provider</Pill>}
      </div>
      <VerificationDetails rec={rec} />
      {onBook && (
        <div className="mt-3 flex justify-end">
          <button className="btn-teal" onClick={() => onBook(rec)}>{rec.booking_capability === "online_handoff" ? "Prepare booking handoff" : "Get contact instructions"}</button>
        </div>
      )}
    </article>
  );
}

export function WaitTimeComparison({ result }: { result: WorkflowResult }) {
  const ws = result.wait_summary;
  const rows = [...result.recommendations].sort((a, b) => (a.days_until ?? 999) - (b.days_until ?? 999)).slice(0, 8);
  const max = Math.max(ws.existing_wait_days ?? 0, ...rows.map((r) => r.days_until ?? 0), 1);
  return (
    <div>
      <table className="w-full text-sm">
        <caption className="sr-only">Wait time comparison</caption>
        <thead><tr className="text-left text-xs uppercase text-slate-500"><th className="py-1">Centre</th><th>Distance</th><th className="w-1/3">Next slot</th><th>Status</th></tr></thead>
        <tbody>
          {ws.existing_wait_days != null && (
            <tr className="border-t border-slate-100">
              <td className="py-2 font-medium">Your current appointment</td><td>—</td>
              <td><Bar days={ws.existing_wait_days} max={max} tone="bg-slate-400" /></td><td><Pill>Existing appointment</Pill></td>
            </tr>
          )}
          {rows.map((r) => (
            <tr key={r.slot_id} className="border-t border-slate-100">
              <td className="py-2 font-medium">{r.facility_name}</td><td>{r.straight_km.toFixed(1)} km</td>
              <td><Bar days={r.days_until ?? 0} max={max} tone={r.tier === "CONFIRMED_ALTERNATIVE" ? "bg-ok" : "bg-warn"} /></td>
              <td><AvailabilityBadge status={r.verification_status} simulated={r.is_synthetic} /></td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-2 text-xs text-slate-500">{ws.basis}</p>
    </div>
  );
}

function Bar({ days, max, tone }: { days: number; max: number; tone: string }) {
  return (
    <div className="flex items-center gap-2">
      <div className="h-2.5 flex-1 rounded-full bg-slate-100"><div className={`h-2.5 rounded-full ${tone}`} style={{ width: `${Math.max(3, (days / max) * 100)}%` }} /></div>
      <span className="w-14 text-right text-xs font-semibold">{days} d</span>
    </div>
  );
}

export function RequisitionChecklist({ cards, service }: { cards: FacilityCard[]; service: string | null }) {
  const needs = cards.filter((c) => c.eligibility && (c.eligibility.actions.length || c.eligibility.status !== "ELIGIBLE"));
  return (
    <div className="space-y-3 text-sm">
      <ul className="list-inside list-disc space-y-1 text-slate-700">
        <li>Have your {service === "SPECIALIST" ? "referral" : "requisition"} ready — providers confirm eligibility directly.</li>
        <li>Some facilities accept only their own network form. Ask your clinician if a new requisition is needed.</li>
        <li>Coverage is never guaranteed by MedAccess AI — confirm costs with the provider.</li>
      </ul>
      {needs.length > 0 && (
        <div>
          <div className="label">Facility-specific conditions</div>
          <ul className="space-y-2">
            {needs.slice(0, 6).map((c) => (
              <li key={c.facility.id} className="rounded-lg border border-slate-200 p-2">
                <div className="font-medium">{c.facility.name} <Pill tone={c.eligibility!.status === "INELIGIBLE" ? "danger" : "warn"}>{c.eligibility!.status}</Pill></div>
                <ul className="ml-4 list-disc text-xs text-slate-600">{[...c.eligibility!.reasons, ...c.eligibility!.actions].map((r, i) => <li key={i}>{r}</li>)}</ul>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export function BookingApprovalModal({ rec, searchWorkflowId, onClose, onDone }: { rec: Recommendation; searchWorkflowId: string; onClose: () => void; onDone?: (r: any) => void }) {
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [pending, setPending] = useState<any>(null);
  const [result, setResult] = useState<any>(null);
  const keyRef = useRef(`bk-${searchWorkflowId}-${rec.slot_id}-${Math.random().toString(36).slice(2, 10)}`);
  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    dialogRef.current?.focus();
    const esc = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [onClose]);

  const request = async () => {
    setBusy(true); setErr(null);
    try {
      const r: any = await endpoints.requestBooking({ search_workflow_id: searchWorkflowId, slot_id: rec.slot_id, idempotency_key: keyRef.current, consent: true });
      if (!r.approval_id) setErr((r.errors || []).join(" ") || "The booking handoff could not be prepared.");
      setPending(r);
    } catch (e) { setErr(e instanceof Error ? e.message : String(e)); } finally { setBusy(false); }
  };
  const decide = async (decision: "APPROVED" | "REJECTED") => {
    setBusy(true); setErr(null);
    try {
      const r: any = await endpoints.decide(pending.approval_id, { decision });
      setResult(r.workflow); onDone?.(r.workflow);
    } catch (e) { setErr(e instanceof Error ? e.message : String(e)); } finally { setBusy(false); }
  };
  const handoff = result?.booking?.handoff;
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-ink/40 p-3 sm:items-center" role="presentation" onClick={onClose}>
      <div ref={dialogRef} tabIndex={-1} role="dialog" aria-modal="true" aria-labelledby="bk-title" className="card max-h-[92vh] w-full max-w-lg overflow-auto p-5 outline-none" onClick={(e) => e.stopPropagation()}>
        <h2 id="bk-title" className="h2">Booking handoff — your approval is required</h2>
        <p className="muted mt-1">MedAccess AI does not book appointments. With your approval it prepares the provider's official booking instructions. Nothing is sent to the provider.</p>
        <div className="mt-3 rounded-xl bg-canvas p-3 text-sm">
          <div className="font-semibold">{rec.facility_name}</div>
          <div>{fmtDate(rec.start_local)} · {rec.straight_km.toFixed(1)} km</div>
          <div className="mt-1"><AvailabilityBadge status={rec.verification_status} simulated={rec.is_synthetic} /></div>
        </div>
        {err && <div className="mt-3"><Alert tone="danger">{err}</Alert></div>}
        {!pending && (
          <>
            <label className="mt-4 flex items-start gap-2 text-sm">
              <input type="checkbox" className="mt-1" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
              <span>I consent to MedAccess AI preparing booking instructions for this opening. I understand the appointment is not confirmed until the provider confirms it.</span>
            </label>
            <div className="mt-4 flex justify-end gap-2">
              <button className="btn-ghost" onClick={onClose}>Cancel</button>
              <button className="btn-primary" disabled={!consent || busy} onClick={request}>{busy ? "Preparing…" : "Continue"}</button>
            </div>
          </>
        )}
        {pending?.approval_id && !result && (
          <div className="mt-4 space-y-3">
            <Alert tone="info" title="Approval request">
              <div>Requested action: prepare booking handoff · Requesting agent: Booking Assistance Agent</div>
              <ul className="ml-4 mt-1 list-disc text-xs"><li>Instructions will be prepared for you</li><li>No information is sent to the provider</li><li>The appointment is NOT booked until the provider confirms it</li></ul>
            </Alert>
            <div className="flex justify-end gap-2">
              <button className="btn-danger" disabled={busy} onClick={() => decide("REJECTED")}>Reject</button>
              <button className="btn-teal" disabled={busy} onClick={() => decide("APPROVED")}>Approve</button>
            </div>
          </div>
        )}
        {result && (
          <div className="mt-4 space-y-3">
            {handoff ? (
              <Alert tone="ok" title="Handoff ready — NOT CONFIRMED">
                <ol className="ml-4 list-decimal space-y-1">{handoff.steps.map((s: string, i: number) => <li key={i}>{s}</li>)}</ol>
                <p className="mt-2 text-xs">{handoff.disclaimer}</p>
              </Alert>
            ) : (
              <Alert tone="warn">Request {result.workflow_status?.toLowerCase()}. Nothing was prepared or shared.</Alert>
            )}
            <div className="flex justify-end"><button className="btn-primary" onClick={onClose}>Close</button></div>
          </div>
        )}
      </div>
    </div>
  );
}
