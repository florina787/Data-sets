import { Link } from "react-router-dom";
import { ArrowRight, BadgeCheck, HeartHandshake, Lock, MessageCircleHeart, ShieldAlert, Sparkles } from "lucide-react";
import { SiteLayout, Eyebrow, StatusPill } from "../SiteLayout";
import { Reveal } from "../Reveal";
import { Carousel } from "../Carousel";
import { Botanicals } from "../Botanicals";
import { phone, shot } from "../media";
import { usePageMeta } from "../usePageMeta";
import { waitlistHref } from "./PricingPage";

const B = import.meta.env.BASE_URL;
const PILLARS = [
  { icon: MessageCircleHeart, title: "Heard", text: "Muse listens first, encourages often, can make you laugh, and knows when to say 'please talk to a clinician.'" },
  { icon: Sparkles, title: "Understood", text: "Cycles, symptoms, sleep, food from every kitchen: patterns explained from your own records, with honest uncertainty." },
  { icon: HeartHandshake, title: "Connected", text: "A map of verified menopause societies and support groups worldwide, and a sisterhood built on consent." },
];

export function HomePage() {
  usePageMeta("FEMORA Muse · Every woman's journey deserves to be understood", "Meet Muse, your personal AI wellness companion. Understand your menopause journey, discover meaningful connections, and feel supported through every change.", "/");
  return (
    <SiteLayout dark>
      {/* ---------- Cinematic hero ---------- */}
      <section className="site-hero-bg relative overflow-hidden pt-28 text-[#f7f1e6] md:pt-32">
        <Botanicals className="absolute -left-24 top-10 h-[720px] w-[720px] opacity-90" />
        <div aria-hidden className="pointer-events-none absolute -right-40 top-0 h-[40rem] w-[40rem] rounded-full bg-[radial-gradient(circle,rgba(215,181,122,0.28),transparent_60%)]" />
        <div className="relative mx-auto grid max-w-7xl gap-12 px-5 pb-24 lg:grid-cols-[1.15fr_1fr] lg:pb-32">
          <div className="pt-6 lg:pt-14">
            <p className="site-line text-sm font-semibold uppercase tracking-[0.35em] text-[#e7cf9f]">FEMORA Muse · women's health & life</p>
            <h1 className="mt-6 font-display text-[3.2rem] leading-[1.02] sm:text-6xl md:text-7xl xl:text-[5.4rem]">
              <span className="site-line block" style={{ animationDelay: "120ms" }}>Every woman's journey</span>{" "}
              <span className="site-line block italic text-[#e7cf9f]" style={{ animationDelay: "280ms" }}>deserves to be understood.</span>
            </h1>
            <p className="site-line mt-7 max-w-xl text-lg leading-relaxed text-[#ece4d4]" style={{ animationDelay: "460ms" }}>
              Meet Muse, your personal AI wellness companion. Understand your menopause journey, discover meaningful connections, and feel supported through every change.
            </p>
            <div className="site-line mt-9 flex flex-wrap items-center gap-3" style={{ animationDelay: "620ms" }}>
              <a href={waitlistHref} className="inline-flex items-center gap-2 rounded-full bg-[#d7b57a] px-6 py-3.5 font-medium text-[#17140f]">Start Your 30-Day Free Trial <ArrowRight size={18} /></a>
              <Link to="/demo" className="inline-flex items-center gap-2 rounded-full px-6 py-3.5 font-medium text-[#f7f1e6] ring-1 ring-[#f7f1e6]/35 hover:bg-white/10">Explore the Interactive Demo</Link>
            </div>
            <p className="site-line mt-4 text-sm text-[#d9cfbd]" style={{ animationDelay: "760ms" }}>Free trial coming soon: the button above joins the waitlist by email. No payment details, no account needed to explore.</p>
          </div>
          <div className="relative hidden min-h-[520px] md:block" aria-hidden="true">
            <img src={shot("home", 1280)} alt="" width={1280} height={800} fetchPriority="high" decoding="async"
              className="site-float absolute right-0 top-8 w-[92%] rounded-[22px] shadow-[0_40px_120px_-30px_rgba(0,0,0,0.7)] ring-1 ring-white/10" style={{ ["--r" as string]: "-2deg" }} />
            <img src={phone("journey")} alt="" width={420} height={910} loading="lazy" decoding="async"
              className="site-float absolute -bottom-6 left-0 w-[38%] rounded-[30px] shadow-[0_40px_120px_-30px_rgba(0,0,0,0.75)] ring-4 ring-[#17140f]" style={{ ["--r" as string]: "3deg", animationDelay: "-3s" }} />
            <img src={phone("guardian")} alt="" width={420} height={910} loading="lazy" decoding="async"
              className="site-float absolute -bottom-10 right-6 w-[30%] rounded-[26px] shadow-[0_40px_120px_-30px_rgba(0,0,0,0.75)] ring-4 ring-[#17140f]" style={{ ["--r" as string]: "-4deg", animationDelay: "-6s" }} />
          </div>
        </div>
      </section>

      {/* ---------- Pillars ---------- */}
      <section className="mx-auto max-w-7xl px-5 py-24">
        <Reveal><Eyebrow>Meet Muse</Eyebrow><h2 className="mt-3 max-w-3xl font-display text-5xl leading-tight">A calm, private companion for every chapter of midlife.</h2></Reveal>
        <div className="mt-12 grid gap-6 md:grid-cols-3">
          {PILLARS.map((p, k) => (
            <Reveal key={p.title} delay={k * 120} className="site-glass rounded-[28px] p-8">
              <p.icon className="text-[#3f5139]" size={28} strokeWidth={1.5} />
              <h3 className="mt-5 font-display text-3xl">{p.title}</h3><p className="mt-2 leading-relaxed text-[#5a544b]">{p.text}</p>
            </Reveal>))}
        </div>
      </section>

      {/* ---------- Sliding product showcase ---------- */}
      <section className="bg-[#f4f1ea] py-24">
        <div className="mx-auto max-w-7xl px-5">
          <Reveal className="flex flex-wrap items-end justify-between gap-4"><div><Eyebrow>The product</Eyebrow><h2 className="mt-3 font-display text-5xl">Nine views of FEMORA Muse</h2></div>
            <p className="max-w-md text-[#5a544b]">Real screens from the app. Swipe, use the arrows or your keyboard.</p></Reveal>
          <div className="mt-10"><Carousel /></div>
        </div>
      </section>

      {/* ---------- Real data ---------- */}
      <section className="mx-auto max-w-7xl px-5 py-24">
        <div className="grid items-center gap-12 lg:grid-cols-[1fr_1.3fr]">
          <Reveal><Eyebrow>Trained on real data</Eyebrow><h2 className="mt-3 font-display text-5xl leading-tight">Context from 10,375 real women, not guesswork.</h2>
            <p className="mt-4 text-lg leading-relaxed text-[#5a544b]">Muse's menopause-timing model was trained with open-source tools on the U.S. national health survey (CDC NHANES 2013–2018). It gives population context, like "among women aged 48, about a quarter had reached menopause". It never predicts any one woman's final period.</p>
            <Link to="/trust" className="mt-6 inline-flex items-center gap-2 font-medium text-[#3f5139]">How we use evidence <ArrowRight size={16} /></Link></Reveal>
          <Reveal delay={150}><img src={`${B}media/chart-menopause-curve.svg`} alt="Share of U.S. women who had reached natural menopause by age, crossing 50% at age 51" loading="lazy" width={1600} height={760} className="w-full rounded-[24px] shadow-[0_30px_80px_-40px_rgba(23,20,15,0.4)]" /></Reveal>
        </div>
      </section>

      {/* ---------- Safety & trust strip ---------- */}
      <section className="bg-[#17140f] py-20 text-[#f7f1e6]">
        <div className="mx-auto grid max-w-7xl gap-8 px-5 md:grid-cols-4">
          {[[Lock, "Private by default", "Records stay on your device. Export or delete anytime."], [ShieldAlert, "Safety first", "Crisis and urgent symptoms always route to real help."], [BadgeCheck, "Nothing invented", "Verified sources only. No fake events, offers or experts."], [HeartHandshake, "Supports clinicians", "No diagnoses, no dose changes, no final-period predictions."]].map(([I, t, d], k) => {
            const Icon = I as typeof Lock;
            return <Reveal key={t as string} delay={k * 90}><Icon size={26} strokeWidth={1.5} className="text-[#d7b57a]" /><h3 className="mt-4 font-display text-2xl">{t as string}</h3><p className="mt-1 text-[#d9cfbd]">{d as string}</p></Reveal>;
          })}
        </div>
      </section>

      {/* ---------- Sisterhood teaser ---------- */}
      <section className="mx-auto grid max-w-7xl items-center gap-12 px-5 py-24 lg:grid-cols-2">
        <Reveal><img src={shot("sisterhood", 1280)} srcSet={`${shot("sisterhood", 640)} 640w, ${shot("sisterhood", 1280)} 1280w`} sizes="(max-width: 1024px) 100vw, 50vw" alt="Sisterhood map with verified organisations" loading="lazy" width={1280} height={800} className="w-full rounded-[24px] shadow-[0_30px_80px_-40px_rgba(23,20,15,0.45)]" /></Reveal>
        <Reveal delay={120}><Eyebrow>Sisterhood</Eyebrow><h2 className="mt-3 font-display text-5xl leading-tight">A women's club, built on consent.</h2>
          <p className="mt-4 text-lg leading-relaxed text-[#5a544b]">Today: a world map of 15 menopause societies and support organisations, each verified at its official website. Coming next: moderated circles, an anonymous lounge and consent-first introductions.</p>
          <div className="mt-6 flex flex-wrap gap-3"><StatusPill s="live" /><StatusPill s="soon" /></div>
          <Link to="/club" className="mt-6 inline-flex items-center gap-2 font-medium text-[#3f5139]">Step inside the club <ArrowRight size={16} /></Link></Reveal>
      </section>

      {/* ---------- Final CTA ---------- */}
      <section className="site-hero-bg relative overflow-hidden py-24 text-center text-[#f7f1e6]">
        <Botanicals className="absolute -right-20 -top-20 h-[560px] w-[560px] opacity-70" />
        <Reveal className="relative mx-auto max-w-3xl px-5"><h2 className="font-display text-5xl leading-tight md:text-6xl">Your health, your pace, your Muse.</h2>
          <div className="mt-8 flex flex-wrap justify-center gap-3"><Link to="/demo" className="rounded-full bg-[#d7b57a] px-6 py-3.5 font-medium text-[#17140f]">Explore the Interactive Demo</Link>
            <Link to="/app" className="rounded-full px-6 py-3.5 font-medium ring-1 ring-[#f7f1e6]/35">Open the app</Link></div></Reveal>
      </section>
    </SiteLayout>
  );
}
