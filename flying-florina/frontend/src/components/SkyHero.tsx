import { useMemo } from "react";
import { worldPath } from "@/lib/world";

const W = 520, H = 260;
const LAT_TOP = 80, LAT_BOTTOM = -58;
const px = (lon: number) => ((lon + 180) / 360) * W;
const py = (lat: number) => ((LAT_TOP - lat) / (LAT_TOP - LAT_BOTTOM)) * H;

/** Fictional demo hubs (same cities as the synthetic dataset) and the routes drawn between them. */
const HUBS: Record<string, [number, number]> = {
  Hamburg: [9.99, 53.63], Chicago: [-87.9, 41.98], Dubai: [55.36, 25.25], Brisbane: [153.12, -27.38], Santiago: [-70.79, -33.39], Nairobi: [36.93, -1.32],
};
const ROUTES: [string, string, number][] = [["Chicago", "Hamburg", 9], ["Hamburg", "Dubai", 7], ["Dubai", "Brisbane", 11], ["Santiago", "Nairobi", 13]];

function arc(a: [number, number], b: [number, number]): string {
  const [x1, y1, x2, y2] = [px(a[0]), py(a[1]), px(b[0]), py(b[1])];
  const mx = (x1 + x2) / 2, my = (y1 + y2) / 2 - Math.min(70, Math.hypot(x2 - x1, y2 - y1) * 0.35);
  return `M${x1.toFixed(1)},${y1.toFixed(1)} Q${mx.toFixed(1)},${my.toFixed(1)} ${x2.toFixed(1)},${y2.toFixed(1)}`;
}

/** Original hero card: frosted glass, serif headline, flight paths with planes moving along them. */
export function SkyHero({ stats }: { stats: { value: string; label: string }[] }) {
  const land = useMemo(() => worldPath(W, H, LAT_TOP, LAT_BOTTOM), []);
  return (
    <section className="sky-hero glass-card relative overflow-hidden" data-testid="sky-hero">
      <div className="grid items-center gap-6 p-6 sm:p-8 lg:grid-cols-[1fr_1.15fr]">
        <div>
          <p className="label tracking-[0.2em]">Flying Florina 3.0</p>
          <h2 className="font-serif mt-2 text-3xl leading-tight sm:text-[2.6rem]">Reach every aircraft.<br />Even offline.</h2>
          <p className="muted mt-3 max-w-md text-sm leading-relaxed">
            Forecast parts, map the network, simulate disruptions and explain every answer, on one machine with a local Qwen model. People still make every decision.
          </p>
          <div className="mt-6 grid grid-cols-2 gap-5">
            {stats.map((s) => (
              <div key={s.label}>
                <p className="font-serif text-4xl leading-none sm:text-5xl">{s.value}</p>
                <p className="muted mt-2 text-xs">{s.label}</p>
              </div>
            ))}
          </div>
        </div>
        <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Flight paths between the demo maintenance hubs">
          <path d={land} className="sky-land" />
          {ROUTES.map(([a, b, dur], i) => {
            const d = arc(HUBS[a], HUBS[b]);
            return (
              <g key={i}>
                <path id={`route-${i}`} d={d} className="sky-route" />
                <g className="sky-plane">
                  <path d="M-7 0 L5 -1.2 L8 0 L5 1.2Z M-1 0 L-4 -6 L-2 -6 L3 0Z M-1 0 L-4 6 L-2 6 L3 0Z M-6 0 L-8 -3 L-7 -3 L-5 0Z M-6 0 L-8 3 L-7 3 L-5 0Z" />
                  <animateMotion dur={`${dur}s`} repeatCount="indefinite" rotate="auto" begin={`${-i * 2.3}s`}>
                    <mpath href={`#route-${i}`} />
                  </animateMotion>
                </g>
              </g>
            );
          })}
          {Object.entries(HUBS).map(([n, [lo, la]]) => (
            <g key={n}>
              <circle cx={px(lo)} cy={py(la)} r={7} className="sky-hub-halo" />
              <circle cx={px(lo)} cy={py(la)} r={3.2} className="sky-hub" />
            </g>
          ))}
        </svg>
      </div>
      <p className="muted px-6 pb-4 text-[11px] sm:px-8">Fictional hubs and synthetic data · runs fully offline · not affiliated with IFS</p>
    </section>
  );
}
