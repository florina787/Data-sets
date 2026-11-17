import { useEffect, useLayoutEffect, useRef, useState, useSyncExternalStore } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { X } from "lucide-react";
import { Button } from "../../components/ui";
import { tourStore } from "./tours";

/** Spotlight tour. Accessible: focusable dialog, Esc closes, works with reduced motion. */
export function TourOverlay() {
  const { tour, step } = useSyncExternalStore(tourStore.subscribe, tourStore.get);
  const nav = useNavigate();
  const loc = useLocation();
  const [rect, setRect] = useState<DOMRect | null>(null);
  const card = useRef<HTMLDivElement>(null);
  const s = tour?.steps[step];

  useEffect(() => { if (tour && loc.pathname !== tour.path) nav(tour.path); }, [tour, loc.pathname, nav]);

  useLayoutEffect(() => {
    if (!s) { setRect(null); return; }
    let tries = 0, id = 0;
    const find = () => {
      const el = document.querySelector(`[data-tour="${s.target}"]`) as HTMLElement | null;
      if (el) {
        el.scrollIntoView?.({ block: "center", behavior: window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
        id = window.setTimeout(() => setRect(el.getBoundingClientRect()), 250);
      } else if (tries++ < 20) id = window.setTimeout(find, 150); // wait for lazy pages
      else setRect(null);
    };
    find();
    const onResize = () => { const el = document.querySelector(`[data-tour="${s.target}"]`); if (el) setRect(el.getBoundingClientRect()); };
    addEventListener("resize", onResize); addEventListener("scroll", onResize, true);
    return () => { clearTimeout(id); removeEventListener("resize", onResize); removeEventListener("scroll", onResize, true); };
  }, [s, loc.pathname]);

  useEffect(() => { card.current?.focus(); }, [step, tour]);
  useEffect(() => { const k = (e: KeyboardEvent) => { if (e.key === "Escape") tourStore.stop(); }; addEventListener("keydown", k); return () => removeEventListener("keydown", k); }, []);

  if (!tour || !s) return null;
  const pad = 8;
  const w = 340, vw = window.innerWidth, vh = window.innerHeight;
  const H = 200;
  let top = vh / 2 - H / 2, left = vw / 2 - w / 2;
  if (rect) {
    const tall = rect.height > vh * 0.5;
    if (tall && rect.right + 16 + w < vw) { left = rect.right + 16; top = Math.min(Math.max(16, rect.top + 16), vh - H - 16); }       // beside tall targets
    else if (rect.bottom + 16 + H < vh) { top = rect.bottom + 16; left = rect.left + rect.width / 2 - w / 2; }                          // below
    else if (rect.top - 16 - H > 0) { top = rect.top - 16 - H; left = rect.left + rect.width / 2 - w / 2; }                              // above
    else { top = vh - H - 16; }
    left = Math.min(Math.max(16, left), vw - w - 16);
  }
  return (
    <div className="fixed inset-0 z-[60]" aria-live="polite">
      {rect ? <div aria-hidden className="pointer-events-none fixed rounded-f-sm ring-2 ring-accent transition-all duration-300 motion-reduce:transition-none"
        style={{ top: rect.top - pad, left: rect.left - pad, width: rect.width + pad * 2, height: rect.height + pad * 2, boxShadow: "0 0 0 9999px rgb(10 8 6 / 0.55)" }} />
        : <div aria-hidden className="fixed inset-0 bg-black/55" />}
      <div ref={card} tabIndex={-1} role="dialog" aria-modal="true" aria-label={`${tour.title}: step ${step + 1} of ${tour.steps.length}`}
        className="f-enter fixed rounded-f bg-surface p-5 shadow-f outline-none ring-1 ring-line" style={{ top, left, width: w }}>
        <div className="flex items-start gap-2"><span className="text-xs uppercase tracking-widest text-accent">{tour.title} · {step + 1}/{tour.steps.length}</span>
          <button className="ml-auto text-muted hover:text-ink" aria-label="Close tour" onClick={tourStore.stop}><X size={16} /></button></div>
        <h3 className="mt-1 font-display text-xl">{s.title}</h3>
        <p className="mt-1 text-sm text-muted">{s.text}</p>
        <div className="mt-4 flex items-center gap-2">
          <button className="text-sm text-muted underline" onClick={tourStore.stop}>Skip tour</button>
          <div className="ml-auto flex gap-2">{step > 0 && <Button size="sm" onClick={tourStore.back}>Back</Button>}
            <Button size="sm" variant="primary" onClick={tourStore.next}>{step + 1 === tour.steps.length ? "Done" : "Next"}</Button></div>
        </div>
      </div>
    </div>
  );
}
