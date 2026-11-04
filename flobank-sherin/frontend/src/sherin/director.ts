/**
 * The Sherin director: one persistent character shared by every route. Choreography code awaits
 * walkTo / point / sleep, all of which honour pause, speed, skip (abort) and reduced motion.
 * It never computes or changes financial values or agent state.
 */
import { useSyncExternalStore } from "react";
import type { Pose } from "./Character";
import { sound } from "./sound";

export class Aborted extends Error { constructor() { super("choreography aborted"); } }

export interface Speech { text: string; tone: "info" | "success" | "warning" | "error"; synthetic?: boolean }
export interface CharState {
  x: number; pose: Pose; facing: 1 | -1; say: Speech | null; paused: boolean; speed: number; muted: boolean;
  reducedPref: boolean; collapsed: boolean; walking: boolean; fadeKey: number; journey: boolean; focus: string | null;
}

export interface WalkControls { done: Promise<void>; pause(): void; play(): void; stop(): void }
interface LaneImpl { walk(x: number, ms: number): WalkControls; jump(x: number): void; width(): number; left(): number }

const WALK_PX_PER_S = 190;
const load = <T,>(k: string, d: T): T => { try { const v = localStorage.getItem(`sherin.char.${k}`); return v === null ? d : (JSON.parse(v) as T); } catch { return d; } };
const save = (k: string, v: unknown) => { try { localStorage.setItem(`sherin.char.${k}`, JSON.stringify(v)); } catch { /* storage unavailable */ } };

class Director {
  state: CharState = { x: 120, pose: "idle", facing: 1, say: null, paused: false, speed: load("speed", 1), muted: load("muted", true),
    reducedPref: load("reduced", false), collapsed: load("collapsed", false), walking: false, fadeKey: 0, journey: false, focus: null };
  private listeners = new Set<() => void>();
  private lane: LaneImpl | null = null;
  private walkCtl: WalkControls | null = null;
  private gen = 0;
  private sayTimer: ReturnType<typeof setTimeout> | null = null;

  subscribe = (fn: () => void) => { this.listeners.add(fn); return () => { this.listeners.delete(fn); }; };
  get = () => this.state;
  private set(p: Partial<CharState>) { this.state = { ...this.state, ...p }; this.listeners.forEach((l) => l()); }

  attachLane(l: LaneImpl | null) { this.lane = l; }
  systemReduced() { try { return window.matchMedia("(prefers-reduced-motion: reduce)").matches; } catch { return false; } }
  reduced() { return this.state.reducedPref || this.systemReduced(); }

  // ---- user controls
  setSpeed(s: number) { this.set({ speed: s }); save("speed", s); }
  setMuted(m: boolean) { this.set({ muted: m }); save("muted", m); }
  setReduced(r: boolean) { this.set({ reducedPref: r }); save("reduced", r); }
  setCollapsed(c: boolean) { this.set({ collapsed: c }); save("collapsed", c); }
  setJourney(j: boolean) { this.set({ journey: j }); }
  pause() { this.set({ paused: true }); this.walkCtl?.pause(); }
  resume() { this.set({ paused: false }); this.walkCtl?.play(); }
  /** Cancel any running choreography (skip / jump / replay). Pending awaits reject with Aborted. */
  abort() { this.gen++; this.walkCtl?.stop(); this.walkCtl = null; this.set({ walking: false, paused: false, pose: this.state.pose === "walk" ? "idle" : this.state.pose }); }
  token() { return this.gen; }
  check(tok: number) { if (tok !== this.gen) throw new Aborted(); }

  // ---- primitives
  pose(p: Pose) { this.set({ pose: p }); if (!this.state.muted) { if (p === "success") sound.chime(); if (p === "warning" || p === "error") sound.alert(); } }
  say(text: string | null, tone: Speech["tone"] = "info", opts: { synthetic?: boolean; ttlMs?: number } = {}) {
    if (this.sayTimer) clearTimeout(this.sayTimer);
    this.set({ say: text ? { text, tone, synthetic: opts.synthetic } : null });
    if (text && opts.ttlMs) this.sayTimer = setTimeout(() => this.set({ say: null }), opts.ttlMs);
  }
  focus(selector: string | null) {
    document.querySelectorAll(".sherin-focus").forEach((e) => e.classList.remove("sherin-focus"));
    if (selector) document.querySelector(selector)?.classList.add("sherin-focus");
    this.set({ focus: selector });
  }

  /** Pausable, speed-scaled wait. */
  async sleep(ms: number, tok = this.gen) {
    let left = ms;
    while (left > 0) {
      this.check(tok);
      await new Promise((r) => setTimeout(r, 40));
      if (!this.state.paused) left -= 40 * this.state.speed;
    }
    this.check(tok);
  }

  xFor(target: number | string | Element | null): number | null {
    if (!this.lane || target === null) return null;
    if (typeof target === "number") return target <= 1 ? target * this.lane.width() : target;
    const el = typeof target === "string" ? document.querySelector(target) : target;
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return r.left + r.width / 2 - this.lane.left();
  }
  private clamp(x: number) { const w = this.lane?.width() ?? 800; return Math.max(40, Math.min(w - 60, x)); }

  /** Walk along the reserved lane to a fraction (0..1), a pixel x, a selector or an element. */
  async walkTo(target: number | string | Element | null, tok = this.gen, offset = 0) {
    const raw = this.xFor(target);
    if (raw === null || !this.lane) return;
    const x = this.clamp(raw + offset);
    const dx = x - this.state.x;
    if (Math.abs(dx) < 4) return;
    if (this.reduced()) { this.lane.jump(x); this.set({ x, facing: dx > 0 ? 1 : -1 }); return; }
    const facing: 1 | -1 = dx > 0 ? 1 : -1;
    if (facing !== this.state.facing) { this.set({ pose: "turn" }); await this.sleep(220, tok); this.set({ facing }); }
    this.set({ pose: "walk", walking: true });
    const ms = (Math.abs(dx) / WALK_PX_PER_S) * 1000 / this.state.speed;
    this.walkCtl = this.lane.walk(x, ms);
    if (this.state.paused) this.walkCtl.pause();
    try { await this.walkCtl.done; } finally { this.walkCtl = null; }
    this.check(tok);
    this.set({ x, pose: "idle", walking: false });
  }

  /** Walk to the target, face it and point at it, highlighting it. */
  async presentAt(selector: string, text: string, tok = this.gen, tone: Speech["tone"] = "info", pose: Pose = "point") {
    this.focus(selector);
    await this.walkTo(selector, tok, -70);
    this.set({ facing: 1 });
    this.pose(pose);
    this.say(text, tone);
  }

  /** Short scene transition for long jumps: fade out, reposition, fade in (no impractical walk). */
  async transitionTo(x: number, tok = this.gen) {
    if (!this.lane) return;
    const cx = this.clamp(x <= 1 ? x * this.lane.width() : x);
    this.set({ fadeKey: this.state.fadeKey + 1 });
    await this.sleep(this.reduced() ? 0 : 220, tok);
    this.lane.jump(cx);
    this.set({ x: cx, pose: "idle" });
  }

  setX(x: number) { this.set({ x }); }
}

export const sherin = new Director();

export function useSherin(): CharState {
  return useSyncExternalStore(sherin.subscribe, sherin.get, sherin.get);
}

/** Map a copilot answer to what Sherin should point at on the current page. */
export const FOCUS_BY_INTENT: Record<string, { selector: string; say: string }> = {
  why_spend: { selector: "#graph-d-drivers", say: "Here is the largest cost increase. Click a bar to inspect its cost records." },
  ai_cost: { selector: "#graph-d", say: "This is what I cost, by category. Click any category for the records." },
  bank_revenue: { selector: "#graph-a", say: "Revenue, expenditure and operating profit are here." },
  net_contribution: { selector: "#graph-b", say: "This waterfall shows how the net benefit is built." },
  tokens: { selector: "#graph-e", say: "Token consumption by provider and agent." },
  human_vs_ai: { selector: "#graph-c", say: "Human-only versus AI-assisted cost per verified task." },
  forecast: { selector: "#graph-f", say: "Scenario forecast. These are projections, not guarantees." },
  department: { selector: "#graph-h", say: "Financial value by department." },
  agent_productivity: { selector: "#graph-g", say: "Agent productivity economics." },
};

export async function focusForAnswer(intent: string) {
  const f = FOCUS_BY_INTENT[intent];
  const tok = sherin.token();
  try {
    if (f && document.querySelector(f.selector)) {
      document.querySelector(f.selector)!.scrollIntoView({ behavior: sherin.reduced() ? "auto" : "smooth", block: "center" });
      await sherin.sleep(450, tok);
      await sherin.presentAt(f.selector, f.say, tok);
    } else {
      const link = document.querySelector("[data-sherin-link]:last-of-type");
      if (link) await sherin.walkTo(link, tok);
      sherin.pose(f ? "point" : "idle");
      if (f) sherin.say("Open the linked dashboard and I'll show you the chart.", "info", { ttlMs: 6000 });
    }
  } catch (e) { if (!(e instanceof Aborted)) throw e; }
}
