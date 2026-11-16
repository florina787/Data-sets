// Validated-rule safety layer. Runs BEFORE any provider, scripted or live. Rules, not model judgement.
import type { Reply } from "./types";

const CRISIS = [/\b(kill|hurt|harm)\s+(myself|me)\b/, /\bsuicid/, /\bend (my|it all|my life)\b/, /\bwant to die\b/, /\bno reason to live\b/, /\bself[- ]harm/];
const ABUSE = [/\b(he|she|they|partner|husband) (hits|hit|beats|threatens|threatened) me\b/, /\bi('m| am) not safe\b/];
const URGENT = [/\bchest pain\b/, /\bcan'?t breathe\b/, /\bfaint(ed|ing)\b/, /\bbleeding (after|since) (my )?(menopause|periods stopped)\b/, /\bpostmenopausal bleeding\b/, /\bsoaking (a|one) pad (every|each) hour\b/];

export function safetyCheck(text: string): Reply | null {
  const t = text.toLowerCase();
  if (CRISIS.some((r) => r.test(t)) || ABUSE.some((r) => r.test(t))) {
    return {
      safety: "crisis",
      text: "I'm really glad you told me. What you're feeling matters, and you deserve support from a person right now.\n" +
        "- If you are in immediate danger, call your local emergency number (for example 911, 999, 112).\n" +
        "- You can reach a crisis line any time: findahelpline.com lists free, confidential services in your country.\n" +
        "- If you can, tell someone you trust that you're struggling.\n" +
        "I'm an AI companion and can't provide crisis care, but I can stay here with you while you reach out. Would you like to tell me a little more about what's happening?",
      actions: [{ kind: "open", label: "Open Guardian (safety)", payload: "/app/guardian" }],
    };
  }
  if (URGENT.some((r) => r.test(t))) {
    return {
      safety: "urgent-medical",
      text: "That symptom should be checked by a clinician promptly, not tracked and watched.\n" +
        "- Chest pain, trouble breathing or fainting: call your local emergency number now.\n" +
        "- Any bleeding after periods have stopped for 12 months, or very heavy bleeding, needs a medical review soon [S3].\n" +
        "Would you like help writing down what happened, to share with a doctor?",
      sources: ["S3"],
      actions: [{ kind: "open", label: "Find a clinician", payload: "/app/care" }],
    };
  }
  return null;
}
