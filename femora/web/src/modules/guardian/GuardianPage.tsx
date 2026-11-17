import { useState } from "react";
import { Check, Download, MapPin, MessageCircle, Phone, Plus, Printer, ShieldAlert, Smartphone, Trash2, UserPlus } from "lucide-react";
import { useApp } from "../../lib/app-state";
import { uid } from "../../lib/storage";
import { Badge, Button, Card, Field, Notice, PageHeader, inputCls } from "../../components/ui";
import { smsUrl, whatsappUrl } from "../connections/share";
import { CAPABILITIES, checkInMessage, checkInStatus, emergencyCard, emergencyNumber, knownCountry, sosMessage, type EmergencyInfo } from "./logic";
import { useGuardian } from "./useGuardian";

const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

export function GuardianPage() {
  const app = useApp();
  const g = useGuardian();
  const number = emergencyNumber(app.profile.country);
  const trusted = g.contacts.filter((c) => g.guardians.includes(c.id));
  const [loc, setLoc] = useState<{ lat: number; lon: number; accuracy: number } | null>(null);
  const [locState, setLocState] = useState<"idle" | "asking" | "denied">("idle");
  const [sosOpen, setSosOpen] = useState(false);
  const [opened, setOpened] = useState<string[]>([]);
  const [nc, setNc] = useState({ name: "", phone: "", role: "Trusted contact" });
  const [ci, setCi] = useState({ label: "Evening check-in", time: "21:00", graceMin: 30, days: [0, 1, 2, 3, 4, 5, 6] });
  const msg = sosMessage(g.info.fullName || app.profile.name, loc ?? undefined);

  function shareLocation() {
    if (!navigator.geolocation) { setLocState("denied"); return; }
    setLocState("asking");
    navigator.geolocation.getCurrentPosition((p) => { setLoc({ lat: p.coords.latitude, lon: p.coords.longitude, accuracy: p.coords.accuracy }); setLocState("idle"); }, () => setLocState("denied"), { enableHighAccuracy: true, timeout: 10000 });
  }
  const checkIn = (id: string) => g.setLog([...g.log, { checkInId: id, date: new Date().toISOString().slice(0, 10), at: Date.now(), status: "ok" }]);
  function printCard() {
    const w = window.open("", "_blank"); if (!w) return;
    const pre = w.document.createElement("pre"); pre.textContent = emergencyCard(g.info, trusted); pre.style.cssText = "font:16px/1.6 system-ui;white-space:pre-wrap;padding:24px";
    w.document.body.appendChild(pre); w.print();
  }

  return (
    <div>
      <PageHeader title="Guardian" sub="Your safety tools, always one tap away. Muse helps you reach people fast. It never claims a message was delivered when it can't confirm it." />

      <section data-tour="guardian-emergency" aria-label="Emergency" className="rounded-f-lg border-2 border-danger bg-danger/8 p-5 md:p-6">
        <div className="flex flex-wrap items-center gap-3">
          <ShieldAlert className="text-danger" size={28} aria-hidden />
          <h2 className="font-display text-2xl">In an emergency</h2>
          <div className="ml-auto flex flex-wrap gap-3">
            <a href={`tel:${number}`} className="inline-flex items-center gap-2 rounded-full bg-danger px-6 py-3 text-lg font-semibold text-white shadow-f focus-visible:outline-4"><Phone size={20} /> Call {number}</a>
            <button onClick={() => setSosOpen(!sosOpen)} aria-expanded={sosOpen} className="inline-flex items-center gap-2 rounded-full border-2 border-danger bg-surface px-6 py-3 text-lg font-semibold text-danger"><MessageCircle size={20} /> SOS to my people</button>
          </div>
        </div>
        {!knownCountry(app.profile.country) && <p className="mt-2 text-sm">Your country's number isn't in Muse's list; 112 works on many mobile networks. Please confirm your local number.</p>}
        {sosOpen && (
          <div className="mt-4 rounded-f bg-surface p-4">
            <p className="text-sm"><b>Your message:</b> {msg}</p>
            <div className="mt-2 flex flex-wrap items-center gap-2 text-sm">
              {loc ? <Badge tone="good"><MapPin size={12} /> Location added (±{Math.round(loc.accuracy)} m)</Badge> : <Button size="sm" onClick={shareLocation} disabled={locState === "asking"}><MapPin size={14} /> {locState === "asking" ? "Getting location…" : "Add my location to this message"}</Button>}
              {loc && <Button size="sm" variant="ghost" onClick={() => setLoc(null)}>Remove location</Button>}
              {locState === "denied" && <span className="text-warn">Location unavailable or not allowed.</span>}
            </div>
            {trusted.length === 0 ? <p className="mt-3 text-sm">No trusted contacts yet. Add some below, or send from your own apps: <a className="underline" href={smsUrl(undefined, msg)}>SMS</a> · <a className="underline" href={whatsappUrl(msg)} target="_blank" rel="noreferrer">WhatsApp</a></p> : (
              <ul className="mt-3 space-y-2">{trusted.map((c) => (
                <li key={c.id} className="flex flex-wrap items-center gap-2"><b className="w-36">{c.name}</b>
                  {c.phone && <a href={`tel:${c.phone}`} className="inline-flex items-center gap-1 rounded-full bg-surface-2 px-3 py-1.5 text-sm"><Phone size={14} /> Call</a>}
                  {c.phone && <a href={smsUrl(c.phone, msg)} onClick={() => setOpened([...opened, c.id])} className="inline-flex items-center gap-1 rounded-full bg-surface-2 px-3 py-1.5 text-sm"><Smartphone size={14} /> SMS</a>}
                  {c.phone && <a href={whatsappUrl(msg, c.phone)} target="_blank" rel="noreferrer" onClick={() => setOpened([...opened, c.id])} className="inline-flex items-center gap-1 rounded-full bg-surface-2 px-3 py-1.5 text-sm"><MessageCircle size={14} /> WhatsApp</a>}
                  {opened.includes(c.id) && <span className="text-xs text-muted" role="status">Draft opened in your app. Press send there. Muse can't confirm delivery.</span>}
                </li>))}</ul>)}
            <p className="mt-3 text-xs text-muted">If you're thinking about harming yourself, free confidential support is at <a className="underline" href="https://www.findahelpline.com" target="_blank" rel="noreferrer">findahelpline.com</a>.</p>
          </div>)}
      </section>

      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <Card title="Trusted contacts">
          {g.contacts.length === 0 ? <p className="text-sm text-muted">No contacts yet.</p> : (
            <ul className="divide-y divide-line">{g.contacts.map((c) => { const on = g.guardians.includes(c.id); return (
              <li key={c.id} className="flex items-center gap-3 py-2 text-sm"><span className="flex-1"><b className="font-medium">{c.name}</b> <span className="text-muted">{c.role}{c.phone ? ` · ${c.phone}` : ""}</span></span>
                <label className="flex items-center gap-1"><input type="checkbox" checked={on} onChange={() => g.setGuardians(on ? g.guardians.filter((x) => x !== c.id) : [...g.guardians, c.id])} /> Guardian</label></li>); })}</ul>)}
          <form className="mt-3 grid grid-cols-2 gap-2 border-t border-line pt-3" onSubmit={(e) => { e.preventDefault(); if (!nc.name.trim()) return; const id = uid(); g.setContacts([...g.contacts, { id, name: nc.name.trim(), phone: nc.phone.trim() || undefined, role: nc.role }]); g.setGuardians([...g.guardians, id]); setNc({ name: "", phone: "", role: "Trusted contact" }); }}>
            <Field label="Name"><input className={inputCls} value={nc.name} onChange={(e) => setNc({ ...nc, name: e.target.value })} /></Field>
            <Field label="Mobile (with country code)"><input className={inputCls} value={nc.phone} onChange={(e) => setNc({ ...nc, phone: e.target.value })} /></Field>
            <div className="col-span-2"><Button type="submit" variant="primary"><UserPlus size={16} /> Add trusted contact</Button></div>
          </form>
          <p className="mt-2 text-xs text-muted">Shared with Connections. Stored only on this device.</p>
        </Card>

        <div data-tour="guardian-checkins"><Card title="Safety check-ins">
          {g.checkIns.length === 0 ? <p className="text-sm text-muted">Schedule a check-in, for example after a walk or before bed. If you miss it, Muse alerts you while it's open and helps you message someone.</p> : (
            <ul className="divide-y divide-line">{g.checkIns.map((c) => { const s = checkInStatus(c, g.log); return (
              <li key={c.id} className="py-2.5 text-sm">
                <div className="flex flex-wrap items-center gap-2"><span className="flex-1"><b className="font-medium">{c.label}</b> <span className="text-muted">{c.time} · {c.days.length === 7 ? "every day" : c.days.map((d) => DAYS[d]).join(", ")} · {c.graceMin} min grace</span></span>
                  <Badge tone={s === "missed" ? "danger" : s === "due" ? "warn" : s === "done" ? "good" : "neutral"}>{s === "not-today" ? "not today" : s}</Badge>
                  {(s === "due" || s === "missed" || s === "upcoming") && <Button size="sm" variant="primary" onClick={() => checkIn(c.id)}><Check size={14} /> I'm OK</Button>}
                  <button aria-label={`Delete ${c.label}`} className="text-muted hover:text-danger" onClick={() => g.setCheckIns(g.checkIns.filter((x) => x.id !== c.id))}><Trash2 size={15} /></button></div>
                {s === "missed" && trusted.length > 0 && <div className="mt-2 rounded-f-sm bg-danger/8 p-2">Missed check-in. Message someone?{trusted.map((t) => t.phone && <a key={t.id} className="ml-2 underline" href={smsUrl(t.phone, checkInMessage(app.profile.name, c.label))}>{t.name}</a>)}<span className="ml-2 text-xs text-muted">Opens your SMS app; you press send.</span></div>}
              </li>); })}</ul>)}
          <form className="mt-3 grid grid-cols-2 gap-2 border-t border-line pt-3" onSubmit={(e) => { e.preventDefault(); g.setCheckIns([...g.checkIns, { id: uid(), ...ci, enabled: true }]); }}>
            <Field label="Label"><input className={inputCls} value={ci.label} onChange={(e) => setCi({ ...ci, label: e.target.value })} /></Field>
            <Field label="Time"><input type="time" className={inputCls} value={ci.time} onChange={(e) => setCi({ ...ci, time: e.target.value })} /></Field>
            <Field label="Grace (minutes)"><input type="number" min={5} max={240} className={inputCls} value={ci.graceMin} onChange={(e) => setCi({ ...ci, graceMin: Number(e.target.value) })} /></Field>
            <Field label="Days"><div className="flex flex-wrap gap-1">{DAYS.map((d, i) => <button type="button" key={d} aria-pressed={ci.days.includes(i)} onClick={() => setCi({ ...ci, days: ci.days.includes(i) ? ci.days.filter((x) => x !== i) : [...ci.days, i].sort() })} className={`rounded-full px-2 py-0.5 text-xs ${ci.days.includes(i) ? "bg-primary text-primary-ink" : "bg-surface-2"}`}>{d}</button>)}</div></Field>
            <div className="col-span-2"><Button type="submit" variant="primary"><Plus size={16} /> Add check-in</Button></div>
          </form>
        </Card></div>
      </div>

      <Card className="mt-5" title="Emergency information" actions={<div className="flex gap-2"><Button size="sm" onClick={printCard}><Printer size={14} /> Print card</Button>
        <Button size="sm" onClick={() => { const url = URL.createObjectURL(new Blob([emergencyCard(g.info, trusted)], { type: "text/plain" })); const a = document.createElement("a"); a.href = url; a.download = "emergency-card.txt"; a.click(); URL.revokeObjectURL(url); }}><Download size={14} /> Save</Button></div>}>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {([["fullName", "Full name"], ["dateOfBirth", "Date of birth"], ["bloodType", "Blood type"], ["conditions", "Medical conditions"], ["allergies", "Allergies"], ["medications", "Current medications"], ["clinician", "Clinician / clinic"], ["pets", "Pet-care instructions"], ["notes", "Other notes"]] as [keyof EmergencyInfo, string][]).map(([k, l]) => (
            <Field key={k} label={l}><input className={inputCls} value={g.info[k]} onChange={(e) => g.setInfo({ ...g.info, [k]: e.target.value })} /></Field>))}
        </div>
        <p className="mt-2 text-xs text-muted">Only what you type. Saved on this device and never shared unless you print or send it.</p>
      </Card>

      <Card className="mt-5" title="What Guardian can and can't do today">
        <ul className="divide-y divide-line text-sm">{CAPABILITIES.map((c) => (
          <li key={c.feature} className="flex flex-wrap items-center gap-3 py-2.5"><span className="flex-1"><b className="font-medium">{c.feature}</b><br /><span className="text-muted">{c.detail}</span></span>
            <Badge tone={c.status === "works" ? "good" : "neutral"}>{c.status === "works" ? "Works now" : c.status === "server" ? "Needs secure server" : "Needs mobile app"}</Badge></li>))}</ul>
        <Notice tone="neutral">Location is never shared in the background or with any community. Future live sharing will use time-limited, encrypted links that you start and stop yourself.</Notice>
      </Card>
    </div>
  );
}
