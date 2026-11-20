import { useNavigate } from "react-router-dom";
import { FlaskConical, RotateCcw, ShieldCheck } from "lucide-react";
import { SiteLayout, Eyebrow, StatusPill } from "../SiteLayout";
import { Reveal } from "../Reveal";
import { usePageMeta } from "../usePageMeta";
import { startDemo } from "../demoData";
import { phone } from "../media";

const INCLUDED = ["A sample Muse conversation (you can keep chatting)", "Six months of synthetic cycles and symptom history", "A month of sample sleep, mood, steps and blood pressure", "A week of sample meals from several cuisines", "Reminders, a check-up with saved questions and a check-in", "The sisterhood map and all three themes"];

export function DemoPage() {
  usePageMeta("Interactive demo · FEMORA Muse", "Explore FEMORA Muse with synthetic sample data: Muse conversation, symptom history, health dashboard, journey timeline, nutrition and the sisterhood map. No sign-up, no health data needed.", "/demo");
  const nav = useNavigate();
  const go = (path: string) => { startDemo(); nav(path); };
  return (
    <SiteLayout>
      <section className="mx-auto grid max-w-7xl items-center gap-12 px-5 pb-20 pt-32 lg:grid-cols-[1.2fr_1fr]">
        <Reveal><Eyebrow>Interactive demo</Eyebrow><h1 className="mt-3 font-display text-6xl leading-tight">Explore Muse with a sample profile.</h1>
          <p className="mt-4 text-lg text-[#5a544b]">Walk through the real app using <b>synthetic data</b> for a fictional member, "Demo Bea". You don't need an account, and we'll never ask for your health information.</p>
          <div className="mt-6 flex flex-wrap gap-3"><StatusPill s="preview" /></div>
          <div className="mt-8 flex flex-wrap gap-3">
            <button onClick={() => go("/app")} className="inline-flex items-center gap-2 rounded-full bg-[#17140f] px-6 py-3.5 font-medium text-[#f7f1e6]"><FlaskConical size={18} /> Start the demo</button>
            <button onClick={() => go("/app/copilot")} className="rounded-full px-6 py-3.5 font-medium ring-1 ring-[#17140f]/20">Go straight to Muse</button>
            <button onClick={() => go("/app/journey")} className="rounded-full px-6 py-3.5 font-medium ring-1 ring-[#17140f]/20">Open the journey</button>
          </div>
          <ul className="mt-8 grid gap-2 text-[15px] sm:grid-cols-2">{INCLUDED.map((x) => <li key={x} className="flex gap-2"><span aria-hidden className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-[#7c5f2b]" />{x}</li>)}</ul></Reveal>
        <Reveal delay={120} className="relative mx-auto w-full max-w-sm"><img src={phone("home")} alt="The demo opens on Muse's home screen" width={420} height={910} className="w-full rounded-[34px] shadow-[0_40px_100px_-40px_rgba(23,20,15,0.6)] ring-8 ring-[#17140f]" /></Reveal>
      </section>
      <section className="bg-[#f4f1ea] py-16"><div className="mx-auto grid max-w-7xl gap-6 px-5 md:grid-cols-3">
        {[[ShieldCheck, "Clearly labelled", "A banner shows on every screen while you're in the demo, and Muse's replies come from its offline library, not a live AI model."], [FlaskConical, "Kept separate", "Demo data lives in its own storage area in your browser, never mixed with real records."], [RotateCcw, "Reset anytime", "Reset demo restores the sample data; Exit demo removes it completely."]].map(([I, t, d]) => {
          const Icon = I as typeof ShieldCheck;
          return <Reveal key={t as string} className="site-glass rounded-[24px] p-6"><Icon className="text-[#3f5139]" size={24} /><h2 className="mt-3 font-display text-2xl">{t as string}</h2><p className="mt-1 text-[15px] text-[#5a544b]">{d as string}</p></Reveal>;
        })}
      </div></section>
    </SiteLayout>
  );
}
