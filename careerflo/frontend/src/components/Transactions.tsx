import { ArrowDownRight, ArrowUpRight, Bell, Receipt } from "lucide-react";
import { useMemo, useState } from "react";
import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { cn } from "@/lib/utils";

/** Billing amounts are exact: always two decimals. */
const money = (v: number, cur?: string | null) =>
  new Intl.NumberFormat("en-CA", { style: "currency", currency: (cur || "CAD").toUpperCase(), minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(v);

export type Txn = {
  id: string; status: "paid" | "failed" | "refunded" | string; amount_cents: number; refunded_cents?: number;
  currency: string; plan?: string | null; url?: string | null; paid_at?: string | null; created_at?: string | null;
};
type Sub = { status: string; current_period_end?: string | null; cancel_at_period_end?: boolean } | null;

const RANGES = { "1M": 30, "3M": 91, "6M": 182, "1Y": 365, ALL: Infinity } as const;
type Range = keyof typeof RANGES;
const DAY = 864e5;

export const net = (t: Txn) => (t.status === "failed" ? 0 : t.amount_cents - (t.refunded_cents ?? 0));

/** Summarise real transactions for a time window: total in the window, change vs. the previous equal window, cumulative series. */
export function summarise(txns: Txn[], range: Range, now = Date.now()) {
  const when = (t: Txn) => t.paid_at ?? t.created_at;
  const dated = txns.filter((t) => when(t)).map((t) => ({ ...t, ts: new Date(when(t)!).getTime() })).sort((a, b) => a.ts - b.ts);
  const days = RANGES[range];
  const start = days === Infinity ? (dated[0]?.ts ?? now) : now - days * DAY;
  const inWin = dated.filter((t) => t.ts >= start && t.ts <= now);
  const prevStart = days === Infinity ? -Infinity : start - days * DAY;
  const prev = dated.filter((t) => t.ts >= prevStart && t.ts < start);
  const total = inWin.reduce((s, t) => s + net(t), 0);
  const prevTotal = prev.reduce((s, t) => s + net(t), 0);
  const delta = total - prevTotal;
  const pct = days === Infinity || prevTotal === 0 ? null : delta / prevTotal;
  let run = 0;
  const series = [{ ts: start, label: new Date(start).toLocaleDateString(), value: 0 }];
  for (const t of inWin) { run += net(t); series.push({ ts: t.ts, label: new Date(t.ts).toLocaleDateString(), value: run / 100 }); }
  series.push({ ts: now, label: new Date(now).toLocaleDateString(), value: run / 100 });
  return { total, delta, pct, series, count: inWin.length, currency: (dated.at(-1)?.currency ?? "CAD").toUpperCase() };
}

export function alertsFor(txns: Txn[], sub: Sub) {
  const out: { tone: "coral" | "amber" | "sky"; text: string }[] = [];
  for (const t of txns.filter((x) => x.status === "failed").slice(0, 3)) out.push({ tone: "coral", text: `Payment of ${money(t.amount_cents / 100, t.currency)} failed — update your card in the billing portal.` });
  if (sub?.status === "past_due") out.push({ tone: "coral", text: "Subscription is past due. Stripe will retry; access continues during the retry window." });
  if (sub?.cancel_at_period_end && sub.current_period_end) out.push({ tone: "amber", text: `Subscription ends on ${new Date(sub.current_period_end).toLocaleDateString()} — no further charges.` });
  else if (sub?.current_period_end && sub.status === "active") out.push({ tone: "sky", text: `Renews on ${new Date(sub.current_period_end).toLocaleDateString()}.` });
  for (const t of txns.filter((x) => (x.refunded_cents ?? 0) > 0).slice(0, 3)) out.push({ tone: "sky", text: `Refund of ${money((t.refunded_cents ?? 0) / 100, t.currency)} issued.` });
  return out;
}

/** Dark "market ticker" card for billing transactions — real Stripe-synchronised records only. */
export function TransactionsCard({ txns, sub, mode, title = "Billing", asOf = new Date() }: { txns: Txn[]; sub: Sub; mode?: string; title?: string; asOf?: Date }) {
  const [tab, setTab] = useState<"overview" | "transactions" | "alerts">("overview");
  const [range, setRange] = useState<Range>("ALL");
  const s = useMemo(() => summarise(txns, range, asOf.getTime()), [txns, range, asOf]);
  const alerts = alertsFor(txns, sub);
  const up = s.delta >= 0;
  const empty = txns.length === 0;
  return (
    <section aria-label="Transactions" className="overflow-hidden rounded-[28px] bg-[#0b0d0f] p-6 text-white shadow-lift ring-1 ring-white/5 sm:p-7"
      style={{ backgroundImage: "radial-gradient(120% 80% at 100% 0%, #1b2a1f 0%, transparent 55%)" }}>
      <div className="flex items-center justify-between">
        <div className="flex gap-1 rounded-full bg-white/[.06] p-1 text-[12.5px]" role="tablist">
          {(["overview", "transactions", "alerts"] as const).map((t) => (
            <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)}
              className={cn("rounded-full px-3.5 py-1.5 capitalize transition", tab === t ? "bg-white/15 text-white" : "text-white/60 hover:text-white")}>
              {t}{t === "alerts" && alerts.length > 0 && <span className="ml-1 rounded-full bg-[#2bd576]/25 px-1.5 text-[10px] text-[#7dfab0]">{alerts.length}</span>}
            </button>
          ))}
        </div>
        {mode && <span className="hidden whitespace-nowrap rounded-full bg-white/[.06] px-2.5 py-1 text-[11px] text-white/60 sm:inline">Stripe {mode} mode</span>}
      </div>

      {tab === "overview" && (
        <>
          <p className="mt-6 flex items-center gap-2 text-[13px] text-white/70"><Receipt className="h-4 w-4" />{title} · total paid</p>
          <div className="mt-1 flex items-end gap-3">
            <p className="font-sans text-[40px] font-semibold leading-none tracking-tight tabular-nums sm:text-[44px]">{money(s.total / 100, s.currency)}</p>
            <span className="mb-1 text-[12px] font-medium text-white/45">{s.currency}</span>
            {!empty && (up ? <ArrowUpRight className="mb-1 h-7 w-7 text-[#2bd576]" /> : <ArrowDownRight className="mb-1 h-7 w-7 text-[#ff6b6b]" />)}
          </div>
          <div className="mt-3 flex items-center gap-2 text-[13px] tabular-nums">
            {empty ? <span className="text-white/50">No transactions yet</span> : (
              <>
                <span className={up ? "text-[#2bd576]" : "text-[#ff6b6b]"}>{up ? "+" : "−"}{money(Math.abs(s.delta) / 100, s.currency)}</span>
                <span className={cn("rounded-md px-2 py-0.5", up ? "bg-[#2bd576]/15 text-[#7dfab0]" : "bg-[#ff6b6b]/15 text-[#ffb0b0]")}>
                  {s.pct == null ? (range === "ALL" ? "all time" : "new") : `${up ? "+" : ""}${(s.pct * 100).toFixed(2)}%`}
                </span>
                <span className="text-white/45">{s.count} transaction{s.count === 1 ? "" : "s"}</span>
              </>
            )}
          </div>
          <p className="mt-4 text-[12px] text-white/45">As of {asOf.toLocaleString(undefined, { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" })} · synced from Stripe{mode && <span className="sm:hidden"> · {mode} mode</span>}</p>
          <div className="mt-5 flex justify-between gap-1 text-[12.5px] sm:justify-start sm:gap-2">
            {(Object.keys(RANGES) as Range[]).map((r) => (
              <button key={r} onClick={() => setRange(r)} aria-pressed={range === r}
                className={cn("rounded-lg px-3 py-1.5 transition", range === r ? "bg-white/15 text-white" : "text-white/55 hover:text-white")}>{r}</button>
            ))}
          </div>
          <div className="-mx-6 mt-4 h-44 sm:-mx-7">
            <ResponsiveContainer>
              <AreaChart data={s.series} margin={{ top: 8, right: 0, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="txfill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#2bd576" stopOpacity={0.45} />
                    <stop offset="100%" stopColor="#2bd576" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="label" hide />
                <YAxis hide domain={[0, "dataMax"]} />
                <Tooltip contentStyle={{ background: "#14171a", border: "1px solid #ffffff1a", borderRadius: 12, color: "white" }}
                  formatter={(v: number) => [money(v, s.currency), "cumulative"]} />
                <Area type="stepAfter" dataKey="value" stroke={empty ? "#ffffff33" : "#2bd576"} strokeWidth={2} fill={empty ? "transparent" : "url(#txfill)"} isAnimationActive={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
          {empty && <p className="-mt-24 mb-16 text-center text-[13px] text-white/50">Your payments will appear here once Stripe confirms them.</p>}
        </>
      )}

      {tab === "transactions" && (
        <ul className="mt-5 divide-y divide-white/[.06]">
          {empty && <li className="py-8 text-center text-[13px] text-white/50">No transactions yet.</li>}
          {[...txns].sort((a, b) => (b.paid_at ?? b.created_at ?? "").localeCompare(a.paid_at ?? a.created_at ?? "")).map((t) => (
            <li key={t.id} className="flex items-center gap-3 py-3 text-[13.5px]">
              <span className={cn("grid h-9 w-9 place-items-center rounded-full", t.status === "failed" ? "bg-[#ff6b6b]/15 text-[#ff6b6b]" : "bg-[#2bd576]/15 text-[#2bd576]")}>
                {t.status === "failed" ? <ArrowDownRight className="h-4 w-4" /> : <ArrowUpRight className="h-4 w-4" />}
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium">{t.plan ? `${t.plan[0].toUpperCase()}${t.plan.slice(1)} plan` : "Subscription"}</p>
                <p className="text-[11.5px] text-white/45">{(t.paid_at ?? t.created_at) ? new Date((t.paid_at ?? t.created_at)!).toLocaleDateString(undefined, { day: "2-digit", month: "short", year: "numeric" }) : "—"} · {t.status}</p>
              </div>
              <div className="text-right tabular-nums">
                <p className={t.status === "failed" ? "text-white/40 line-through" : ""}>{money(t.amount_cents / 100, t.currency)}</p>
                {(t.refunded_cents ?? 0) > 0 && <p className="text-[11.5px] text-[#7dfab0]">−{money((t.refunded_cents ?? 0) / 100, t.currency)} refunded</p>}
              </div>
              {t.url && <a href={t.url} target="_blank" rel="noreferrer" className="text-[12px] text-white/60 underline-offset-2 hover:underline">Receipt</a>}
            </li>
          ))}
        </ul>
      )}

      {tab === "alerts" && (
        <ul className="mt-5 space-y-2">
          {alerts.length === 0 && <li className="py-8 text-center text-[13px] text-white/50">No alerts. Everything is in order.</li>}
          {alerts.map((a) => (
            <li key={a.text} className="flex items-start gap-3 rounded-2xl bg-white/[.05] p-3 text-[13px]">
              <Bell className={cn("mt-0.5 h-4 w-4 shrink-0", a.tone === "coral" ? "text-[#ff6b6b]" : a.tone === "amber" ? "text-[#fbbf24]" : "text-[#38bdf8]")} />{a.text}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
