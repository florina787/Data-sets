import { Check, Minus, Info } from "lucide-react";
import { Link } from "react-router-dom";
import { SiteLayout, Eyebrow, StatusPill } from "../SiteLayout";
import { Reveal } from "../Reveal";
import { usePageMeta } from "../usePageMeta";
import { FEATURE_LABEL, PLANS, TRIAL_DAYS, noBilling, trialWindow, type Feature } from "../../modules/billing/entitlements";

export const waitlistHref = "mailto:florinaregius@yahoo.com?subject=" + encodeURIComponent("FEMORA Muse: free-trial waitlist") + "&body=" + encodeURIComponent("Please add me to the FEMORA Muse free-trial waitlist. (No health information needed.)");
const ALL: Feature[] = ["offline-muse", "tracking", "food", "guardian", "sisterhood-map", "hosted-ai", "sync", "circles", "lounge", "sister-match", "priority-support"];

export function PricingPage() {
  usePageMeta("Pricing & free trial · FEMORA Muse", "FEMORA Free, Plus and Circle: proposed plans, transparent entitlements and a 30-day free trial planned for paid features. No payments are active.", "/pricing");
  const w = trialWindow(new Date());
  const fmt = (d: Date) => d.toLocaleDateString(undefined, { day: "numeric", month: "long", year: "numeric" });
  return (
    <SiteLayout>
      <section className="mx-auto max-w-7xl px-5 pb-10 pt-32">
        <Reveal><Eyebrow>Pricing</Eyebrow><h1 className="mt-3 max-w-3xl font-display text-6xl leading-tight">Simple, honest plans.</h1>
          <p className="mt-4 max-w-2xl text-lg text-[#5a544b]">FEMORA Free works fully today. Paid plans are proposals: prices and terms will be published before any checkout exists.</p></Reveal>
        <div role="status" className="mt-6 flex items-start gap-3 rounded-[18px] bg-[#7c5f2b]/10 p-4 text-[15px] text-[#4a3a1c]"><Info size={18} className="mt-0.5 shrink-0" />{noBilling.reason}</div>
      </section>

      <section className="mx-auto grid max-w-7xl gap-6 px-5 lg:grid-cols-3">
        {PLANS.map((p, k) => (
          <Reveal key={p.id} delay={k * 100} className={`flex flex-col rounded-[28px] p-8 ${p.id === "plus" ? "bg-[#17140f] text-[#f7f1e6]" : "site-glass"}`}>
            <div className="flex items-center gap-2"><h2 className="font-display text-3xl">{p.name}</h2>{p.id === "free" ? <StatusPill s="live" /> : <StatusPill s="soon" onDark={p.id === "plus"} />}</div>
            <p className={`mt-1 ${p.id === "plus" ? "text-[#d9cfbd]" : "text-[#5a544b]"}`}>{p.tagline}</p>
            <p className="mt-6 font-display text-4xl">{p.price}</p>
            {p.trial && <p className={`mt-1 text-sm ${p.id === "plus" ? "text-[#e7cf9f]" : "text-[#6a4f22]"}`}>{TRIAL_DAYS}-day free trial planned</p>}
            <ul className="mt-6 space-y-2 text-[15px]">{p.features.map((f) => <li key={f} className="flex gap-2"><Check size={18} className={p.id === "plus" ? "text-[#d7b57a]" : "text-[#2f6a4a]"} />{FEATURE_LABEL[f]}</li>)}</ul>
            <p className={`mt-5 text-sm ${p.id === "plus" ? "text-[#d9cfbd]" : "text-[#5a544b]"}`}><b>AI usage:</b> {p.aiAllowance}</p>
            <div className="mt-auto pt-8">{p.id === "free"
              ? <Link to="/app" className="inline-flex rounded-full bg-[#17140f] px-6 py-3 font-medium text-[#f7f1e6]">Open the app, free</Link>
              : <a href={waitlistHref} className={`inline-flex rounded-full px-6 py-3 font-medium ${p.id === "plus" ? "bg-[#d7b57a] text-[#17140f]" : "bg-[#17140f] text-[#f7f1e6]"}`}>Join the waitlist</a>}</div>
          </Reveal>))}
      </section>

      <section className="mx-auto max-w-7xl px-5 py-20">
        <Reveal><h2 className="font-display text-4xl">What each plan includes</h2></Reveal>
        <div className="mt-6 overflow-x-auto rounded-[24px] bg-white/70 ring-1 ring-black/5">
          <table className="w-full min-w-[640px] text-left text-[15px]"><caption className="sr-only">Feature entitlements by plan</caption>
            <thead className="bg-[#f4f1ea]"><tr><th scope="col" className="px-5 py-4">Feature</th>{PLANS.map((p) => <th key={p.id} scope="col" className="px-5 py-4">{p.name}</th>)}</tr></thead>
            <tbody>{ALL.map((f) => <tr key={f} className="border-t border-black/5"><th scope="row" className="px-5 py-3 font-normal">{FEATURE_LABEL[f]}</th>
              {PLANS.map((p) => <td key={p.id} className="px-5 py-3">{p.features.includes(f) ? <><Check size={18} className="text-[#2f6a4a]" aria-hidden /><span className="sr-only">Included</span></> : <><Minus size={18} className="text-[#a59d90]" aria-hidden /><span className="sr-only">Not included</span></>}</td>)}</tr>)}</tbody>
          </table>
        </div>
      </section>

      <section id="trial" className="bg-[#f4f1ea] py-20">
        <div className="mx-auto grid max-w-7xl gap-10 px-5 lg:grid-cols-2">
          <Reveal><Eyebrow>The proposed free trial</Eyebrow><h2 className="mt-3 font-display text-4xl">Clear dates. No surprises.</h2>
            <ul className="mt-6 space-y-3 text-[15px]">
              <li>• {TRIAL_DAYS} days of Plus or Circle features, once per account, enforced on our server.</li>
              <li>• If a trial started today, it would end on <b>{fmt(w.end)}</b>, with a reminder on <b>{fmt(w.reminder)}</b>.</li>
              <li>• <b>No automatic billing.</b> When the trial ends you return to Free unless you explicitly choose a paid plan.</li>
              <li>• Cancel anytime in one step. No hidden charges.</li>
              <li>• Your records stay yours: on-device data is never deleted because a trial or plan ends; synced copies can be exported or deleted at any time.</li>
            </ul></Reveal>
          <Reveal delay={120} className="site-glass rounded-[28px] p-8"><h2 className="font-display text-3xl">How billing will work (when approved)</h2>
            <ul className="mt-4 space-y-2 text-[15px] text-[#4a443c]">
              <li>• Authenticated accounts; entitlements checked on a secure server, never trusted from the browser.</li>
              <li>• Trial start and expiry timestamps, usage counted server-side, rate limits and abuse controls.</li>
              <li>• A payment provider connected server-side with idempotent webhooks; no secret keys ever ship to this website.</li>
            </ul>
            <p className="mt-4 text-sm text-[#5a544b]">Full design: <a className="underline" href="https://github.com/florina787/femora/blob/main/femora/docs/SUBSCRIPTIONS.md">docs/SUBSCRIPTIONS.md</a></p></Reveal>
        </div>
      </section>
    </SiteLayout>
  );
}
