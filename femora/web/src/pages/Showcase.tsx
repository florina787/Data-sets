import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { Button, Logo, StatusBadge, type Status } from "../components/ui";
import { Credit } from "../components/Credit";

const PILLARS = [
  ["A companion she can talk to", "Long, real conversations about sleep, cycles, loneliness, family, work and joy, with safety rules that run before any AI does."],
  ["Food that respects her culture", "Log idli, jollof, laksa or tacos in plain language. Nutrient estimates are deterministic and editable, never invented by a model."],
  ["Menopause intelligence", "Cycle history, symptoms and education grounded in recognised staging (STRAW+10) and guidelines, with uncertainty shown."],
  ["Global sisterhood", "An interactive world map of support organisations, walking groups and circles, with privacy built in."],
  ["Care and safety", "Free check-ups and screening campaigns near her, medication and check-up reminders, clinician discovery, and a Guardian with trusted contacts."],
  ["Private by design", "Offline-first, consent-based memory, and separate privacy boundaries for health records, conversations and communities."],
];

const STATUS_ROWS: [string, Status][] = [
  ["Conversational copilot: 8 modes, history, search, export, memory consent", "simulated"],
  ["Safety rules for crisis and urgent symptoms", "demonstrated"],
  ["Food logging, natural-language entry, nutrient calculations", "demonstrated"],
  ["My Joy Map", "demonstrated"],
  ["MedScan: lab-report explainer (reading simulated) and rule-based symptom check", "simulated"],
  ["Home sample collection with results in 2–3 days (booking simulated)", "simulated"],
  ["Connections: contacts, WhatsApp, email, text, calendar (you press send)", "demonstrated"],
  ["Gmail/Outlook and WhatsApp sync", "planned"],
  ["Medication & check-up reminders with notifications", "demonstrated"],
  ["Free care & events: check-ups, sample collection, communities, goodies (example listings)", "simulated"],
  ["Region & city personalisation, food camera scan (recognition simulated), sugar % charts", "demonstrated"],
  ["Themeable design system: light/dark and three presets", "demonstrated"],
  ["Menstrual, ovulation and symptom tracking", "planned"],
  ["Walking, sleep, body health, mood", "planned"],
  ["Global sisterhood map", "planned"],
  ["Doctor discovery and Guardian SOS (simulation)", "planned"],
  ["Live AI inference, secure accounts, mobile apps, wearables", "planned"],
  ["Clinical evaluation", "planned"],
];

const ROADMAP = [
  ["Now", "Leadership demo on GitHub Pages: synthetic data, simulated AI, working tracking"],
  ["Next", "Secure accounts, encrypted storage, live multilingual AI with retrieval over a graded evidence base"],
  ["Then", "Android and iOS apps, offline on-device models, wearable integrations, moderated communities"],
  ["Scale", "Clinical evaluation partnerships, country-specific care networks, international expansion"],
];

export function Showcase() {
  return (
    <div className="min-h-screen">
      <header className="hero-grad relative overflow-hidden text-white">
        <nav className="mx-auto flex max-w-6xl items-center gap-3 px-6 py-5">
          <span className="flex items-center gap-2 font-semibold tracking-[0.2em]"><Logo /> FEMORA AI</span>
          <Link to="/app" className="ml-auto"><Button className="!bg-white !text-[#1f2a44]">Try FEMORA <ArrowRight size={16} /></Button></Link>
        </nav>
        <div className="mx-auto max-w-6xl px-6 pb-24 pt-12">
          <span className="rounded-full border border-white/40 bg-white/15 px-3 py-1 text-sm">Leadership demonstration · prototype</span>
          <h1 className="mt-5 max-w-3xl font-display text-5xl leading-tight md:text-6xl">From safety to health, one companion that walks beside her.</h1>
          <p className="mt-5 max-w-2xl text-lg opacity-90">Every woman who lives long enough goes through menopause, yet many navigate it with little information, scattered care and no one to talk to. FEMORA brings conversation, nutrition, health tracking, community and care into one calm, private companion.</p>
          <div className="mt-8 flex flex-wrap gap-3"><Link to="/app/copilot"><Button className="!bg-white !text-[#1f2a44]">Start a conversation</Button></Link><Link to="/app/food"><Button className="!bg-white/20 !text-white">See food intelligence</Button></Link></div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl space-y-20 px-6 py-16">
        <section>
          <p className="text-sm font-semibold uppercase tracking-[0.2em] text-warm">The gap</p>
          <h2 className="mt-2 font-display text-4xl">A life stage that healthcare and technology have under-served</h2>
          <div className="mt-6 grid gap-5 md:grid-cols-3">
            {[["Information", "Symptoms like sleep loss, brain fog, joint pain and mood changes are often not recognised as connected to the menopausal transition."],
              ["Care", "Access to menopause-trained clinicians varies widely between and within countries."],
              ["Connection", "Midlife can be isolating, especially for women living alone, new immigrants or carers. Emotional support matters as much as data."]].map(([t, d]) => (
              <div key={t} className="rounded-f bg-surface p-6 shadow-f"><h3 className="font-display text-xl">{t}</h3><p className="mt-2 text-muted">{d}</p></div>))}
          </div>
          <p className="mt-3 text-xs text-muted">Market sizing and evidence figures will be added once sourced and verified in the research workstream.</p>
        </section>

        <section>
          <p className="text-sm font-semibold uppercase tracking-[0.2em] text-warm">The product</p>
          <h2 className="mt-2 font-display text-4xl">Six pillars, one companion</h2>
          <div className="mt-6 grid gap-5 md:grid-cols-2 lg:grid-cols-3">
            {PILLARS.map(([t, d]) => <div key={t} className="rounded-f bg-surface p-6 shadow-f"><h3 className="font-display text-xl">{t}</h3><p className="mt-2 text-muted">{d}</p></div>)}
          </div>
        </section>

        <section>
          <p className="text-sm font-semibold uppercase tracking-[0.2em] text-warm">Honest status</p>
          <h2 className="mt-2 font-display text-4xl">What's real in this demo</h2>
          <div className="mt-6 overflow-hidden rounded-f bg-surface shadow-f">
            <table className="w-full text-left text-[15px]"><caption className="sr-only">Capability status</caption>
              <thead className="bg-surface-2 text-sm"><tr><th className="px-5 py-3">Capability</th><th className="px-5 py-3">Status</th></tr></thead>
              <tbody>{STATUS_ROWS.map(([c, s]) => <tr key={c} className="border-t border-line"><td className="px-5 py-3">{c}</td><td className="px-5 py-3"><StatusBadge status={s} /></td></tr>)}</tbody>
            </table>
          </div>
          <p className="mt-3 text-sm text-muted">No capability is clinically validated yet. All profiles and health data are fictional.</p>
        </section>

        <section>
          <p className="text-sm font-semibold uppercase tracking-[0.2em] text-warm">Roadmap & funding</p>
          <h2 className="mt-2 font-display text-4xl">From demo to global platform</h2>
          <ol className="mt-6 grid gap-5 md:grid-cols-4">
            {ROADMAP.map(([s, d], i) => <li key={s} className="rounded-f bg-surface p-6 shadow-f"><span className="text-sm text-muted">0{i + 1}</span><h3 className="font-display text-2xl">{s}</h3><p className="mt-2 text-muted">{d}</p></li>)}
          </ol>
          <div className="hero-grad mt-10 rounded-f-lg p-10 text-center text-white">
            <h3 className="font-display text-3xl">Funding unlocks secure accounts, real AI, clinical evaluation and mobile apps.</h3>
            <Link to="/app"><Button className="mt-6 !bg-white !text-[#1f2a44]">Try FEMORA <ArrowRight size={16} /></Button></Link>
          </div>
        </section>
      </main>
      <footer className="border-t border-line py-8 text-center text-sm text-muted">FEMORA AI · prototype for demonstration · fictional data · not medical advice<Credit className="mt-1" /></footer>
    </div>
  );
}
