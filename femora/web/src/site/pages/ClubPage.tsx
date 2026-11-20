import { useState } from "react";
import { Link } from "react-router-dom";
import { EyeOff, Flag, HandHeart, Lock, MessageSquareHeart, ShieldCheck, Sparkles, UserCheck } from "lucide-react";
import { SiteLayout, Eyebrow, StatusPill } from "../SiteLayout";
import { Reveal } from "../Reveal";
import { Botanicals } from "../Botanicals";
import { usePageMeta } from "../usePageMeta";
import { PLACES } from "../../modules/sisterhood/places";

// FICTIONAL preview profiles for illustrating the design. Not real members.
const SAMPLE = [
  { i: "AO", n: "Sample member A", c: "Perimenopause", x: 18, y: 30 }, { i: "LM", n: "Sample member B", c: "Food & cooking", x: 34, y: 62 },
  { i: "SR", n: "Sample member C", c: "Walking", x: 52, y: 22 }, { i: "KP", n: "Sample member D", c: "Career", x: 66, y: 58 },
  { i: "NB", n: "Sample member E", c: "Living alone", x: 82, y: 30 }, { i: "TJ", n: "Sample member F", c: "Book club", x: 46, y: 80 }, { i: "MV", n: "Sample member G", c: "Postmenopause", x: 88, y: 74 },
];
const CIRCLES = [
  { t: "Perimenopause", d: "Changing cycles, sleep, and what nobody tells you." }, { t: "Postmenopause", d: "Strength, bones, and the decades ahead." },
  { t: "Living alone", d: "Company without pressure; check-ins if you want them." }, { t: "Food & cooking", d: "Recipes from every kitchen, protein and calcium friendly." },
  { t: "Walking & yoga", d: "Gentle movement, local meet-ups where safe." }, { t: "Career & confidence", d: "Brain fog at work, negotiating, leading." },
  { t: "New to a country", d: "Finding care and friendship in a new place." }, { t: "Book club", d: "One book a month, one conversation." },
];
const FORMATS = [["Monthly Muse Circle", "A facilitated online circle on one theme, with a menopause-informed host."], ["Walk & Talk", "Small local walks organised by members, with safety guidance and public meeting points."], ["Kitchen Table", "Share a recipe from your culture; the group cooks it that week."], ["Ask the Expert", "Q&A with credentialed clinicians once verification is in place."]];

export function ClubPage() {
  usePageMeta("Sisterhood club · FEMORA Muse", "A women's club built on consent: verified organisations map today; moderated circles, anonymous lounge and Sister Match coming with secure accounts.", "/club");
  const [hover, setHover] = useState<number | null>(null);
  const regions = Object.entries(PLACES.reduce<Record<string, number>>((a, p) => { a[p.country] = (a[p.country] ?? 0) + 1; return a; }, {})).sort((a, b) => b[1] - a[1]);
  return (
    <SiteLayout dark>
      <section className="site-hero-bg relative overflow-hidden pb-20 pt-32 text-[#f7f1e6]">
        <Botanicals className="absolute -left-32 top-0 h-[640px] w-[640px] opacity-70" />
        <div className="relative mx-auto grid max-w-7xl items-center gap-12 px-5 lg:grid-cols-[1fr_1.1fr]">
          <Reveal><Eyebrow light>FEMORA Sisterhood</Eyebrow><h1 className="mt-3 font-display text-6xl leading-[1.05]">The members' club for women in every chapter.</h1>
            <p className="mt-5 max-w-lg text-lg text-[#ece4d4]">Circles, conversation and real-world connection, designed around consent, privacy and moderation from day one.</p>
            <div className="mt-6 flex flex-wrap gap-3"><span className="rounded-full bg-[#2f6a4a] px-3 py-1 text-xs font-semibold uppercase tracking-wider text-white">Map: available now</span><span className="rounded-full bg-white/15 px-3 py-1 text-xs font-semibold uppercase tracking-wider">Circles: coming soon</span></div></Reveal>
          {/* Member constellation */}
          <Reveal delay={120}>
            <figure className="relative aspect-[4/3] rounded-[28px] bg-white/[0.06] ring-1 ring-white/15 backdrop-blur" aria-label="Member constellation preview with fictional sample profiles">
              <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="absolute inset-0 h-full w-full" aria-hidden>
                {SAMPLE.flatMap((a, k) => SAMPLE.slice(k + 1).filter((_, j) => (k + j) % 3 === 0).map((b) => <line key={a.i + b.i} x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="#d7b57a" strokeOpacity={hover === k ? 0.7 : 0.22} strokeWidth="0.3" />))}
              </svg>
              {SAMPLE.map((m, k) => (
                <button key={m.i} onMouseEnter={() => setHover(k)} onMouseLeave={() => setHover(null)} onFocus={() => setHover(k)} onBlur={() => setHover(null)}
                  aria-label={`${m.n}, interested in ${m.c} (fictional preview)`} className="absolute -translate-x-1/2 -translate-y-1/2" style={{ left: `${m.x}%`, top: `${m.y}%` }}>
                  <span className={`grid h-12 w-12 place-items-center rounded-full font-display text-lg transition ${hover === k ? "scale-110 bg-[#d7b57a] text-[#17140f]" : "bg-[#f7f1e6] text-[#17140f]"}`}>{m.i}</span>
                  {hover === k && <span className="absolute left-1/2 top-14 w-max -translate-x-1/2 rounded-full bg-[#17140f] px-3 py-1 text-xs">{m.c}</span>}
                </button>))}
              <figcaption className="absolute bottom-3 left-4 text-xs text-[#d9cfbd]">Fictional preview profiles · not real members</figcaption>
            </figure>
          </Reveal>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-5 py-20">
        <Reveal className="flex flex-wrap items-end justify-between gap-4"><div><Eyebrow>Women's circles</Eyebrow><h2 className="mt-3 font-display text-5xl">Find your circle</h2></div><StatusPill s="soon" /></Reveal>
        <div className="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">{CIRCLES.map((c, k) => (
          <Reveal key={c.t} delay={(k % 4) * 80} className="group site-glass rounded-[24px] p-6 transition hover:-translate-y-1">
            <Sparkles size={20} className="text-[#7c5f2b]" /><h3 className="mt-3 font-display text-2xl">{c.t}</h3><p className="mt-1 text-[15px] text-[#5a544b]">{c.d}</p>
            <p className="mt-4 text-xs font-semibold uppercase tracking-wider text-[#3f5139]">Opens with moderated accounts</p></Reveal>))}</div>
      </section>

      <section className="bg-[#f4f1ea] py-20"><div className="mx-auto grid max-w-7xl gap-10 px-5 lg:grid-cols-2">
        <Reveal><Eyebrow>Club events</Eyebrow><h2 className="mt-3 font-display text-4xl">Event formats we're designing</h2>
          <p className="mt-2 text-[15px] text-[#5a544b]">Formats only. No events are scheduled yet, and we'll never list a host or expert we haven't verified.</p>
          <ul className="mt-6 space-y-4">{FORMATS.map(([t, d]) => <li key={t} className="rounded-[20px] bg-white/80 p-5 ring-1 ring-black/5"><b className="font-display text-xl font-normal">{t}</b><p className="text-[15px] text-[#5a544b]">{d}</p></li>)}</ul></Reveal>
        <div className="space-y-6">
          <Reveal delay={100} className="rounded-[24px] bg-[#17140f] p-6 text-[#f7f1e6]"><div className="flex items-center gap-2"><EyeOff size={18} className="text-[#d7b57a]" /><h2 className="font-display text-2xl">Anonymous Lounge</h2><span className="ml-auto text-xs uppercase tracking-wider text-[#d9cfbd]">Preview · sample posts</span></div>
            <ul className="mt-4 space-y-3 text-[15px]">
              <li className="rounded-[16px] bg-white/[0.07] p-4"><span className="text-xs text-[#d7b57a]">Moonlit Fern · sample</span><p>Does anyone else wake at 3am with their mind racing? What helps you?</p><span className="text-xs text-[#d9cfbd]">Replies are moderated before they're visible</span></li>
              <li className="rounded-[16px] bg-white/[0.07] p-4"><span className="text-xs text-[#d7b57a]">Quiet Harbour · sample</span><p>First week back at the gym after years. Small win, but mine.</p></li></ul></Reveal>
          <Reveal delay={180} className="site-glass rounded-[24px] p-6"><div className="flex items-center gap-2"><HandHeart size={18} className="text-[#3f5139]" /><h2 className="font-display text-2xl">Sister Match</h2><span className="ml-auto text-xs uppercase tracking-wider text-[#5a544b]">Preview</span></div>
            <p className="mt-2 text-[15px] text-[#5a544b]">Opt-in introductions based on interests you choose, never on health records. Both people must say yes before anything is shared.</p>
            <div className="mt-4 flex items-center gap-4 rounded-[18px] bg-white p-4 ring-1 ring-black/5"><span className="grid h-12 w-12 place-items-center rounded-full bg-[#3f5139] font-display text-lg text-white">LM</span>
              <div><b>Sample member B</b><p className="text-sm text-[#5a544b]">Shared interests: walking, cooking</p></div><span className="ml-auto rounded-full bg-[#f4f1ea] px-3 py-1 text-xs">Fictional</span></div></Reveal>
        </div>
      </div></section>

      <section className="mx-auto grid max-w-7xl gap-10 px-5 py-20 lg:grid-cols-[1fr_1.2fr]">
        <Reveal><Eyebrow>Global reach today</Eyebrow><h2 className="mt-3 font-display text-4xl">{PLACES.length} verified organisations</h2>
          <p className="mt-2 text-[15px] text-[#5a544b]">Menopause societies, support groups, public health and wellness directories, each checked at its official website.</p>
          <ul className="mt-6 space-y-2">{regions.map(([r, n]) => <li key={r} className="flex items-center gap-3"><span className="w-36 text-[15px]">{r}</span><span className="h-2.5 rounded-full bg-[#3f5139]" style={{ width: `${n * 36}px` }} /><span className="text-sm text-[#5a544b]">{n}</span></li>)}</ul>
          <Link to="/app/sisterhood" className="mt-6 inline-flex rounded-full bg-[#17140f] px-6 py-3 font-medium text-[#f7f1e6]">Open the live map</Link></Reveal>
        <Reveal delay={120} className="site-glass rounded-[28px] p-8"><h2 className="font-display text-3xl">Safety & consent come first</h2>
          <ul className="mt-5 grid gap-4 sm:grid-cols-2 text-[15px]">
            {[[UserCheck, "Verified accounts", "Circles open only with secure sign-in."], [ShieldCheck, "Human moderation", "Posts and introductions are moderated."], [Flag, "Report & block", "One tap, always available."], [Lock, "Health stays private", "Health records are never shown to other members."], [EyeOff, "Anonymous by choice", "Use a pseudonym in the lounge."], [MessageSquareHeart, "Mutual consent", "Nothing is shared without both people agreeing."]].map(([I, t, d]) => {
              const Icon = I as typeof Lock;
              return <li key={t as string} className="flex gap-3"><Icon size={20} className="mt-0.5 shrink-0 text-[#3f5139]" /><span><b className="font-medium">{t as string}</b><br /><span className="text-[#5a544b]">{d as string}</span></span></li>;
            })}</ul></Reveal>
      </section>
    </SiteLayout>
  );
}
