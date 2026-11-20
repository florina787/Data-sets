import { useEffect, useRef, useState } from "react";
import { Play, Pause, Captions } from "lucide-react";
import { clip as clipSrc, type Clip } from "./media";

/** Poster first; the video loads only when she presses play. One clip plays at a time. Text transcript always available. */
let current: HTMLVideoElement | null = null;
export function ClipPlayer({ c, compact = false }: { c: Clip; compact?: boolean }) {
  const src = clipSrc(c.id);
  const v = useRef<HTMLVideoElement>(null);
  const [loaded, setLoaded] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [showText, setShowText] = useState(false);
  useEffect(() => () => { if (current === v.current) current = null; }, []);
  function toggle() {
    if (!loaded) { setLoaded(true); return; }
    const el = v.current; if (!el) return;
    if (el.paused) { if (current && current !== el) current.pause(); current = el; void el.play(); } else el.pause();
  }
  useEffect(() => { if (loaded && v.current) { if (current && current !== v.current) current.pause(); current = v.current; void v.current.play().catch(() => {}); } }, [loaded]);
  return (
    <figure className="site-clip">
      <div className="relative overflow-hidden rounded-[20px] bg-[#17140f] ring-1 ring-black/5">
        {loaded ? (
          <video ref={v} className="aspect-[16/10] w-full" poster={src.poster} muted loop playsInline controls={false}
            onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)} aria-label={`${c.title}: ${c.caption}`}>
            <source src={src.webm} type="video/webm" /><source src={src.mp4} type="video/mp4" />
            <img src={src.gif} alt={c.caption} loading="lazy" />
          </video>
        ) : <img src={src.poster} alt={`${c.title}: ${c.caption}`} loading="lazy" decoding="async" width={960} height={600} className="aspect-[16/10] w-full object-cover" />}
        <button onClick={toggle} aria-label={playing ? `Pause ${c.title}` : `Play ${c.title}`}
          className="absolute bottom-3 left-3 flex items-center gap-2 rounded-full bg-[#f7f1e6]/95 px-4 py-2 text-sm font-medium text-[#17140f] shadow-lg backdrop-blur">
          {playing ? <Pause size={16} /> : <Play size={16} />} {playing ? "Pause" : "Play"}
        </button>
        <button onClick={() => setShowText(!showText)} aria-expanded={showText} aria-label={`Show text description of ${c.title}`}
          className="absolute bottom-3 right-3 rounded-full bg-[#17140f]/80 p-2 text-[#f7f1e6] backdrop-blur"><Captions size={16} /></button>
      </div>
      <figcaption className={`mt-3 ${compact ? "text-sm" : ""}`}><b className="font-display text-xl font-normal">{c.title}</b><span className="block text-sm text-muted">{c.caption}</span></figcaption>
      {showText && <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm text-muted">{c.transcript.map((t) => <li key={t}>{t}</li>)}</ol>}
    </figure>
  );
}
