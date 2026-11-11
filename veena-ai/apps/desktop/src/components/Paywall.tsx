// In-app pricing screen. Opens when a feature's free uses are used up (or sign-in is needed), and from
// Settings. Payment happens on Stripe's own page in the browser; the app then asks VEENA's server for
// the new entitlement every few seconds, so it unlocks without a restart. Nothing is trusted locally.
import { useEffect, useState } from "react";
import { useApp } from "../stores/app";
import { Button, Input } from "./ui";

interface Account {
  unlimited: boolean;
  plan: string | null;
  credit_minutes: number;
  trial_remaining: Record<string, number>;
  trial_uses: number;
}
interface Status {
  enabled: boolean;
  signed_in?: boolean;
  offline?: boolean;
  account?: Account | null;
}
const NAMES: Record<string, string> = { chat: "Ask anything", documents: "Documents", screen: "Screen", meeting: "Meetings", interview: "Interview practice" };
const PLANS = [
  { id: "unlimited_monthly", label: "Unlimited · Monthly", price: "$74.95 / month" },
  { id: "unlimited_annual", label: "Unlimited · Annual", price: "$299.95 / year" },
];
const PACKS = [
  { id: "credits_1", label: "1 credit · 60 min", price: "$19.00" },
  { id: "credits_3", label: "3 credits · 180 min", price: "$29.50" },
  { id: "credits_8", label: "8 credits · 480 min", price: "$59.00" },
  { id: "credits_15", label: "15 credits · 900 min", price: "$88.50" },
];

export function Paywall() {
  const { api, paywall, toast } = useApp();
  const [st, setSt] = useState<Status | null>(null);
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [sent, setSent] = useState(false);
  const [waiting, setWaiting] = useState<{ before: Account | null } | null>(null);
  const close = () => {
    useApp.setState({ paywall: null });
    setWaiting(null);
  };
  const load = async () => {
    if (!api) return null;
    const s = await api.get<Status>("/api/billing");
    setSt(s);
    return s;
  };
  useEffect(() => {
    if (paywall) void load().catch(() => setSt(null));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paywall]);
  // After checkout opens: poll the server until it confirms a new entitlement.
  useEffect(() => {
    if (!waiting) return;
    const t = setInterval(async () => {
      const s = await load().catch(() => null);
      const a = s?.account, b = waiting.before;
      if (a && (a.unlimited && !b?.unlimited || a.credit_minutes > (b?.credit_minutes ?? 0))) {
        toast("success", a.unlimited ? `VEENA Unlimited (${a.plan}) is active.` : `Payment confirmed: ${a.credit_minutes} credit minutes.`);
        close();
      }
    }, 4000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [waiting]);
  if (!paywall) return null;
  const a = st?.account;
  const act = async (fn: () => Promise<unknown>) => {
    try {
      await fn();
      await load();
    } catch (e) {
      toast("error", (e as Error).message);
    }
  };
  const buy = (pkg: string) =>
    void act(async () => {
      const r = await api!.post<{ url: string }>("/api/billing/checkout", { package: pkg });
      setWaiting({ before: a ?? null });
      window.open(r.url, "_blank"); // Stripe-hosted checkout in the default browser
    });
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-espresso/60 p-4" role="dialog" aria-modal="true" aria-labelledby="pw-title">
      <div className="max-h-[90vh] w-full max-w-xl overflow-y-auto rounded-2xl bg-ivory p-6 shadow-2xl">
        <h2 id="pw-title" className="text-xl font-semibold text-espresso">
          Keep going with VEENA
        </h2>
        <p className="mt-1 text-sm text-bark">{paywall.message.replace(/ See pricing: \S+/, "")}</p>
        {!st?.enabled ? (
          <p className="mt-4 text-sm text-bark">Plans are not available in this version.</p>
        ) : !st.signed_in ? (
          <div className="mt-4 grid gap-2">
            <p className="text-sm text-bark">Sign in with your email to get 3 free uses of every feature. No card needed.</p>
            <Input type="email" placeholder="you@example.com" value={email} onChange={(e) => setEmail(e.target.value)} aria-label="Email" />
            {sent && <Input inputMode="numeric" placeholder="6-digit code" value={code} onChange={(e) => setCode(e.target.value)} aria-label="Code" />}
            <Button variant="primary" onClick={() => void act(async () => (sent ? api!.post("/api/billing/sign-in", { email, code }) : api!.post("/api/billing/sign-in", { email }).then(() => setSent(true))))}>
              {sent ? "Sign in" : "Email me a code"}
            </Button>
          </div>
        ) : (
          <>
            {a && !a.unlimited && (
              <ul className="mt-4 grid gap-1 text-sm text-bark" aria-label="Free uses remaining">
                {Object.entries(a.trial_remaining).map(([f, n]) => (
                  <li key={f} className="flex justify-between border-b border-cream py-1">
                    <span>{NAMES[f] ?? f}</span>
                    <span className={n === 0 ? "font-semibold text-caramel" : ""}>
                      {n} of {a.trial_uses} free uses remaining
                    </span>
                  </li>
                ))}
                <li className="flex justify-between py-1">
                  <span>Credits (meetings and interviews)</span>
                  <span>{a.credit_minutes} minutes</span>
                </li>
              </ul>
            )}
            <h3 className="mt-5 text-sm font-semibold text-espresso">Unlimited · every feature</h3>
            <div className="mt-2 grid gap-2 sm:grid-cols-2">
              {PLANS.map((p) => (
                <Button key={p.id} variant="primary" onClick={() => buy(p.id)}>
                  {p.label} — {p.price}
                </Button>
              ))}
            </div>
            <h3 className="mt-5 text-sm font-semibold text-espresso">Credits · meeting and interview time</h3>
            <div className="mt-2 grid gap-2 sm:grid-cols-2">
              {PACKS.map((p) => (
                <Button key={p.id} onClick={() => buy(p.id)}>
                  {p.label} — {p.price}
                </Button>
              ))}
            </div>
            {waiting && (
              <p className="mt-4 rounded-xl bg-cream p-3 text-sm text-bark" role="status">
                Complete the payment in your browser. This window updates when VEENA's server confirms it; nothing unlocks before then.
              </p>
            )}
            <p className="mt-4 text-xs text-caramel">Prices in USD; taxes may apply. Payments by Stripe; VEENA never sees your card. Cancel Unlimited anytime.</p>
          </>
        )}
        <div className="mt-5 flex justify-end">
          <Button onClick={close}>Close</Button>
        </div>
      </div>
    </div>
  );
}
