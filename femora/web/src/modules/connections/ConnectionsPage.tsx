import { useState } from "react";
import { Mail, MessageCircle, Phone, Share2, Smartphone, Trash2, UserPlus, Contact as ContactIcon, CalendarDays, Link2 } from "lucide-react";
import { useApp } from "../../lib/app-state";
import { usePersistent } from "../../lib/usePersistent";
import { uid } from "../../lib/storage";
import { Badge, Button, Card, Field, Notice, PageHeader, StatusBadge, inputCls } from "../../components/ui";
import { contactPickerSupported, emailUrl, nativeShare, pickContacts, smsUrl, whatsappUrl, type Contact } from "./share";

const TEMPLATES = (name: string) => [
  { id: "checkin", label: "I'm OK check-in", text: `Hi, it's ${name}. Just checking in: I'm OK. 💜 (sent from FEMORA)` },
  { id: "support", label: "Ask for support", text: `Hi, it's ${name}. I'm going through some menopause changes and having a tough day. Could we talk or go for a walk this week?` },
  { id: "appt", label: "Share appointment", text: `Hi, it's ${name}. I have a health check-up coming up. Would you be able to come with me?` },
  { id: "invite", label: "Invite to FEMORA circle", text: `Hi! I've joined a women's wellbeing circle through FEMORA. Want to come along to the next walk?` },
];

export function ConnectionsPage() {
  const { profile } = useApp();
  const [contacts, setContacts] = usePersistent<Contact[]>(`contacts:${profile.id}`, () => []);
  const [form, setForm] = useState({ name: "", phone: "", email: "", role: "Trusted contact" });
  const [tpl, setTpl] = useState(TEMPLATES(profile.name)[0]);
  const [msg, setMsg] = useState(tpl.text);

  async function importContacts() {
    const picked = await pickContacts();
    if (!picked.length) { alert(contactPickerSupported() ? "No contacts selected." : "Your browser can't open phone contacts (supported in Chrome on Android). Add contacts manually below."); return; }
    setContacts((c) => [...c, ...picked.map((p) => ({ id: uid(), ...p, role: "Trusted contact" }))]);
  }

  return (
    <div>
      <PageHeader title="Connections" status="demonstrated" sub="Bring FEMORA into the apps you already use: contacts, WhatsApp, email, text and calendar. You stay in control; nothing is sent unless you press send." />

      <div className="grid gap-5 lg:grid-cols-[1fr_1fr]">
        <Card title={<span className="flex items-center gap-2"><ContactIcon size={18} className="text-primary" /> Trusted people</span>}
          actions={<Button size="sm" onClick={importContacts}><Smartphone size={14} /> Import from phone</Button>}>
          {contacts.length === 0 ? <p className="text-sm text-muted">Add the people you'd like to reach quickly: a partner, friend, sister or neighbour.</p> : (
            <ul className="divide-y divide-line">{contacts.map((c) => (
              <li key={c.id} className="flex flex-wrap items-center gap-2 py-2.5">
                <span className="flex-1"><b className="font-medium">{c.name}</b> <Badge>{c.role}</Badge><br /><span className="text-xs text-muted">{[c.phone, c.email].filter(Boolean).join(" · ")}</span></span>
                {c.phone && <a className="rounded-full bg-surface-2 p-2" aria-label={`WhatsApp ${c.name}`} href={whatsappUrl(msg, c.phone)} target="_blank" rel="noreferrer"><MessageCircle size={16} /></a>}
                {c.phone && <a className="rounded-full bg-surface-2 p-2" aria-label={`Text ${c.name}`} href={smsUrl(c.phone, msg)}><Smartphone size={16} /></a>}
                {c.phone && <a className="rounded-full bg-surface-2 p-2" aria-label={`Call ${c.name}`} href={`tel:${c.phone}`}><Phone size={16} /></a>}
                {c.email && <a className="rounded-full bg-surface-2 p-2" aria-label={`Email ${c.name}`} href={emailUrl(c.email, "From FEMORA", msg)}><Mail size={16} /></a>}
                <button aria-label={`Remove ${c.name}`} className="p-2 text-muted hover:text-danger" onClick={() => setContacts((cs) => cs.filter((x) => x.id !== c.id))}><Trash2 size={15} /></button>
              </li>))}</ul>)}
          <form className="mt-4 grid grid-cols-2 gap-2 border-t border-line pt-4" onSubmit={(e) => { e.preventDefault(); if (!form.name.trim()) return; setContacts((c) => [...c, { id: uid(), ...form, name: form.name.trim() }]); setForm({ name: "", phone: "", email: "", role: "Trusted contact" }); }}>
            <Field label="Name"><input className={inputCls} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
            <Field label="Relationship"><select className={inputCls} value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>{["Trusted contact", "Partner", "Family", "Friend", "Clinician", "Neighbour"].map((r) => <option key={r}>{r}</option>)}</select></Field>
            <Field label="Mobile (with country code)"><input className={inputCls} value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} placeholder="+1 615 555 0100" /></Field>
            <Field label="Email"><input type="email" className={inputCls} value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></Field>
            <div className="col-span-2"><Button type="submit" variant="primary"><UserPlus size={16} /> Add person</Button></div>
          </form>
          <p className="mt-2 text-xs text-muted">Contacts are stored only in this browser. Please use fictional details in the public demo.</p>
        </Card>

        <div className="space-y-5">
          <Card title={<span className="flex items-center gap-2"><Share2 size={18} className="text-primary" /> Message</span>}>
            <div className="flex flex-wrap gap-2">{TEMPLATES(profile.name).map((t) => <button key={t.id} aria-pressed={tpl.id === t.id} onClick={() => { setTpl(t); setMsg(t.text); }} className={`rounded-full px-3 py-1.5 text-sm ${tpl.id === t.id ? "bg-primary text-primary-ink" : "bg-surface-2"}`}>{t.label}</button>)}</div>
            <label className="mt-3 block"><span className="sr-only">Message text</span><textarea rows={4} className={inputCls} value={msg} onChange={(e) => setMsg(e.target.value)} /></label>
            <div className="mt-3 flex flex-wrap gap-2">
              <a href={whatsappUrl(msg)} target="_blank" rel="noreferrer"><Button variant="primary"><MessageCircle size={16} /> WhatsApp</Button></a>
              <a href={emailUrl(undefined, "From FEMORA", msg)}><Button><Mail size={16} /> Email</Button></a>
              <a href={smsUrl(undefined, msg)}><Button><Smartphone size={16} /> Text</Button></a>
              <Button onClick={async () => { if (!(await nativeShare("FEMORA", msg))) { await navigator.clipboard?.writeText(msg); alert("Copied to clipboard."); } }}><Share2 size={16} /> Share…</Button>
            </div>
            <p className="mt-2 text-xs text-muted">Choose a person on the left to message them directly, or pick a recipient in WhatsApp or your email app.</p>
          </Card>

          <Card title={<span className="flex items-center gap-2"><Link2 size={18} className="text-primary" /> Integrations</span>}>
            <ul className="space-y-2 text-sm">
              {([["WhatsApp, email, SMS, share sheet", "Pre-filled messages you send yourself", "demonstrated"],
                ["Phone contacts", "Contact Picker in supported browsers, or manual entry", "demonstrated"],
                ["Calendar", "Add events and check-ups as .ics files to Google, Apple or Outlook calendars", "demonstrated"],
                ["Gmail / Outlook sync", "Read appointment emails and lab results with permission (OAuth)", "planned"],
                ["WhatsApp reminders from FEMORA", "Opt-in reminders via WhatsApp Business messaging", "planned"],
                ["Google / Apple Health, wearables", "Steps, sleep and heart-rate import", "planned"]] as const).map(([t, d, s]) => (
                <li key={t} className="flex items-start gap-3"><CalendarDays size={16} className="mt-0.5 text-muted" /><span className="flex-1"><b className="font-medium">{t}</b><br /><span className="text-muted">{d}</span></span><StatusBadge status={s} /></li>))}
            </ul>
            <Notice tone="neutral">Account sync needs secure sign-in and a backend. These are in the funded roadmap.</Notice>
          </Card>
        </div>
      </div>
    </div>
  );
}
