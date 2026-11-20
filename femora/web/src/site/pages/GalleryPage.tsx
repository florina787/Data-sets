import { useMemo, useState } from "react";
import { SiteLayout, Eyebrow } from "../SiteLayout";
import { Reveal } from "../Reveal";
import { ClipPlayer } from "../ClipPlayer";
import { CLIPS, clip, type ClipCategory } from "../media";
import { usePageMeta } from "../usePageMeta";

const CATS: ("All" | ClipCategory)[] = ["All", "Getting started", "Muse", "Health", "Food", "Safety", "Community", "Design"];

export function GalleryPage() {
  usePageMeta("Gallery · FEMORA Muse", "Short recordings of the real FEMORA Muse app: onboarding, Muse conversations, menopause journey, food, health dashboard, Guardian, sisterhood map and themes.", "/gallery");
  const [cat, setCat] = useState<(typeof CATS)[number]>("All");
  const list = useMemo(() => CLIPS.filter((c) => cat === "All" || c.category === cat), [cat]);
  return (
    <SiteLayout>
      <section className="mx-auto max-w-7xl px-5 pb-6 pt-32"><Reveal><Eyebrow>Gallery</Eyebrow><h1 className="mt-3 font-display text-6xl">See it move.</h1>
        <p className="mt-4 max-w-2xl text-lg text-[#5a544b]">Ten short recordings of the real app. Nothing plays until you press play, and every clip has a text description. Recorded with example entries; a fresh install starts empty.</p></Reveal>
        <div role="group" aria-label="Filter by category" className="mt-8 flex flex-wrap gap-2">{CATS.map((c) => <button key={c} aria-pressed={cat === c} onClick={() => setCat(c)} className={`rounded-full px-4 py-2 text-sm ${cat === c ? "bg-[#17140f] text-[#f7f1e6]" : "bg-white/70 ring-1 ring-black/5"}`}>{c}</button>)}</div>
      </section>
      <section className="mx-auto grid max-w-7xl gap-10 px-5 pb-24 md:grid-cols-2" aria-live="polite">
        {list.map((c) => <div key={c.id}><ClipPlayer c={c} compact /><a className="mt-1 inline-block text-xs text-[#5a544b] underline" href={clip(c.id).gif}>Animated GIF version</a></div>)}
      </section>
    </SiteLayout>
  );
}
