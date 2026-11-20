import { Link } from "react-router-dom";
import { ShieldCheck } from "lucide-react";
import { SiteLayout, Eyebrow, StatusPill } from "../SiteLayout";
import { Reveal } from "../Reveal";
import { ClipPlayer } from "../ClipPlayer";
import { CLIPS, shot } from "../media";
import { usePageMeta } from "../usePageMeta";

interface F { id: string; title: string; value: string; shot: string; clip?: string; how: string[]; status: "live" | "preview" | "soon"; privacy?: string; soon?: string[] }
const FEATURES: F[] = [
  { id: "muse", title: "Muse AI Companion", value: "A warm companion for anything on your mind, with answers grounded in your own records.", shot: "chat", clip: "chat", status: "live",
    how: ["Eight modes, from 'Talk with me' to Emotional support and Doctor assistant.", "Numbers (protein, cycles, sleep) come from deterministic tools, never guesses.", "Works offline from a reviewed response library, or with your own llama.cpp model on your computer."],
    privacy: "Memory is off until you approve a fact. Crisis and urgent symptoms are handled by safety rules before any AI.", soon: ["Hosted AI (with published usage limits)"] },
  { id: "journey", title: "Menopause Journey", value: "Cycles, symptoms and patterns explained with honest uncertainty.", shot: "journey", clip: "journey", status: "live",
    how: ["Log periods, symptoms (severity and impact) and ovulation observations.", "STRAW+10-based pattern notes switch off when contraception or surgery make cycles unreliable.", "Next-period forecast from your own cycles; population context from 10,375 women (CDC NHANES)."],
    privacy: "Muse never predicts your final period or diagnoses a stage." },
  { id: "health", title: "Health Intelligence", value: "Fourteen measures you record, with trends, comparisons and guideline ranges.", shot: "body", clip: "body", status: "live",
    how: ["Blood pressure, glucose, HbA1c, sleep, steps, joints, skin, hair, nails, brain fog and mood.", "Compare any two measures over 7 days to a year.", "ACC/AHA and ADA ranges in plain words; dangerous readings raise an urgent alert."],
    privacy: "No scores and no diagnoses. Export everything as a spreadsheet.", soon: ["Apple Health & Health Connect import (mobile app)"] },
  { id: "medscan", title: "MedScan", value: "Understand your lab results right away, against your own report's ranges.", shot: "medscan", status: "live",
    how: ["Enter a result and the reference range printed on your report.", "Get a plain-language explanation and questions for your clinician.", "A rule-based symptom check says when to seek care."],
    privacy: "Never compares against invented 'normal' ranges.", soon: ["Reading reports from a photo (needs a secure processing service)"] },
  { id: "food", title: "Food & Lifestyle", value: "Log meals from ten world regions in a sentence.", shot: "food", clip: "food", status: "live",
    how: ["Type '2 idli and sambar for breakfast' and it's logged.", "Fourteen nutrients, editable portions and goals.", "Added sugar as a share of calories against WHO guidance."],
    privacy: "Photo-assisted logging keeps photos on your device; you choose the dish." },
  { id: "guardian", title: "Guardian", value: "Safety tools that are always one tap away.", shot: "guardian", clip: "guardian", status: "live",
    how: ["Call your local emergency number in one tap.", "SOS opens SMS or WhatsApp with your message (and location only if you allow it).", "Scheduled check-ins and a printable emergency card."],
    privacy: "Muse never claims a message was delivered. Location is never shared in the background.", soon: ["Automatic alerts when a check-in is missed (needs a verified delivery server)", "Live location sharing", "Fall detection (mobile app)"] },
  { id: "sisterhood", title: "Sisterhood", value: "A world map of verified menopause societies and support organisations.", shot: "sisterhood", clip: "sisterhood", status: "live",
    how: ["Fifteen organisations checked at their official websites, with dates.", "Search by country, language or topic; map or list view.", "Markers show the country or city served, never an address."],
    privacy: "Your own location is never shown to anyone.", soon: ["Moderated circles, anonymous lounge, Sister Match"] },
  { id: "privacy", title: "Privacy & Offline AI", value: "Your records stay on your device. You decide what Muse remembers.", shot: "settings", clip: "themes", status: "live",
    how: ["Everything works offline; fonts and assets are self-hosted.", "Export or delete all your data in one step.", "Optional: connect your own llama.cpp model, so conversations never leave your computer."],
    privacy: "No account, no tracking, no third-party analytics.", soon: ["Accounts with encrypted sync (opt-in)"] },
];

export function FeaturesPage() {
  usePageMeta("Features · FEMORA Muse", "Muse AI companion, menopause journey, health intelligence, MedScan, food & lifestyle, Guardian safety, sisterhood and offline privacy. What works today and what's coming.", "/features");
  return (
    <SiteLayout>
      <section className="mx-auto max-w-7xl px-5 pb-6 pt-32">
        <Reveal><Eyebrow>Features</Eyebrow><h1 className="mt-3 max-w-3xl font-display text-6xl leading-tight">Everything Muse can do, honestly labelled.</h1></Reveal>
        <nav aria-label="Feature sections" className="mt-8 flex flex-wrap gap-2">{FEATURES.map((f) => <a key={f.id} href={`#${f.id}`} className="rounded-full bg-white/70 px-4 py-2 text-sm ring-1 ring-black/5 hover:bg-white">{f.title}</a>)}</nav>
      </section>
      {FEATURES.map((f, k) => {
        const c = CLIPS.find((x) => x.id === f.clip);
        return (
          <section key={f.id} id={f.id} className={`scroll-mt-24 py-16 ${k % 2 ? "bg-[#f4f1ea]" : ""}`}>
            <div className="mx-auto grid max-w-7xl items-start gap-10 px-5 lg:grid-cols-2">
              <Reveal className={k % 2 ? "lg:order-2" : ""}>
                <div className="flex flex-wrap items-center gap-3"><h2 className="font-display text-4xl">{f.title}</h2><StatusPill s={f.status} /></div>
                <p className="mt-3 text-xl text-[#3f3a33]">{f.value}</p>
                <h3 className="mt-6 text-sm font-semibold uppercase tracking-[0.2em] text-[#7c5f2b]">How it works</h3>
                <ul className="mt-2 space-y-2 text-[15px]">{f.how.map((h) => <li key={h} className="flex gap-2"><span aria-hidden className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-[#3f5139]" />{h}</li>)}</ul>
                {f.privacy && <p className="mt-5 flex gap-2 rounded-[16px] bg-[#3f5139]/10 p-3 text-[15px] text-[#2c3a28]"><ShieldCheck size={18} className="mt-0.5 shrink-0" />{f.privacy}</p>}
                {f.soon && <div className="mt-4"><StatusPill s="soon" /><ul className="mt-2 text-sm text-[#5a544b]">{f.soon.map((s) => <li key={s}>• {s}</li>)}</ul></div>}
              </Reveal>
              <Reveal delay={120}>
                {c ? <ClipPlayer c={c} /> : <img src={shot(f.shot, 1280)} srcSet={`${shot(f.shot, 640)} 640w, ${shot(f.shot, 1280)} 1280w`} sizes="(max-width:1024px) 100vw, 50vw" alt={`${f.title} screen`} loading="lazy" width={1280} height={800} className="w-full rounded-[20px] shadow-[0_30px_80px_-40px_rgba(23,20,15,0.45)]" />}
              </Reveal>
            </div>
          </section>);
      })}
      <section className="mx-auto max-w-7xl px-5 py-16 text-center"><Link to="/demo" className="inline-flex rounded-full bg-[#17140f] px-6 py-3.5 font-medium text-[#f7f1e6]">Try it in the interactive demo</Link></section>
    </SiteLayout>
  );
}
