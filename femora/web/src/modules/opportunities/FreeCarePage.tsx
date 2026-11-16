import { useEffect, useState } from "react";
import { BadgeCheck, CalendarPlus, ExternalLink, Plus, Trash2 } from "lucide-react";
import { useApp, type SpiritualPref } from "../../lib/app-state";
import { usePersistent } from "../../lib/usePersistent";
import { uid } from "../../lib/storage";
import { Badge, Button, Card, Field, Notice, PageHeader, inputCls } from "../../components/ui";
import { CATEGORIES, COMMERCIAL, filterFor, loadVerifiedFeed, resourcesFor, toICS, type Category, type Opportunity } from "./data";

const SPIRITUAL: { id: SpiritualPref; label: string }[] = [
  { id: "spiritual", label: "Spiritual" }, { id: "religious", label: "Religious" }, { id: "secular", label: "Secular" },
  { id: "mindfulness", label: "Mindfulness" }, { id: "yoga", label: "Yoga" }, { id: "nature", label: "Nature" }, { id: "none", label: "No spiritual recommendations" },
];

function downloadICS(o: Opportunity) {
  const url = URL.createObjectURL(new Blob([toICS(o)], { type: "text/calendar" }));
  const a = document.createElement("a"); a.href = url; a.download = `${o.id}.ics`; a.click(); URL.revokeObjectURL(url);
}

export function FreeCarePage() {
  const app = useApp();
  const city = app.location?.city || app.profile.city;
  const [feed, setFeed] = useState<Opportunity[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [mine, setMine] = usePersistent<Opportunity[]>(`saved-opps:${app.profile.id}`, () => []);
  const [commercial, setCommercial] = usePersistent(`commercial:${app.profile.id}`, () => false);
  const [cat, setCat] = useState<Category | "All">("All");
  const [form, setForm] = useState({ title: "", organization: "", category: "Screening campaign" as Category, start: "", venue: "", url: "", cost: "free" as Opportunity["cost"] });

  useEffect(() => { loadVerifiedFeed().then((f) => { setFeed(f); setLoaded(true); }); }, []);

  const noSpiritual = app.spiritual.includes("none");
  const visibleCats = CATEGORIES.filter((c) => (commercial || !COMMERCIAL.includes(c)) && !(noSpiritual && c === "Spiritual & mindfulness"));
  const items = filterFor([...feed, ...mine], { city, category: cat, commercial }).filter((o) => visibleCats.includes(o.category));
  const resources = resourcesFor(app.profile.country, city);

  return (
    <div>
      <PageHeader title="Health opportunities & discovery" sub={<>Free screening campaigns, consultations, health education, yoga and spiritual zones, and community activities{city ? <> around <b>{city}</b></> : null}. Every listing is verified or added by you.</>} />

      <div className="grid gap-5 lg:grid-cols-[1.4fr_1fr]">
        <div className="space-y-5">
          <Card title="Events & services">
            <div className="flex flex-wrap gap-2">{(["All", ...visibleCats] as const).map((c) => <button key={c} aria-pressed={cat === c} onClick={() => setCat(c)} className={`rounded-full px-3 py-1.5 text-sm ${cat === c ? "bg-primary text-primary-ink" : "bg-surface-2"}`}>{c}</button>)}</div>
            {!loaded ? <p className="mt-4 text-sm text-muted">Checking verified listings…</p> : items.length === 0 ? (
              <div className="mt-4 rounded-f-sm bg-surface-2 p-4 text-sm">
                <p><b>No verified events{city ? ` for ${city}` : ""} yet.</b> Muse won't invent events, free consultations or discounts. Verified listings will appear here as partner and public-health feeds are connected.</p>
                <p className="mt-1 text-muted">Meanwhile, the official sources on the right are checked and current, and you can save events you find yourself below.</p>
              </div>) : (
              <ul className="mt-4 space-y-3">{items.map((o) => (
                <li key={o.id} className="rounded-f-sm border border-line p-4">
                  <div className="flex flex-wrap items-center gap-1">
                    {o.provenance === "verified-feed" ? <Badge tone="good"><BadgeCheck size={12} /> Verified {o.verifiedAt}</Badge> : <Badge tone="accent">Added by you</Badge>}
                    <Badge>{o.category}</Badge>{o.cost !== "unknown" && <Badge tone={o.cost === "free" ? "good" : "neutral"}>{o.cost}</Badge>}</div>
                  <h3 className="mt-1 font-display text-lg">{o.title}</h3>
                  <p className="text-sm text-muted">{o.organization} · {o.online ? "Online" : `${o.venue}${o.city ? `, ${o.city}` : ""}`} · {new Date(o.start).toLocaleString(undefined, { dateStyle: "medium", ...(o.start.length > 10 ? { timeStyle: "short" } : {}) })}</p>
                  {o.eligibility && <p className="text-sm">Who: {o.eligibility}</p>}
                  <div className="mt-2 flex flex-wrap gap-2">
                    <a href={o.url} target="_blank" rel="noreferrer"><Button size="sm" variant="primary"><ExternalLink size={14} /> Official page</Button></a>
                    <Button size="sm" onClick={() => downloadICS(o)}><CalendarPlus size={14} /> Add to calendar</Button>
                    {o.provenance === "user-added" && <Button size="sm" variant="ghost" onClick={() => setMine((m) => m.filter((x) => x.id !== o.id))}><Trash2 size={14} /> Remove</Button>}
                  </div>
                </li>))}</ul>)}
          </Card>

          <Card title="Save an event you found">
            <form className="grid gap-2 sm:grid-cols-2" onSubmit={(e) => { e.preventDefault(); if (!form.title.trim() || !form.start) return;
              const o: Opportunity = { id: uid(), organization: form.organization.trim() || "—", title: form.title.trim(), category: form.category, country: app.profile.country, city: city ?? "", venue: form.venue.trim(), online: !form.venue.trim(), start: form.start, eligibility: "", cost: form.cost, registration: "", url: form.url.trim(), provenance: "user-added" };
              setMine((m) => [...m, o]);
              app.notify({ key: `saved-${o.id}`, category: "community", priority: "low", title: `Saved: ${o.title}`, body: `${new Date(o.start).toLocaleDateString()}. You can add it to your calendar.`, link: "/app/free-care" });
              setForm({ ...form, title: "", organization: "", start: "", venue: "", url: "" }); }}>
              <Field label="Title"><input className={inputCls} value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="e.g. Free cervical screening day" /></Field>
              <Field label="Organizer"><input className={inputCls} value={form.organization} onChange={(e) => setForm({ ...form, organization: e.target.value })} /></Field>
              <Field label="Category"><select className={inputCls} value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value as Category })}>{CATEGORIES.map((c) => <option key={c}>{c}</option>)}</select></Field>
              <Field label="Date & time"><input type="datetime-local" className={inputCls} value={form.start} onChange={(e) => setForm({ ...form, start: e.target.value })} /></Field>
              <Field label="Venue" hint="Leave empty for online"><input className={inputCls} value={form.venue} onChange={(e) => setForm({ ...form, venue: e.target.value })} /></Field>
              <Field label="Link"><input type="url" className={inputCls} value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })} placeholder="https://" /></Field>
              <Field label="Cost"><select className={inputCls} value={form.cost} onChange={(e) => setForm({ ...form, cost: e.target.value as Opportunity["cost"] })}>{["free", "subsidised", "paid", "discount", "unknown"].map((c) => <option key={c}>{c}</option>)}</select></Field>
              <div className="flex items-end"><Button type="submit" variant="primary"><Plus size={16} /> Save</Button></div>
            </form>
          </Card>
        </div>

        <div className="space-y-5">
          <Card title="Official sources">
            <ul className="space-y-3 text-sm">{resources.map((r) => (
              <li key={r.url}><a className="font-medium text-primary underline" href={r.url} target="_blank" rel="noreferrer">{r.title}</a>
                <div className="text-xs text-muted">{r.organization} · {r.kind}{r.city ? ` · ${r.city}` : ""} · <BadgeCheck size={11} className="inline" /> checked {r.verifiedAt}</div></li>))}</ul>
            <p className="mt-3 text-xs text-muted">Screening is personal: eligibility depends on your age, country, history and your clinician's advice. Muse doesn't tell everyone to have the same test.</p>
          </Card>
          <Card title="Spiritual & wellness preferences">
            <p className="text-sm text-muted">Muse never assumes your beliefs. Choose what, if anything, you'd like to see.</p>
            <div className="mt-2 flex flex-wrap gap-2">{SPIRITUAL.map((s) => { const on = app.spiritual.includes(s.id); return (
              <button key={s.id} aria-pressed={on} onClick={() => app.setSpiritual(s.id === "none" ? (on ? [] : ["none"]) : on ? app.spiritual.filter((x) => x !== s.id) : [...app.spiritual.filter((x) => x !== "none"), s.id])}
                className={`rounded-full px-3 py-1.5 text-sm ${on ? "bg-accent text-white" : "bg-surface-2"}`}>{s.label}</button>); })}</div>
            <p className="mt-2 text-xs text-muted">Spiritual practices complement, and never replace, medical care.</p>
          </Card>
          <Card title="Offers & discounts">
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={commercial} onChange={(e) => setCommercial(e.target.checked)} /> Show verified offers and discounts</label>
            <p className="mt-1 text-xs text-muted">Off by default. Offers are never presented as health recommendations, and Muse never sends marketing without your consent.</p>
          </Card>
          <Notice tone="neutral">Interactive map view arrives with the Global Sisterhood milestone.</Notice>
        </div>
      </div>
    </div>
  );
}
