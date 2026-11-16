// llama.cpp adapter: talks to a llama.cpp `llama-server` the user runs herself (OpenAI-compatible API).
// Static hosting can't run llama.cpp; this connects to e.g. http://localhost:8080 on her own machine.
import type { ChatProvider, Reply, ReplyContext } from "./types";
import { SYSTEM_PROMPT } from "./persona";

export interface LlamaConfig { url: string; enabled: boolean; maxTokens: number }
export const DEFAULT_LLAMA: LlamaConfig = { url: "http://localhost:8080", enabled: false, maxTokens: 512 };

const clean = (u: string) => u.replace(/\/+$/, "");

/** Verifies the server answers. Returns the model id(s) it reports, or throws with a readable reason. */
export async function testLlama(url: string, fetcher: typeof fetch = fetch): Promise<string> {
  const r = await fetcher(`${clean(url)}/v1/models`, { signal: AbortSignal.timeout(5000) });
  if (!r.ok) throw new Error(`Server answered ${r.status}`);
  const j = (await r.json()) as { data?: { id: string }[] };
  return j.data?.map((m) => m.id).join(", ") || "connected";
}

/** Facts Muse may use, built deterministically. The model must not invent numbers beyond these. */
export function contextBlock(c: ReplyContext): string {
  const p = c.profile;
  return [`User's first name: ${p.name}.`, p.stage ? `Self-reported stage: ${p.stage}.` : "Menopause stage: not recorded; do not assume.",
    c.memory.length ? `Approved memories: ${c.memory.join("; ")}.` : "No approved memories.",
    c.food.weekDays ? `Food log, last ${c.food.weekDays} logged days: protein ${Math.round(c.food.weekProtein)} g total; alcohol on ${c.food.weekAlcoholDays} days.` : "No food logged recently.",
    c.journey?.lastPeriod ? `Last recorded period start: ${c.journey.lastPeriod} (${c.journey.daysSinceLast} days ago); average cycle ${c.journey.avgCycle ?? "unknown"} days.` : "No cycles recorded.",
    c.journey?.topSymptoms14d.length ? `Symptoms logged in 14 days: ${c.journey.topSymptoms14d.map(([n, k]) => `${n} ×${k}`).join(", ")}.` : "",
    `Conversation mode: ${c.mode}.`, c.brief ? "Answer precisely and briefly." : ""].filter(Boolean).join(" ");
}

export function llamaProvider(cfg: LlamaConfig, fetcher: typeof fetch = fetch): ChatProvider {
  return {
    id: "llama.cpp", label: `llama.cpp at ${clean(cfg.url)}`, live: true,
    async respond(c): Promise<Reply> {
      const messages = [{ role: "system", content: `${SYSTEM_PROMPT}\n\n${contextBlock(c)}` },
        ...c.history.slice(-12).map((m) => ({ role: m.role, content: m.text }))];
      const r = await fetcher(`${clean(cfg.url)}/v1/chat/completions`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages, max_tokens: cfg.maxTokens, temperature: 0.7, stream: false }),
      });
      if (!r.ok) throw new Error(`llama.cpp ${r.status}`);
      const j = (await r.json()) as { choices?: { message?: { content?: string } }[] };
      const text = j.choices?.[0]?.message?.content?.trim();
      if (!text) throw new Error("empty response");
      return { text };
    },
  };
}
