import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bell, BellRing, CalendarPlus, ExternalLink, Gift, HeartPulse, MapPin, MessageCircleHeart, Microscope, Stethoscope, Users, BookOpen, Flower2, Sparkles, Tag } from "lucide-react";
import { useApp } from "../../lib/app-state";
import { Badge, Button, Card, Notice, PageHeader } from "../../components/ui";
import { CATEGORIES, OFFICIAL, opportunitiesFor, toICS, type Category, type Opportunity } from "./data";

const ICON: Record<Category, typeof Gift> = { "Health check-ups": HeartPulse, "Sample collection": Microscope, Consultation: Stethoscope, Workshop: BookOpen, Community: Users, "Free goodies": Gift, Yoga: Flower2, "Spiritual & mindfulness": Sparkles, Deals: Tag };

function downloadICS(o: Opportunity) {
  const url = URL.createObjectURL(new Blob([toICS(o)], { type: "text/calendar" }));
  const a = document.createElement("a"); a.href = url; a.download = `${o.id}.ics`; a.click(); URL.revokeObjectURL(url);
}

export function FreeCarePage() {
  const app = useApp();
  const nav = useNavigate();
  const city = app.location?.city || app.profile.city || "your city";
  const all = useMemo(() => opportunitiesFor(city), [city]);
  const [cat, setCat] = useState<Category | "All">("All");
  const [online, setOnline] = useState<"all" | "online" | "in-person">("all");
  const [saved, setSaved] = useState<string[]>([]);
  const shown = all.filter((o) => (cat === "All" || o.category === cat) && (online === "all" || (online === "online") === o.online));

  async function enableBrowserNotifications() {
    if (typeof Notification === "undefined") { alert("This browser doesn't support notifications."); return; }
    const p = await Notification.requestPermission();
    app.notify(p === "granted" ? "Notifications on" : "Notifications stay in-app", p === "granted" ? "You'll get FEMORA alerts in this browser while the app is open." : "You can still see alerts under the bell icon.");
  }

  function follow(c: Category) {
    const on = !app.follows.includes(c);
    app.toggleFollow(c);
    if (on) {
      const next = all.find((o) => o.category === c);
      app.notify(`Following ${c}`, next ? `Next: ${next.title} · ${new Date(next.date).toLocaleDateString()} · ${next.where} (example)` : "We'll tell you when something new appears.", "/app/free-care");
    }
  }

  return (
    <div>
      <PageHeader title="Free care, events & deals" status="simulated"
        sub={<>Free health check-ups, sample collection, consultations, yoga and spiritual zones, communities, goodies and deals for women near <b>{city}</b> and online. Follow what matters to you and get notified.</>}
        actions={<Button variant="primary" onClick={enableBrowserNotifications}><BellRing size={16} /> Turn on notifications</Button>} />

      <Notice tone="warn">Events below are <b>examples</b> generated for {city} to show how FEMORA will work. Production will use verified listings from health services, NGOs and partners. Official programme links are real.</Notice>

      <Card className="mt-5" title="Follow categories">
        <div className="flex flex-wrap gap-2">
          {CATEGORIES.map((c) => { const I = ICON[c]; const on = app.follows.includes(c); return (
            <button key={c} aria-pressed={on} onClick={() => follow(c)} className={`flex items-center gap-2 rounded-full px-4 py-2 text-sm ${on ? "bg-primary text-primary-ink" : "bg-surface-2 hover:bg-line"}`}>
              <I size={16} /> {c} {on ? <BellRing size={14} /> : <Bell size={14} className="opacity-60" />}</button>); })}
        </div>
      </Card>

      <div className="mt-5 flex flex-wrap items-center gap-2">
        {(["All", ...CATEGORIES] as const).map((c) => <button key={c} aria-pressed={cat === c} onClick={() => setCat(c)} className={`rounded-full px-3 py-1.5 text-sm ${cat === c ? "bg-ink text-surface" : "bg-surface hover:bg-surface-2"}`}>{c}</button>)}
        <select aria-label="Online or in person" className="ml-auto rounded-full border border-line bg-surface px-3 py-1.5 text-sm" value={online} onChange={(e) => setOnline(e.target.value as typeof online)}>
          <option value="all">Online & in person</option><option value="in-person">In person</option><option value="online">Online</option></select>
      </div>

      <ul className="mt-4 grid gap-4 md:grid-cols-2">
        {shown.map((o) => { const I = ICON[o.category]; const isSaved = saved.includes(o.id); return (
          <li key={o.id} className="flex flex-col rounded-f bg-surface p-5 shadow-f">
            <div className="flex items-start gap-3">
              <div className="grid h-11 w-11 shrink-0 place-items-center rounded-f-sm bg-primary/12 text-primary"><I size={20} /></div>
              <div className="flex-1">
                <div className="flex flex-wrap items-center gap-1">{o.free ? <Badge tone="good">Free</Badge> : <Badge tone="warn">Discount</Badge>}<Badge tone="accent">{o.category}</Badge><Badge>Example</Badge></div>
                <h3 className="mt-1 font-display text-lg leading-snug">{o.title}</h3>
                <p className="text-sm text-muted"><MapPin size={13} className="inline" /> {o.host} · {o.where}</p>
              </div>
              <div className="text-right text-sm"><b>{new Date(o.date).toLocaleDateString(undefined, { day: "numeric", month: "short" })}</b><div className="text-xs text-muted">{o.time}</div></div>
            </div>
            <p className="mt-3 text-sm">{o.details}</p>
            <p className="mt-1 text-xs text-muted">Who: {o.eligibility}</p>
            <div className="mt-4 flex flex-wrap gap-2">
              <Button size="sm" variant={isSaved ? "secondary" : "primary"} onClick={() => { setSaved((s) => isSaved ? s.filter((x) => x !== o.id) : [...s, o.id]); if (!isSaved) app.notify(`Reminder set: ${o.title}`, `${new Date(o.date).toLocaleDateString()} · ${o.time} · ${o.where} (example)`, "/app/free-care"); }}>
                {isSaved ? <><BellRing size={14} /> Reminder on</> : <><Bell size={14} /> Notify me</>}</Button>
              <Button size="sm" onClick={() => downloadICS(o)}><CalendarPlus size={14} /> Add to calendar</Button>
              <Button size="sm" variant="ghost" onClick={() => nav("/app/copilot")}><MessageCircleHeart size={14} /> Ask FEMORA</Button>
            </div>
          </li>); })}
      </ul>
      {shown.length === 0 && <p className="mt-4 text-muted">Nothing in this filter yet.</p>}

      <Card className="mt-6" title="Official programmes (real sources)">
        <ul className="space-y-2 text-sm">{OFFICIAL.map((p) => (
          <li key={p.url}><Badge tone="primary">{p.topic}</Badge> <a className="text-primary underline" href={p.url} target="_blank" rel="noreferrer">{p.title} <ExternalLink size={12} className="inline" /></a> <span className="text-muted">· {p.publisher}</span></li>))}</ul>
        <p className="mt-2 text-xs text-muted">Screening eligibility differs by country. Check your national programme or ask your clinician.</p>
      </Card>
    </div>
  );
}
