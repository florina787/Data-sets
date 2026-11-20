// Billing & entitlement ABSTRACTION. No payments are active. The browser is never the source of truth
// for subscriptions: production entitlements must come from an authenticated server (see docs/SUBSCRIPTIONS.md).
export type PlanId = "free" | "plus" | "circle";
export type Feature = "offline-muse" | "tracking" | "food" | "guardian" | "sisterhood-map" | "hosted-ai" | "sync" | "circles" | "lounge" | "sister-match" | "priority-support";

export interface Plan { id: PlanId; name: string; tagline: string; price: string; features: Feature[]; aiAllowance: string; trial: boolean }

/** Prices are intentionally not set. They'll be published, with terms, before any checkout exists. */
export const PLANS: Plan[] = [
  { id: "free", name: "FEMORA Free", tagline: "Everything that runs privately on your device.", price: "Free", trial: false,
    features: ["offline-muse", "tracking", "food", "guardian", "sisterhood-map"], aiAllowance: "Unlimited offline Muse on your device. Optional: your own local llama.cpp model." },
  { id: "plus", name: "FEMORA Plus", tagline: "Hosted AI and encrypted sync across devices.", price: "To be announced", trial: true,
    features: ["offline-muse", "tracking", "food", "guardian", "sisterhood-map", "hosted-ai", "sync", "priority-support"], aiAllowance: "A monthly hosted-AI allowance, published before launch and shown in-app with a live counter." },
  { id: "circle", name: "FEMORA Circle", tagline: "Plus, with moderated sisterhood circles.", price: "To be announced", trial: true,
    features: ["offline-muse", "tracking", "food", "guardian", "sisterhood-map", "hosted-ai", "sync", "circles", "lounge", "sister-match", "priority-support"], aiAllowance: "As Plus, plus community features with moderation and safety tools." },
];

export const FEATURE_LABEL: Record<Feature, string> = {
  "offline-muse": "Muse conversation (offline, on-device)", tracking: "Journey, body & planner tracking", food: "Food & sugar insights", guardian: "Guardian safety tools",
  "sisterhood-map": "Verified sisterhood map", "hosted-ai": "Hosted AI conversation", sync: "Encrypted multi-device sync", circles: "Moderated women's circles",
  lounge: "Anonymous lounge", "sister-match": "Consent-first Sister Match", "priority-support": "Priority support",
};

export const TRIAL_DAYS = 30;

/** Pure trial maths, for the future server and for showing honest dates. */
export function trialWindow(start: Date, days = TRIAL_DAYS) {
  const end = new Date(start); end.setDate(end.getDate() + days);
  const reminder = new Date(end); reminder.setDate(reminder.getDate() - 3);
  return { start, end, reminder };
}

export interface Entitlement { plan: PlanId; status: "none" | "trialing" | "active" | "expired" | "cancelled"; trialEndsAt?: string; source: "server" }

/** Any real provider (e.g. a payments company) must implement this behind a server; the browser only displays results. */
export interface BillingProvider {
  readonly available: boolean;
  readonly reason?: string;
  getEntitlement(): Promise<Entitlement>;
  startTrial(plan: PlanId): Promise<{ ok: false; reason: string } | { ok: true; entitlement: Entitlement }>;
}

/** The only provider shipped today: billing is not available, and nothing is ever charged. */
export const noBilling: BillingProvider = {
  available: false,
  reason: "Subscriptions aren't available yet. No payment details are collected, and nothing can be charged.",
  async getEntitlement() { return { plan: "free", status: "none", source: "server" }; },
  async startTrial() { return { ok: false, reason: "Trials open once secure accounts and billing are approved. Join the waitlist to hear first." }; },
};

export const hasFeature = (plan: PlanId, f: Feature) => PLANS.find((p) => p.id === plan)!.features.includes(f);
