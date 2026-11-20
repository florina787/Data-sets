import { Link } from "react-router-dom";
import { SiteLayout, Eyebrow } from "../SiteLayout";
import { Reveal } from "../Reveal";
import { usePageMeta } from "../usePageMeta";

const CAN = ["Help you record cycles, symptoms, meals, sleep, blood pressure and more", "Explain patterns and published guideline ranges in plain language", "Give population context from real public data (CDC NHANES)", "Remind you about medication and check-ups you entered", "Help you reach people fast in an emergency (you press send)", "Point you to verified menopause organisations"];
const CANNOT = ["Diagnose any condition or tell you your menopause stage", "Predict when your final period will be", "Change, start or stop any medication", "Replace a clinician, therapist or emergency service", "Confirm that an SOS message was delivered", "Guarantee accuracy of food or nutrient estimates"];
const DATA = [
  ["Stored only on your device", "Everything you record: cycles, symptoms, meals, measurements, reminders, conversations, contacts, emergency card. Browser storage, not encrypted at rest yet."],
  ["Sent only when you act", "Map tiles from OpenFreeMap/OpenStreetMap when you open the map; a city name to OpenStreetMap search when you press Go; your messages to your own llama.cpp server if you connect one; drafts to WhatsApp/SMS/email apps when you press send."],
  ["Never sent", "Your health records. No account, no analytics, no advertising trackers. Fonts and media are self-hosted."],
];

export function TrustPage() {
  usePageMeta("Science, trust & privacy · FEMORA Muse", "What FEMORA Muse can and cannot do, what stays on your device, how evidence is used, consent and deletion, community privacy and safety guidance.", "/trust");
  return (
    <SiteLayout>
      <section className="mx-auto max-w-5xl px-5 pb-6 pt-32"><Reveal><Eyebrow>Science, trust & privacy</Eyebrow><h1 className="mt-3 font-display text-6xl leading-tight">Plain answers to fair questions.</h1>
        <p className="mt-4 text-lg text-[#5a544b]">FEMORA Muse is not a medical device, and it hasn't been clinically validated or reviewed by a regulator. Here's exactly what that means for you.</p></Reveal></section>

      <section className="mx-auto grid max-w-5xl gap-6 px-5 py-10 md:grid-cols-2">
        <Reveal className="rounded-[24px] bg-[#2f6a4a]/10 p-7"><h2 className="font-display text-3xl">Muse can</h2><ul className="mt-4 space-y-2 text-[15px]">{CAN.map((c) => <li key={c}>✓ {c}</li>)}</ul></Reveal>
        <Reveal delay={100} className="rounded-[24px] bg-[#b23a32]/8 p-7"><h2 className="font-display text-3xl">Muse cannot</h2><ul className="mt-4 space-y-2 text-[15px]">{CANNOT.map((c) => <li key={c}>✕ {c}</li>)}</ul></Reveal>
      </section>

      <section className="mx-auto max-w-5xl px-5 py-10"><Reveal><h2 className="font-display text-4xl">Your data</h2></Reveal>
        <div className="mt-6 space-y-4">{DATA.map(([t, d]) => <Reveal key={t} className="site-glass rounded-[20px] p-6"><h3 className="font-display text-2xl">{t}</h3><p className="mt-1 text-[15px] text-[#4a443c]">{d}</p></Reveal>)}</div>
        <Reveal className="mt-6 text-[15px] text-[#4a443c]"><b>Consent & deletion.</b> Muse remembers a fact only after you approve it; review or delete memories anytime. Profile & privacy → Your data exports everything as a file or deletes it in one step. The interactive demo uses a separate storage area and is removed when you exit it.</Reveal>
      </section>

      <section className="bg-[#f4f1ea] py-16"><div className="mx-auto max-w-5xl px-5">
        <Reveal><h2 className="font-display text-4xl">How Muse uses health information</h2>
          <p className="mt-3 text-[15px] text-[#4a443c]">Safety rules run first on every message: crisis language or urgent symptoms (such as chest pain or bleeding after menopause) always lead to emergency guidance and real help. Numbers like protein totals, cycle lengths and forecasts come from transparent code, never from a language model. Muse's words come from its reviewed offline library, or from a model you run yourself; it's told to use only the facts it's given.</p></Reveal>
        <Reveal className="mt-8"><h2 className="font-display text-4xl">Evidence & methodology</h2>
          <ul className="mt-3 space-y-2 text-[15px] text-[#4a443c]">
            <li>• Health facts cite sources such as the WHO menopause fact sheet, NICE guideline NG23 and the STRAW+10 staging framework.</li>
            <li>• Guideline ranges: ACC/AHA 2017 (blood pressure), American Diabetes Association (glucose, HbA1c), WHO (added sugar).</li>
            <li>• The menopause-timing model is trained on public CDC NHANES 2013–2018 data with open-source tools. Results, including weak or null findings, are published in the model card.</li>
            <li>• Organisations are listed only after their official website is checked, with the date shown.</li>
            <li>• Muse's replies are tested automatically for warmth, safety and honesty (15 agent evaluations, 134 software tests).</li>
          </ul></Reveal>
      </div></section>

      <section className="mx-auto grid max-w-5xl gap-6 px-5 py-16 md:grid-cols-2">
        <Reveal><h2 className="font-display text-3xl">Community privacy</h2><p className="mt-2 text-[15px] text-[#4a443c]">The map shows organisations only, at country or city level. Your location is never shown. Future circles will require secure accounts, moderation, reporting and blocking; health records will never be visible to other members.</p></Reveal>
        <Reveal delay={100} className="rounded-[24px] border-2 border-[#b23a32] p-6"><h2 className="font-display text-3xl">If you need help now</h2><p className="mt-2 text-[15px]">Call your local emergency number. For emotional support, free confidential helplines are listed at <a className="underline" href="https://www.findahelpline.com" rel="noopener">findahelpline.com</a>. Muse's Guardian page puts your emergency number one tap away.</p>
          <Link to="/app/guardian" className="mt-4 inline-flex rounded-full bg-[#b23a32] px-5 py-2.5 text-white">Open Guardian</Link></Reveal>
      </section>
    </SiteLayout>
  );
}
