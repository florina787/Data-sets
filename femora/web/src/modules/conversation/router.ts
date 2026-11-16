// Lightweight orchestration: safety rules first, then the selected provider. One provider serves every mode;
// modes change prompting/tone, not infrastructure (docs/AUDIT.md §6).
import { safetyCheck } from "./safety";
import { scriptedProvider } from "./scriptedProvider";
import type { ChatProvider, Reply, ReplyContext } from "./types";

let active: ChatProvider = scriptedProvider;
export const setProvider = (p: ChatProvider) => { active = p; };
export const currentProvider = () => active;

export async function reply(ctx: ReplyContext): Promise<Reply & { provider: string }> {
  const safe = safetyCheck(ctx.text);
  if (safe) return { ...safe, provider: "safety-rules" };
  try {
    return { ...(await active.respond(ctx)), provider: active.id };
  } catch {
    // Live model failed: degrade to the offline scripted provider instead of erroring.
    return { ...(await scriptedProvider.respond(ctx)), provider: scriptedProvider.id };
  }
}
