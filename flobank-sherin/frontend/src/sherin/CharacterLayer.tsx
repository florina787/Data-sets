import { useEffect, useRef } from "react";
import { Link, useLocation } from "react-router-dom";
import { animate, motion, useMotionValue } from "framer-motion";
import { Compass, EyeOff } from "lucide-react";
import { SherinCharacter } from "./Character";
import { Aborted, sherin, useSherin } from "./director";
import { sound } from "./sound";
import { SherinAvatar } from "../components/SherinAvatar";

export const LANE_H = 150;

const ROUTE_STOPS: Record<string, { x: number; line: string }> = {
  "/": { x: 0.08, line: "Money first: revenue, expenditure, what I cost and what I was worth." },
  "/journey": { x: 0.04, line: "Press Play Journey and I'll walk you through all seven scenes." },
  "/chat": { x: 0.3, line: "Ask me anything about FLO Bank's money. I answer from the records." },
  "/portfolio": { x: 0.18, line: "Portfolio holdings. Assets under management are never counted as revenue." },
  "/guardian": { x: 0.3, line: "I check every proposal against mandatory controls before anyone can approve it." },
  "/harness": { x: 0.42, line: "This is my agent team. Start a run and I'll follow each agent." },
  "/azure": { x: 0.5, line: "Pipelines, Data Factory, Functions and AKS, each with its cost." },
  "/python": { x: 0.5, line: "Upload a Python file and I'll debug it, with a diff for a human to approve." },
  "/tokens": { x: 0.62, line: "Every token, local and paid, with its real compute cost." },
  "/savings": { x: 0.62, line: "Verified savings, and what it cost me to produce them." },
  "/metrics": { x: 0.72, line: "Live latency, failures and budget alerts." },
  "/approvals": { x: 0.8, line: "Decisions waiting for an authorized human." },
  "/esg": { x: 0.8, line: "ESG validation and compliance events." },
  "/reports": { x: 0.88, line: "Board-ready figures with definitions and reconciliation." },
  "/settings": { x: 0.88, line: "Currency, baselines, roles, and my character settings." },
};

const TONE = { info: "border-flo-200 bg-white text-ink", success: "border-flo-500 bg-flo-50 text-flo-900", warning: "border-[#EED9B5] bg-amber-light text-[#6B4510]", error: "border-[#EFC9C6] bg-red-light text-red" };

/** Persistent character layer. It lives in the app shell, so it survives route changes. It never receives pointer events. */
export function CharacterLayer() {
  const s = useSherin();
  const loc = useLocation();
  const laneRef = useRef<HTMLDivElement>(null);
  const mv = useMotionValue(s.x);

  useEffect(() => {
    sherin.attachLane({
      width: () => laneRef.current?.getBoundingClientRect().width ?? window.innerWidth,
      left: () => laneRef.current?.getBoundingClientRect().left ?? 0,
      jump: (x) => mv.set(x),
      walk: (x, ms) => {
        let resolve!: () => void;
        const done = new Promise<void>((r) => (resolve = r));
        const c = animate(mv, x, { duration: ms / 1000, ease: "linear" });
        c.then(() => resolve());
        return { done, pause: () => c.pause(), play: () => c.play(), stop: () => { c.stop(); resolve(); } };
      },
    });
    return () => sherin.attachLane(null);
  }, [mv]);

  // Footsteps while walking (only when unmuted).
  useEffect(() => {
    if (!s.walking || s.muted || s.paused) return;
    const t = setInterval(() => sound.step(), 310 / s.speed);
    return () => clearInterval(t);
  }, [s.walking, s.muted, s.paused, s.speed]);

  // Route-aware presence: walk (or briefly transition) to this page's stop and say one line.
  useEffect(() => {
    if (sherin.get().journey) return;
    const stop = ROUTE_STOPS[loc.pathname] ?? { x: 0.1, line: "" };
    sherin.abort();
    sherin.focus(null);
    const tok = sherin.token();
    (async () => {
      const w = laneRef.current?.getBoundingClientRect().width ?? 1000;
      const far = Math.abs(stop.x * w - sherin.get().x) > w * 0.45;
      if (far) await sherin.transitionTo(stop.x, tok);
      else await sherin.walkTo(stop.x, tok);
      sherin.pose("idle");
      if (stop.line) sherin.say(stop.line, "info", { ttlMs: 7000 });
    })().catch((e) => { if (!(e instanceof Aborted)) throw e; });
  }, [loc.pathname]);

  const reduced = s.reducedPref || sherin.systemReduced();
  if (s.collapsed) {
    return (
      <button type="button" onClick={() => sherin.setCollapsed(false)} aria-label="Show Sherin" data-testid="sherin-show"
        className="fixed bottom-4 right-4 z-30 flex items-center gap-2 rounded-full border border-line bg-white py-1 pl-1 pr-3 text-xs font-semibold text-flo-900 shadow-lg">
        <SherinAvatar size="sm" />Show Sherin
      </button>
    );
  }
  const w = laneRef.current?.getBoundingClientRect().width ?? 1000;
  const bubbleRight = s.x < w * 0.55;
  return (
    <div ref={laneRef} data-testid="sherin-layer" data-pose={s.pose} data-walking={s.walking ? "true" : "false"} aria-hidden={false}
      className={`pointer-events-none fixed bottom-0 left-0 right-0 z-30 lg:left-64 ${reduced ? "sherin-reduced" : ""}`} style={{ height: LANE_H }}>
      <div className="absolute inset-x-0 bottom-0 h-24 bg-gradient-to-t from-white/80 to-transparent" aria-hidden />
      <motion.div style={{ x: mv }} className="absolute bottom-2 left-0" data-testid="sherin-walker">
        <motion.div key={s.fadeKey} initial={{ opacity: reduced ? 1 : 0, y: reduced ? 0 : 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: reduced ? 0 : 0.35 }}
          style={{ marginLeft: -40, ["--sherin-walk" as any]: `${0.62 / s.speed}s` }} className={s.paused ? "sherin-paused" : ""}>
          <SherinCharacter pose={s.pose} facing={s.facing} height={136} />
        </motion.div>
        {s.say && (
          <div role="status" data-testid="sherin-speech"
            className={`absolute bottom-16 w-max max-w-[min(380px,60vw)] rounded-2xl border px-3 py-2 text-[13px] leading-snug shadow-md ${TONE[s.say.tone]} ${bubbleRight ? "left-12" : "right-16"}`}>
            {s.say.synthetic && <span className="mr-1 rounded-full bg-gold-light px-1.5 text-[10px] font-bold uppercase text-[#7A5D1E]">synthetic</span>}
            {s.say.text}
          </div>
        )}
      </motion.div>
      <div className="pointer-events-auto absolute bottom-2 right-3 flex gap-1.5">
        {loc.pathname !== "/journey" && <Link to="/journey" className="inline-flex items-center gap-1 rounded-full border border-line bg-white/95 px-2.5 py-1 text-[11px] font-semibold text-flo-800 shadow-sm"><Compass className="h-3.5 w-3.5" />Guided journey</Link>}
        <button type="button" onClick={() => sherin.setCollapsed(true)} aria-label="Hide Sherin" className="rounded-full border border-line bg-white/95 p-1.5 text-muted shadow-sm"><EyeOff className="h-3.5 w-3.5" /></button>
      </div>
    </div>
  );
}
