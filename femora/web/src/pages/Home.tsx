import { Link } from "react-router-dom";
import { useApp } from "../lib/app-state";
import { STAGE_LABEL } from "../data/demo/profiles";
import { NAV } from "../modules/navigation";
import { Badge, Button, Card, StatusBadge } from "../components/ui";
import { loadLog } from "../modules/nutrition/store";
import { totals } from "../modules/nutrition/engine";
import { dayKey } from "../lib/storage";
import { useEffect } from "react";
import { GOOD_NEWS, opportunitiesFor } from "../modules/opportunities/data";

export function Home() {
  const { profile, symptoms, joy, location, notify } = useApp();
  const city = location?.city || profile.city || "your city";
  const day = new Date().getDate();
  const news = GOOD_NEWS[day % GOOD_NEWS.length];
  const deals = opportunitiesFor(city).filter((o) => o.category === "Deals" || o.category === "Yoga" || o.category === "Spiritual & mindfulness");
  const deal = deals[day % deals.length];
  useEffect(() => {
    // Cheer her up once per day with good news and a nearby deal or zone.
    const k = `femora:cheer:${profile.id}:${dayKey(new Date())}`;
    if (!sessionStorage.getItem(k) && deal) { sessionStorage.setItem(k, "1"); notify("Something nice for you today ✨", `${deal.title} · ${deal.where} (example)`, "/app/free-care"); }
  }, [profile.id, deal, notify]);
  const today = totals(loadLog(profile.id).filter((e) => e.date === dayKey(new Date())));
  const hour = new Date().getHours();
  return (
    <div className="space-y-6">
      <section className="hero-grad rounded-f-lg p-8 text-white">
        <p className="opacity-85">{hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening"}</p>
        <h1 className="font-display text-4xl">{profile.name}</h1>
        <div className="mt-2 flex flex-wrap gap-2 text-sm"><span className="rounded-full bg-white/20 px-3 py-1">{STAGE_LABEL[profile.stage]}</span><span className="rounded-full bg-white/20 px-3 py-1">{[profile.city, profile.country].filter(Boolean).join(", ")}</span><span className="rounded-full bg-white/20 px-3 py-1">Fictional profile</span></div>
        <p className="mt-4 max-w-2xl opacity-90">{profile.story}</p>
        <div className="mt-5 flex flex-wrap gap-2"><Link to="/app/copilot"><Button className="!bg-white !text-[#1f2a44]">Talk to FEMORA</Button></Link><Link to="/app/food"><Button className="!bg-white/20 !text-white">Log a meal</Button></Link></div>
      </section>
      <section className="grid gap-5 rounded-f bg-surface p-6 shadow-f md:grid-cols-[1.2fr_1fr]" aria-label="Today's good news">
        <div><p className="text-sm font-semibold uppercase tracking-wide text-warm">Good news today</p><p className="mt-1 font-display text-xl">{news}</p></div>
        {deal && <Link to="/app/free-care" className="rounded-f-sm bg-surface-2 p-4 hover:ring-2 hover:ring-primary/30">
          <p className="text-xs font-semibold uppercase tracking-wide text-primary">{deal.category === "Deals" ? "Deal near you" : `${deal.category} near you`} · example</p>
          <p className="mt-1 font-medium">{deal.title}</p><p className="text-sm text-muted">{deal.host} · {deal.time}</p></Link>}
      </section>
      <div className="grid gap-5 md:grid-cols-3">
        <Card title="Today's food"><p className="text-3xl font-display">{today.entries}</p><p className="text-sm text-muted">items logged · {Math.round(today.values.protein)} g protein · {Math.round(today.values.calcium)} mg calcium</p><Link className="mt-2 inline-block text-sm text-primary underline" to="/app/food">Open food log</Link></Card>
        <Card title="Symptoms logged"><p className="text-3xl font-display">{symptoms.length}</p><p className="text-sm text-muted">{symptoms.length ? `Most recent: ${symptoms[symptoms.length - 1].name}` : "Log from a conversation or the journey tracker"}</p></Card>
        <Card title="Joy Map"><p className="text-3xl font-display">{joy.length}</p><p className="text-sm text-muted">{joy.length ? `Latest: ${joy[joy.length - 1].text}` : "Moments you chose to remember"}</p><Link className="mt-2 inline-block text-sm text-primary underline" to="/app/joy">Open Joy Map</Link></Card>
      </div>
      <Card title="Her concerns"><div className="flex flex-wrap gap-2">{profile.concerns.map((c) => <Badge key={c} tone="accent">{c}</Badge>)}</div></Card>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {NAV.filter((n) => n.path !== "/app").map((n) => (
          <Link key={n.path} to={n.path} className="rounded-f bg-surface p-5 shadow-f hover:ring-2 hover:ring-primary/30">
            <div className="flex items-center gap-2"><n.icon size={20} className="text-primary" /><b>{n.label}</b></div>
            <p className="mt-1 text-sm text-muted">{n.summary}</p><div className="mt-2"><StatusBadge status={n.status} /></div>
          </Link>))}
      </div>
    </div>
  );
}
