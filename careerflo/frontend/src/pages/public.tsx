import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Check, ShieldCheck } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { AgentCursor } from "@/components/art/AgentCursor";
import { BookStairs, LadderArt } from "@/components/art/Paths";
import { ActivityHeatmap, CareerProgression } from "@/components/career";
import { Logo } from "@/components/Logo";
import { Button, Card, ErrorNote, Input, Label } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useUsage } from "@/lib/hooks";
import { money } from "@/lib/utils";

function TopBar() {
  const { me } = useAuth();
  return (
    <header className="relative z-10 mx-auto flex max-w-6xl items-center justify-between px-5 py-5">
      <Link to="/"><Logo /></Link>
      <nav className="flex items-center gap-2 text-[13px]">
        <Link to="/pricing" className="hidden px-3 text-slate-600 sm:inline dark:text-slate-300">Pricing</Link>
        {me ? <Link to="/app"><Button size="sm">Open app</Button></Link> : <>
          <Link to="/login"><Button size="sm" variant="outline">Log in</Button></Link>
          <Link to="/register"><Button size="sm" variant="violet">Start free</Button></Link></>}
      </nav>
    </header>
  );
}

const demoDates = Array.from({ length: 40 }, (_, i) => new Date(Date.now() - ((i * 37) % 90) * 864e5).toISOString());

export function Landing() {
  return (
    <div className="bloom relative min-h-dvh overflow-hidden">
      <TopBar />
      <section className="relative z-10 mx-auto max-w-5xl px-5 pb-10 pt-14 text-center">
        <p className="eyebrow">Your Intelligent AI Career Partner</p>
        <h1 className="display mx-auto mt-3 max-w-3xl sm:text-[64px]">See every next step of your career, <em className="text-violet">clearly</em>.</h1>
        <p className="muted mx-auto mt-5 max-w-xl text-[15px]">Fifteen specialised agents find real jobs, match them to your verified resume, tailor documents without inventing facts and prepare you for interviews — on open-weight Qwen models.</p>
        <div className="mt-8 flex flex-wrap justify-center gap-2">
          <Link to="/register"><Button size="lg" variant="violet">Try every feature twice — free</Button></Link>
          <Link to="/pricing"><Button size="lg" variant="outline">See plans</Button></Link>
        </div>
        <p className="muted mt-3 text-xs">No credit card required. Free trials never turn into a charge.</p>
      </section>

      {/* Floating cards on an empty canvas, with agents working like collaborators */}
      <section className="relative z-10 mx-auto h-[360px] max-w-5xl px-5" aria-label="Product preview">
        <motion.div className="card absolute left-[4%] top-12 hidden p-5 sm:block" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
          <ActivityHeatmap dates={demoDates} weeks={10} />
          <AgentCursor label="Application Tracker" tone="amber" className="-left-6 -top-7" flip />
          <AgentCursor label="Analytics" tone="rose" className="right-6 bottom-6" delay={0.6} />
        </motion.div>
        <motion.div className="card absolute right-[6%] top-0 flex w-[min(360px,90%)] items-center gap-4 p-4" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.35 }}>
          <div className="grid h-20 w-24 shrink-0 place-items-center rounded-xl bg-gradient-to-br from-violet/15 to-sky/20"><BookStairs className="h-14" /></div>
          <div className="text-left">
            <p className="text-[15px] font-semibold">Tailored resume ready</p>
            <p className="muted text-[12.5px]">Fact-checked · PDF & DOCX</p>
          </div>
          <AgentCursor label="Resume Agent" tone="coral" className="left-16 -bottom-8" delay={0.3} />
          <AgentCursor label="Supervisor" tone="sky" className="-right-2 -top-8" flip delay={0.9} />
        </motion.div>
        <motion.div className="card absolute bottom-0 left-1/2 hidden w-72 -translate-x-1/2 p-5 text-left md:block" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.5 }}>
          <LadderArt className="mx-auto h-24" />
          <p className="mt-2 text-center text-[13px] font-medium">Next rung: Staff AI Engineer</p>
          <AgentCursor label="Job Matching" tone="violet" className="-right-10 top-4" delay={1.2} />
        </motion.div>
      </section>

      <section className="relative z-10 mx-auto max-w-5xl px-5 py-24 text-center">
        <p className="eyebrow">Career progression</p>
        <h2 className="mt-2 font-serif text-4xl">From where you are to where you're going</h2>
        <CareerProgression name="You" current={2} title="AI Engineer" />
        <p className="muted mx-auto mt-10 max-w-md text-[13px]">Jobs from licensed aggregators and employer boards</p>
        <div className="mt-4 flex flex-wrap items-center justify-center gap-x-10 gap-y-3 text-[15px] font-semibold text-slate-400">
          {["JSearch", "Adzuna", "Greenhouse", "Lever", "Ashby"].map((x) => <span key={x}>{x}</span>)}
        </div>
      </section>
      <footer className="relative z-10 mx-auto max-w-5xl px-5 pb-10 text-center text-xs text-slate-400">
        © Career_flo AI · Powered by open-weight Qwen models · <Link to="/pricing" className="underline">Pricing & terms</Link>
      </footer>
    </div>
  );
}

function AuthShell({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bloom relative min-h-dvh">
      <TopBar />
      <div className="relative z-10 mx-auto mt-10 max-w-sm px-5">
        <Card className="p-8">
          <h1 className="font-serif text-3xl">{title}</h1>
          {children}
        </Card>
      </div>
    </div>
  );
}

export function Login() {
  const { signIn, resetPassword } = useAuth();
  const nav = useNavigate();
  const [err, setErr] = useState<unknown>(null);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setBusy(true); setErr(null);
    try { await signIn(String(f.get("email")), String(f.get("password"))); nav("/app"); } catch (x) { setErr(x); } finally { setBusy(false); }
  }
  return (
    <AuthShell title="Welcome back">
      <form onSubmit={submit} className="mt-6 space-y-4">
        <div><Label>Email</Label><Input name="email" type="email" required autoComplete="email" /></div>
        <div><Label>Password</Label><Input name="password" type="password" required autoComplete="current-password" /></div>
        <ErrorNote error={err} />
        {note && <p className="text-sm text-emerald-700">{note}</p>}
        <Button className="w-full" loading={busy}>Log in</Button>
        <button type="button" className="muted w-full text-center text-xs underline" onClick={async () => {
          const email = (document.querySelector("input[name=email]") as HTMLInputElement)?.value;
          try { await resetPassword(email); setNote("If that account exists, a reset link is on its way."); } catch (x) { setErr(x); }
        }}>Forgot password?</button>
        <p className="muted text-center text-xs">New here? <Link className="text-violet" to="/register">Create an account</Link></p>
      </form>
    </AuthShell>
  );
}

export function Register() {
  const { signUp } = useAuth();
  const nav = useNavigate();
  const [err, setErr] = useState<unknown>(null);
  const [note, setNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setBusy(true); setErr(null);
    try {
      const msg = await signUp(String(f.get("email")), String(f.get("password")));
      if (msg) setNote(msg); else nav("/app");
    } catch (x) { setErr(x); } finally { setBusy(false); }
  }
  return (
    <AuthShell title="Start free">
      <p className="muted mt-2 text-sm">Two free uses of every premium feature. No card needed.</p>
      <form onSubmit={submit} className="mt-6 space-y-4">
        <div><Label>Email</Label><Input name="email" type="email" required autoComplete="email" /></div>
        <div><Label>Password (10+ characters, a letter and a number)</Label><Input name="password" type="password" minLength={10} required autoComplete="new-password" /></div>
        <ErrorNote error={err} />
        {note && <p className="text-sm text-emerald-700">{note}</p>}
        <Button className="w-full" variant="violet" loading={busy}>Create account</Button>
        <p className="muted text-center text-xs">Have an account? <Link className="text-violet" to="/login">Log in</Link></p>
      </form>
    </AuthShell>
  );
}

type PlanRow = { id: string; name: string; price_cents: number; currency: string; highlights: string[]; monthly_limits: Record<string, number> };

export function Pricing() {
  const { me } = useAuth();
  const plans = useQuery({ queryKey: ["plans"], queryFn: () => api<{ plans: PlanRow[]; features: Record<string, string> }>("/api/plans") });
  const usage = useUsage();
  const [err, setErr] = useState<unknown>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const current = me ? usage.data?.plan.id : undefined;
  async function choose(plan: string) {
    if (!me) { location.href = "/register"; return; }
    setBusy(plan); setErr(null);
    try {
      const r = current && current !== "free"
        ? await api("/api/billing/change-plan", { method: "POST", json: { plan } })
        : await api<{ url: string }>("/api/billing/checkout", { method: "POST", json: { plan } });
      if ((r as any).url) location.href = (r as any).url; else alert((r as any).note);
    } catch (x) { setErr(x); } finally { setBusy(null); }
  }
  return (
    <div className="bloom relative min-h-dvh">
      <TopBar />
      <div className="relative z-10 mx-auto max-w-5xl px-5 pb-20">
        <div className="mx-auto max-w-xl pt-8 text-center">
          <p className="eyebrow">Pricing</p>
          <h1 className="display mt-2">Simple monthly plans</h1>
          <p className="muted mt-3 text-[15px]">Every account can try every premium feature twice, free. Upgrade only if it helps.</p>
        </div>
        <div className="mt-12 grid gap-5 md:grid-cols-3">
          {plans.data?.plans.map((p) => (
            <Card key={p.id} className={p.id === "pro" ? "ring-2 ring-violet/40" : ""}>
              <p className="text-[13px] font-semibold">{p.name}</p>
              <p className="mt-3"><span className="font-serif text-5xl">{money(p.price_cents / 100, p.currency).replace(".00", "")}</span><span className="muted text-sm"> {p.currency} / month</span></p>
              <ul className="mt-5 space-y-2 text-[13px]">
                {p.highlights.map((h) => <li key={h} className="flex gap-2"><Check className="mt-0.5 h-4 w-4 shrink-0 text-emerald" />{h}</li>)}
              </ul>
              <div className="mt-6">
                {p.id === "free" ? <Button variant="outline" className="w-full" disabled>{current === "free" ? "Current plan" : "Included"}</Button>
                  : <Button className="w-full" variant={p.id === "pro" ? "violet" : "primary"} loading={busy === p.id} disabled={current === p.id} onClick={() => choose(p.id)}>
                    {current === p.id ? "Current plan" : current && current !== "free" ? `Switch to ${p.name}` : `Choose ${p.name}`}</Button>}
              </div>
            </Card>
          ))}
        </div>
        <ErrorNote error={err} />
        {plans.data && (
          <Card className="mt-10 overflow-x-auto p-0">
            <table className="w-full min-w-[560px] text-left text-[13px]">
              <thead><tr className="text-slate-500"><th className="p-4 font-medium">Monthly allowance</th><th className="p-4">Free (lifetime)</th><th className="p-4">Pro</th><th className="p-4">Premium</th></tr></thead>
              <tbody>
                {Object.entries(plans.data.features).map(([id, name]) => (
                  <tr key={id} className="border-t border-black/5 dark:border-white/10">
                    <td className="p-4">{name}</td><td className="p-4">2 uses</td>
                    {["pro", "premium"].map((pid) => { const v = plans.data!.plans.find((x) => x.id === pid)!.monthly_limits[id]; return <td key={pid} className="p-4 tabular-nums">{v ? v : "—"}</td>; })}
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        )}
        <div className="muted mx-auto mt-8 max-w-2xl space-y-1 text-center text-xs">
          <p className="flex items-center justify-center gap-1"><ShieldCheck className="h-3.5 w-3.5" />Payments are processed by Stripe. We never see or store your card number.</p>
          <p>Prices in CAD; applicable taxes are added at checkout. Plans renew monthly until cancelled; cancelling keeps access until the end of the paid period. Plan changes are prorated. Payments are non-refundable except where required by law or for billing errors. No plan includes unlimited AI usage.</p>
        </div>
      </div>
    </div>
  );
}

export function BillingResult({ ok }: { ok: boolean }) {
  const [params] = useSearchParams();
  const usage = useQuery({ queryKey: ["usage", "poll"], queryFn: () => api<any>("/api/usage"), refetchInterval: ok ? 2500 : false });
  const active = usage.data?.plan.id && usage.data.plan.id !== "free";
  return (
    <AuthShell title={ok ? (active ? "You're all set" : "Confirming payment…") : "Checkout cancelled"}>
      <p className="muted mt-3 text-sm">
        {ok ? (active ? `Your ${usage.data.plan.name} plan is active.` : "We unlock your plan only after Stripe confirms the payment to our server. This usually takes a few seconds.")
          : "No payment was taken. Your free trials are unchanged."}
      </p>
      {params.get("session_id") && <p className="muted mt-2 break-all text-[11px]">Reference: {params.get("session_id")}</p>}
      <Link to={ok ? "/app/billing" : "/pricing"}><Button className="mt-6 w-full">{ok ? "Go to billing" : "Back to plans"}</Button></Link>
    </AuthShell>
  );
}
