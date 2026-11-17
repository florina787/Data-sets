import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { Button, Logo, StatusBadge, type Status } from "../components/ui";
import { Credit } from "../components/Credit";

const LINES = ["walks beside you.", "listens first.", "knows your plate.", "remembers your check-ups.", "finds your people."];

const PILLARS: [string, string][] = [
  ["Muse, your companion", "Warm, encouraging conversation about anything: sleep, cycles, family, work, joy. Safety rules run before any AI does."],
  ["Food from every kitchen", "Log idli, jollof, laksa or tacos in a sentence. Sugar percentage and nutrients come from transparent calculations."],
  ["Your health planner", "Medication and supplement reminders that follow exactly what you enter, plus check-ups and the questions you want to ask."],
  ["MedScan", "Understand your lab results against your own report's ranges, and know when to seek care, right away."],
  ["Verified discovery", "Official screening programmes and health resources, checked and dated. Muse never invents an event, offer or appointment."],
  ["Private by design", "Your data stays on your device. Memory only with your consent. Notifications that respect quiet hours and privacy."],
];

const STATUS_ROWS: [string, Status][] = [
  ["Muse conversation: offline response library, or your own llama.cpp model", "demonstrated"],
  ["Food diary, sugar percentage, nutrient charts, photo-assisted logging", "demonstrated"],
  ["Medication & check-up planner with notification preferences", "demonstrated"],
  ["MedScan lab explainer and rule-based symptom check", "demonstrated"],
  ["Discover: verified official resources; verified event feed (empty until partners connect)", "demonstrated"],
  ["Connections: contacts, WhatsApp, email, text, calendar files (you press send)", "demonstrated"],
  ["Menopause journey, body & mind tracking, Guardian safety, sisterhood map", "planned"],
  ["Accounts, encrypted sync, Gmail/Outlook, mobile apps, wearables", "planned"],
];

export function Showcase() {
  const [i, setI] = useState(0);
  useEffect(() => {
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;
    const id = setInterval(() => setI((x) => (x + 1) % LINES.length), 2800);
    return () => clearInterval(id);
  }, []);
  return (
    <div className="min-h-screen">
      <header className="hero-grad relative overflow-hidden text-[#f7f1e6]">
        <div aria-hidden className="pointer-events-none absolute -right-40 -top-40 h-[36rem] w-[36rem] rounded-full bg-[radial-gradient(circle,rgba(215,181,122,0.35),transparent_60%)]" />
        <div aria-hidden className="pointer-events-none absolute -bottom-52 -left-24 h-[30rem] w-[30rem] rounded-full bg-[radial-gradient(circle,rgba(255,255,255,0.10),transparent_60%)]" />
        <nav className="relative mx-auto flex max-w-6xl items-center gap-3 px-6 py-6">
          <span className="flex items-center gap-2"><Logo /><span className="font-display text-2xl tracking-wide">FEMORA <span className="text-[#d7b57a]">Muse</span></span></span>
          <Link to="/app" className="ml-auto"><Button className="!bg-[#f7f1e6] !text-[#17140f]">Meet your Muse <ArrowRight size={16} /></Button></Link>
        </nav>
        <div className="relative mx-auto max-w-6xl px-6 pb-28 pt-16 md:pt-24">
          <p className="text-sm uppercase tracking-[0.35em] text-[#d7b57a]">Women's health · menopause · life</p>
          <h1 className="mt-6 max-w-4xl font-display text-6xl leading-[1.02] md:text-8xl">A companion that{" "}
            {/* All lines share one grid cell, so the hero is always as tall as the longest line: no layout shift. */}
            <span className="grid italic text-[#e7cf9f]">{LINES.map((l, k) => <span key={l} aria-hidden={k !== i} className={`col-start-1 row-start-1 transition-opacity duration-700 motion-reduce:transition-none ${k === i ? "opacity-100" : "opacity-0"}`}>{l}</span>)}</span></h1>
          <p className="mt-8 max-w-2xl text-lg leading-relaxed text-[#e9e1d2]">FEMORA Muse brings conversation, nutrition, health planning and trusted discovery into one calm, private place, through perimenopause, menopause and every chapter around them.</p>
          <div className="mt-10 flex flex-wrap gap-3">
            <Link to="/app/copilot"><Button className="!bg-[#d7b57a] !text-[#17140f]">Meet your Muse</Button></Link>
            <Link to="/app/food"><Button className="!bg-white/10 !text-[#f7f1e6] ring-1 ring-white/25">Explore your health</Button></Link>
            <Link to="/app/free-care"><Button className="!bg-white/10 !text-[#f7f1e6] ring-1 ring-white/25">Discover</Button></Link>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl space-y-28 px-6 py-24">
        <section className="f-enter">
          <p className="text-sm uppercase tracking-[0.3em] text-accent">What Muse does</p>
          <h2 className="mt-3 max-w-3xl font-display text-5xl leading-tight">Six ways Muse makes this chapter lighter</h2>
          <div className="mt-12 grid gap-px overflow-hidden rounded-f-lg bg-line md:grid-cols-2 lg:grid-cols-3">
            {PILLARS.map(([t, d], k) => <div key={t} className="bg-surface p-8"><span className="font-display text-3xl text-accent">0{k + 1}</span><h3 className="mt-3 font-display text-2xl">{t}</h3><p className="mt-2 leading-relaxed text-muted">{d}</p></div>)}
          </div>
        </section>

        <section>
          <p className="text-sm uppercase tracking-[0.3em] text-accent">Honest by design</p>
          <h2 className="mt-3 font-display text-5xl">What's available today</h2>
          <div className="mt-10 overflow-hidden rounded-f-lg bg-surface shadow-f">
            <table className="w-full text-left text-[15px]"><caption className="sr-only">Feature availability</caption>
              <tbody>{STATUS_ROWS.map(([c, s]) => <tr key={c} className="border-t border-line first:border-0"><td className="px-6 py-4">{c}</td><td className="px-6 py-4 text-right"><StatusBadge status={s} /></td></tr>)}</tbody>
            </table>
          </div>
          <p className="mt-4 text-sm text-muted">Muse supports, and never replaces, your clinicians. Nothing here is clinically validated yet.</p>
        </section>

        <section className="hero-grad rounded-f-lg p-12 text-center text-[#f7f1e6] md:p-16">
          <h2 className="mx-auto max-w-3xl font-display text-5xl leading-tight">Your health, your pace, your Muse.</h2>
          <Link to="/app"><Button className="mt-8 !bg-[#d7b57a] !text-[#17140f]">Start your journey <ArrowRight size={16} /></Button></Link>
        </section>
      </main>
      <footer className="border-t border-line py-10 text-center text-sm text-muted"><p className="font-display text-xl text-ink">FEMORA Muse</p><p className="mt-1">A companion for women's health and life · not a substitute for medical care</p><Credit className="mt-2" /></footer>
    </div>
  );
}
