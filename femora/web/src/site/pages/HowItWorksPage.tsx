import { Link } from "react-router-dom";
import { SiteLayout, Eyebrow, StatusPill } from "../SiteLayout";
import { Reveal } from "../Reveal";
import { ClipPlayer } from "../ClipPlayer";
import { CLIPS } from "../media";
import { usePageMeta } from "../usePageMeta";

const STEPS = [
  { n: 1, t: "Explore FEMORA", d: "Open the app or the interactive demo. No account, no health data needed to look around.", clip: "onboarding", status: "live" as const, cta: { to: "/demo", label: "Explore the demo" } },
  { n: 2, t: "Create a private profile", d: "Today your profile lives only on your device. Secure accounts with encrypted sync will be optional when registration opens.", status: "soon" as const },
  { n: 3, t: "Record symptoms & wellness", d: "Log cycles, symptoms, meals, sleep, blood pressure and more, in seconds.", clip: "journey", status: "live" as const },
  { n: 4, t: "Explore insights with Muse", d: "Ask Muse about your patterns. Numbers come from your records; Muse says when it won't guess.", clip: "chat", status: "live" as const },
  { n: 5, t: "Discover community", d: "Find verified menopause societies and support groups on the sisterhood map. Circles open later.", clip: "sisterhood", status: "live" as const },
  { n: 6, t: "Export or manage your data", d: "Profile & privacy lets you export everything or delete it in one step, and review what Muse remembers.", status: "live" as const, cta: { to: "/trust", label: "What's stored, and where" } },
];

export function HowItWorksPage() {
  usePageMeta("How it works · FEMORA Muse", "Six steps: explore, set up a private profile, record symptoms, explore insights with Muse, discover community, and manage your data.", "/how-it-works");
  return (
    <SiteLayout>
      <section className="mx-auto max-w-7xl px-5 pb-6 pt-32"><Reveal><Eyebrow>How it works</Eyebrow><h1 className="mt-3 max-w-3xl font-display text-6xl leading-tight">Six gentle steps.</h1>
        <p className="mt-4 max-w-2xl text-lg text-[#5a544b]">Every clip below is recorded from the real app and has a text description (use the captions button).</p></Reveal></section>
      <ol className="mx-auto max-w-7xl px-5 pb-20">{STEPS.map((s, k) => {
        const c = CLIPS.find((x) => x.id === s.clip);
        return (
          <li key={s.n} className="grid items-center gap-10 border-t border-black/10 py-14 lg:grid-cols-2">
            <Reveal className={k % 2 ? "lg:order-2" : ""}><span className="font-display text-7xl text-[#7c5f2b]">{String(s.n).padStart(2, "0")}</span>
              <h2 className="mt-2 font-display text-4xl">{s.t}</h2><div className="mt-2"><StatusPill s={s.status} /></div><p className="mt-3 text-lg text-[#5a544b]">{s.d}</p>
              {s.cta && <Link to={s.cta.to} className="mt-5 inline-flex rounded-full bg-[#17140f] px-5 py-3 text-[#f7f1e6]">{s.cta.label}</Link>}</Reveal>
            <Reveal delay={120}>{c ? <ClipPlayer c={c} /> : <div className="grid aspect-[16/10] place-items-center rounded-[20px] bg-[#f4f1ea] p-8 text-center font-display text-3xl text-[#3f5139]">{s.t}</div>}</Reveal>
          </li>);
      })}</ol>
    </SiteLayout>
  );
}
