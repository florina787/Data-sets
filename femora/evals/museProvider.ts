// promptfoo custom provider: runs FEMORA Muse's real conversation router (safety rules + offline library) in Node.
import { reply } from "../web/src/modules/conversation/router";
import type { ReplyContext } from "../web/src/modules/conversation/types";

export default class MuseOffline {
  id() { return "femora-muse-offline"; }
  async callApi(prompt: string, context?: { vars?: Record<string, unknown> }) {
    const v = context?.vars ?? {};
    const ctx: ReplyContext = {
      text: prompt, mode: (v.mode as ReplyContext["mode"]) ?? "talk", brief: Boolean(v.brief), history: [], memory: [],
      profile: { name: "Bea", cuisine: ["North America"] },
      journey: { cyclesLogged: 0, topSymptoms14d: [], age: v.age ? Number(v.age) : undefined, forecast: { status: "too-few" } },
      food: { weekProtein: 280, weekDays: 7, weekAlcoholDays: 2, weekCaffeineAvg: 120, todayCalcium: 400, calciumTarget: 1200, proteinTarget: 60 },
    };
    const r = await reply(ctx);
    return { output: r.text, metadata: { provider: r.provider, safety: r.safety ?? null } };
  }
}
