import { Link } from "react-router-dom";
import { ArrowRight, Sparkles } from "lucide-react";
import { useApp } from "../lib/app-state";
import { NAV } from "../modules/navigation";
import { Button, Card } from "../components/ui";
import { loadLog } from "../modules/nutrition/store";
import { totals } from "../modules/nutrition/engine";
import { dayKey } from "../lib/storage";
import { useReminders } from "../modules/reminders/useReminders";
import { greeting, suggestions } from "../modules/muse/proactive";
import { ENCOURAGEMENTS } from "../modules/opportunities/data";

export function Home() {
  const app = useApp();
  const { meds, checkups } = useReminders();
  const today = totals(loadLog(app.profile.id).filter((e) => e.date === dayKey(new Date())));
  const city = app.location?.city || app.profile.city;
  const list = suggestions({ name: app.profile.name, city, meds, checkups, interests: app.profile.interests, hasFoodToday: today.entries > 0, privateMedication: app.prefs.privateMedication });
  const joyOn = app.prefs.categories.joy.enabled;
  return (
    <div className="space-y-6">
      <section data-tour="home-hero" className="hero-grad relative overflow-hidden rounded-f-lg p-8 text-white md:p-12">
        <p className="flex items-center gap-2 text-sm uppercase tracking-[0.25em] opacity-80"><Sparkles size={16} /> Your Muse</p>
        <h1 className="mt-3 font-display text-4xl md:text-5xl">{greeting(app.profile.name)}</h1>
        <p className="mt-3 max-w-2xl text-lg opacity-90">{list[0]?.text}</p>
        <div className="mt-6 flex flex-wrap gap-2">
          <Link to="/app/copilot"><Button className="!bg-white !text-[#14110f]">Talk to Muse</Button></Link>
          {list[0]?.action && <Link to={list[0].action.to}><Button className="!bg-white/15 !text-white">{list[0].action.label}</Button></Link>}
        </div>
      </section>

      {list.length > 1 && (
        <Card title="Muse suggests">
          <ul className="divide-y divide-line">{list.slice(1).map((s) => (
            <li key={s.id} className="flex items-center gap-4 py-3"><p className="flex-1">{s.text}</p>
              {s.action && <Link to={s.action.to} className="flex shrink-0 items-center gap-1 text-sm font-medium text-primary">{s.action.label} <ArrowRight size={14} /></Link>}</li>))}</ul>
          <p className="mt-2 text-xs text-muted">Suggestions come only from what you've recorded and chosen. Nothing is assumed.</p>
        </Card>)}

      {joyOn && <Card><p className="font-display text-xl">{ENCOURAGEMENTS[new Date().getDate() % ENCOURAGEMENTS.length]}</p></Card>}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {NAV.filter((n) => n.path !== "/app").map((n) => (
          <Link key={n.path} to={n.path} className="group rounded-f bg-surface p-5 shadow-f transition hover:-translate-y-0.5 hover:ring-1 hover:ring-accent/40">
            <div className="flex items-center gap-2"><n.icon size={20} className="text-accent" /><b className="font-display text-lg font-normal">{n.label}</b>{n.status === "planned" && <span className="ml-auto text-[10px] uppercase tracking-widest text-muted">Coming</span>}</div>
            <p className="mt-1 text-sm text-muted">{n.summary}</p>
          </Link>))}
      </div>
    </div>
  );
}
