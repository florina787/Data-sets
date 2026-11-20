import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, ArrowRight } from "lucide-react";
import { SLIDES, shot } from "./media";

/** Accessible product carousel: swipe (scroll-snap), buttons, arrow keys; announces the current slide. */
export function Carousel() {
  const track = useRef<HTMLDivElement>(null);
  const [i, setI] = useState(0);
  useEffect(() => {
    const t = track.current; if (!t) return;
    const on = () => { const w = (t.firstElementChild as HTMLElement | null)?.offsetWidth ?? 1; setI(Math.min(SLIDES.length - 1, Math.round(t.scrollLeft / (w + 24)))); };
    t.addEventListener("scroll", on, { passive: true }); return () => t.removeEventListener("scroll", on);
  }, []);
  const go = (n: number) => {
    const t = track.current; if (!t) return;
    const k = Math.max(0, Math.min(SLIDES.length - 1, n));
    const el = t.children[k] as HTMLElement | undefined;
    t.scrollTo?.({ left: el ? el.offsetLeft - t.offsetLeft : 0, behavior: window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
    setI(k);
  };
  return (
    <section aria-roledescription="carousel" aria-label="FEMORA product tour" className="relative"
      onKeyDown={(e) => { if (e.key === "ArrowRight") { e.preventDefault(); go(i + 1); } if (e.key === "ArrowLeft") { e.preventDefault(); go(i - 1); } }}>
      <div ref={track} tabIndex={0} className="site-track flex snap-x snap-mandatory gap-6 overflow-x-auto pb-6 outline-none" aria-label="Slides: use left and right arrow keys">
        {SLIDES.map((s, k) => (
          <article key={s.id} aria-roledescription="slide" aria-label={`${k + 1} of ${SLIDES.length}: ${s.title}`}
            className={`site-slide w-[86%] shrink-0 snap-center sm:w-[70%] lg:w-[62%] ${k === i ? "is-active" : ""}`}>
            <div className="overflow-hidden rounded-[24px] bg-[#17140f] p-2 shadow-[0_30px_80px_-30px_rgba(23,20,15,0.45)]">
              <img src={shot(s.shot, 1280)} srcSet={`${shot(s.shot, 640)} 640w, ${shot(s.shot, 1280)} 1280w`} sizes="(max-width: 640px) 86vw, 62vw"
                alt={s.alt} loading={k < 2 ? "eager" : "lazy"} decoding="async" width={1280} height={800} className="aspect-[16/10] w-full rounded-[18px] object-cover object-top" />
            </div>
            <div className="mt-4 flex items-start gap-4">
              <span className="font-display text-4xl text-[#7c5f2b]">{String(k + 1).padStart(2, "0")}</span>
              <div><h3 className="font-display text-2xl">{s.title}</h3><p className="text-muted">{s.text} <Link className="text-[#3f5139] underline" to={s.to}>Explore {s.title}</Link></p></div>
            </div>
          </article>))}
      </div>
      <div className="mt-2 flex items-center gap-3">
        <button onClick={() => go(i - 1)} disabled={i === 0} aria-label="Previous slide" className="grid h-12 w-12 place-items-center rounded-full border border-[#17140f]/15 bg-white disabled:opacity-40"><ArrowLeft size={18} /></button>
        <button onClick={() => go(i + 1)} disabled={i === SLIDES.length - 1} aria-label="Next slide" className="grid h-12 w-12 place-items-center rounded-full bg-[#17140f] text-[#f7f1e6] disabled:opacity-40"><ArrowRight size={18} /></button>
        <div className="ml-2 flex gap-1.5" aria-hidden="true">{SLIDES.map((s, k) => <span key={s.id} className={`h-1.5 rounded-full transition-all ${k === i ? "w-8 bg-[#7c5f2b]" : "w-3 bg-[#17140f]/15"}`} />)}</div>
        <p className="sr-only" aria-live="polite">Slide {i + 1} of {SLIDES.length}: {SLIDES[i].title}</p>
      </div>
    </section>
  );
}
