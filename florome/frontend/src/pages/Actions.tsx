import { ArrowUpRight, Check, Play, ShieldAlert, X } from "lucide-react";
import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Chart, type ChartOption } from "../components/Chart";
import { Page, useRole } from "../components/Layout";
import { Badge, Button, Card, DemoLabel, Empty, ErrorBox, Loading, SectionTitle, cx } from "../components/ui";
import { api, nonce, post, type AuditItem, type Execution, type Incident, type Plan } from "../lib/api";
import { fmtDateTime, fmtTime } from "../lib/format";
import { useAsync } from "../lib/useAsync";

export default function Actions() {
  const role = useRole();
  const [params] = useSearchParams();
  const incidents = useAsync(() => api<{ items: Incident[] }>("/incidents"));
  const incidentId = params.get("incident") ?? incidents.data?.items[0]?.id;
  const plans = useAsync(() => (incidentId ? api<Plan[]>(`/remediations?incident_id=${incidentId}`) : Promise.resolve([])), [incidentId]);
  const execs = useAsync(() => api<Execution[]>("/executions?limit=500"));
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [comment, setComment] = useState("");
  const plan = plans.data?.[0];

  const act = async (label: string, fn: () => Promise<unknown>) => {
    setBusy(label);
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
      await Promise.all([plans.reload(), execs.reload()]);
    }
  };
  const decide = (decision: "approve" | "reject") =>
    act(decision, () => post("/approvals", { plan_id: plan!.id, decision, plan_hash: plan!.plan_hash, nonce: nonce(), comment }));

  return (
    <>
      <Page>
        <SectionTitle eyebrow="Action command center" title="Plan, approve, execute, verify"
          sub="Plans use only actions a connector publishes in its typed catalog. Approval binds to the plan's hash, the approver must differ from the creator, and nothing counts as done until validation reads the recovered state." />
        <div className="mb-4 flex flex-wrap items-center gap-3">
          <Button onClick={() => act("plan", () => post("/remediations", { incident_id: incidentId }))} disabled={!incidentId || !!busy}>
            {busy === "plan" ? "Planning…" : "Generate remediation plan"}
          </Button>
          <span className="text-xs text-ink-soft">Acting as <b>demo {role}</b>. Plans need an operator, approvals an approver, execution an operator.</span>
        </div>
        {error && <div className="mb-4"><ErrorBox error={error} /></div>}
        {plans.loading && <Loading />}
        {!plans.loading && !plan && <Empty>No plan yet. Run the RCA first, then generate a plan.</Empty>}
        {plan && (
          <div className="grid gap-5 lg:grid-cols-[1fr_380px]">
            <Card>
              <div className="flex flex-wrap items-center gap-3">
                <h3 className="font-semibold">Plan {plan.id}</h3>
                <Badge value={plan.status} />
                <Badge value={plan.risk === "low" ? "pass" : "warn"} label={`${plan.risk} risk`} />
                <span className="ml-auto font-mono text-[11px] text-ink-mute">sha256 {plan.plan_hash.slice(0, 16)}…</span>
              </div>
              <ol className="mt-4 space-y-3">
                {plan.steps.map((s) => (
                  <li key={s.index} className={cx("rounded-xl border p-4", s.status === "succeeded" ? "border-ok/30 bg-ok/5" : s.status === "failed" ? "border-bad/30 bg-bad/5" : "border-dome-100 bg-white")}>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-xs text-dome-600">{String(s.index + 1).padStart(2, "0")}</span>
                      <b className="text-sm">{s.title}</b>
                      <span className="text-sm text-ink-soft">on {s.target_name} ({s.environment})</span>
                      <span className="ml-auto flex gap-1">{s.simulated && <DemoLabel />}<Badge value={s.status ?? "pending"} /></span>
                    </div>
                    <dl className="mt-2 grid gap-x-6 gap-y-1 text-xs md:grid-cols-2">
                      <div><dt className="inline text-ink-mute">Operation: </dt><dd className="inline font-mono">{s.action_id}({JSON.stringify(s.params)})</dd></div>
                      <div><dt className="inline text-ink-mute">Expected: </dt><dd className="inline">{s.expected_outcome}</dd></div>
                      <div><dt className="inline text-ink-mute">Risk: </dt><dd className="inline">{s.risk}{s.reversible ? ", reversible" : ""}</dd></div>
                      <div><dt className="inline text-ink-mute">Rollback: </dt><dd className="inline">{s.rollback}</dd></div>
                      <div><dt className="inline text-ink-mute">Permission: </dt><dd className="inline font-mono">{s.required_permission}</dd></div>
                      <div><dt className="inline text-ink-mute">Why: </dt><dd className="inline">{s.rationale}</dd></div>
                    </dl>
                    {s.message && <p className="mt-2 text-xs"><b>Result:</b> {s.message}</p>}
                  </li>
                ))}
              </ol>
              {plan.policy_decision.notes.map((n) => <p key={n} className="mt-2 text-xs text-warn">{n}</p>)}
            </Card>
            <div className="space-y-5">
              <Card>
                <h3 className="font-semibold">Governance decision</h3>
                <ul className="mt-2 space-y-1 text-xs text-ink-soft">{plan.policy_decision.reasons.map((r) => <li key={r}>• {r}</li>)}</ul>
                {plan.status === "pending_approval" && (
                  <div className="mt-4 space-y-2">
                    <textarea aria-label="Approval comment" value={comment} onChange={(e) => setComment(e.target.value)} placeholder="Comment (recorded in the audit trail)"
                      className="h-16 w-full rounded-lg border border-dome-100 p-2 text-sm" />
                    <div className="flex gap-2">
                      <Button kind="accent" onClick={() => decide("approve")} disabled={!!busy}><Check className="h-4 w-4" />Approve</Button>
                      <Button kind="ghost" onClick={() => decide("reject")} disabled={!!busy}><X className="h-4 w-4" />Reject</Button>
                    </div>
                    <p className="text-[11px] text-ink-mute">You approve exactly this plan version (hash above). The creator ({plan.created_by}) cannot approve it.</p>
                  </div>
                )}
                {(plan.status === "approved" || plan.status === "failed") && (
                  <Button className="mt-4 w-full" onClick={() => act("exec", () => post("/executions", { plan_id: plan.id }))} disabled={!!busy}>
                    <Play className="h-4 w-4" />{busy === "exec" ? "Executing against sandbox…" : plan.status === "failed" ? `Resume from step ${plan.current_step + 1}` : "Execute approved plan"}
                  </Button>
                )}
                {plan.approvals.map((a) => (
                  <p key={a.id} className="mt-3 text-xs text-ink-soft"><Badge value={a.decision} /> by {a.approver_id} · {fmtDateTime(a.created_at)} · expires {fmtTime(a.expires_at)}</p>
                ))}
              </Card>
              <Card>
                <h3 className="font-semibold">Validation</h3>
                {!plan.validations.length && <p className="mt-2 text-sm text-ink-soft">Runs after the last step: reads every resource on the causal chain and the business process.</p>}
                {plan.validations.slice(-1).map((v) => (
                  <div key={v.id} className="mt-2">
                    <Badge value={v.passed ? "pass" : "fail"} label={v.passed ? "recovery verified" : "not recovered"} />
                    <ul className="mt-2 space-y-1 text-xs">
                      {v.checks.map((c, i) => (
                        <li key={i} className="flex items-center justify-between gap-2"><span>{c.resource} · <span className="font-mono">{c.check}</span></span>
                          <span className={c.passed ? "text-ok" : "text-bad"}>{String(c.observed ?? "")} {c.passed ? "✓" : "✗"}</span></li>
                      ))}
                    </ul>
                  </div>
                ))}
              </Card>
            </div>
          </div>
        )}
      </Page>
      <Ledger execs={execs.data ?? []} loading={execs.loading} />
    </>
  );
}

const RANGES = { "1H": 3600e3, "1D": 864e5, "1W": 6048e5, ALL: Infinity } as const;

export function Ledger({ execs, loading }: { execs: Execution[]; loading: boolean }) {
  const [tab, setTab] = useState<"overview" | "transactions" | "alerts">("overview");
  const [range, setRange] = useState<keyof typeof RANGES>("ALL");
  const alerts = useAsync(() => api<{ items: AuditItem[] }>("/governance/audit?limit=200"));
  const inRange = execs.filter((e) => Date.now() - new Date(e.started_at).getTime() <= RANGES[range]);
  const ok = inRange.filter((e) => e.status === "succeeded").length;
  const rate = inRange.length ? (ok / inRange.length) * 100 : 0;
  const option: ChartOption = useMemo(() => {
    const sorted = [...inRange].sort((a, b) => a.started_at.localeCompare(b.started_at));
    let n = 0;
    return {
      grid: { left: 0, right: 0, top: 10, bottom: 0 },
      xAxis: { type: "time", show: false }, yAxis: { type: "value", show: false },
      tooltip: { trigger: "axis" },
      series: [{ type: "line", smooth: true, showSymbol: false, lineStyle: { color: "#3DDC97", width: 2 },
        areaStyle: { color: { type: "linear", x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: "rgba(61,220,151,0.45)" }, { offset: 1, color: "rgba(61,220,151,0)" }] } },
        data: sorted.map((e) => [new Date(e.started_at).getTime(), (n += e.status === "succeeded" ? 1 : 0)]) }],
    };
  }, [inRange]);
  const denied = (alerts.data?.items ?? []).filter((a) => a.outcome === "denied" || a.outcome === "failed");

  return (
    <section className="bg-gradient-to-b from-[#0b0b0f] to-[#16161c] text-white">
      <div className="mx-auto max-w-[1400px] px-6 py-14">
        <div className="mx-auto max-w-3xl rounded-[28px] border border-white/10 bg-black/60 p-6 shadow-2xl">
          <div className="flex gap-2" role="tablist" aria-label="Ledger view">
            {(["overview", "transactions", "alerts"] as const).map((t) => (
              <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)}
                className={cx("rounded-full px-4 py-1.5 text-sm capitalize", tab === t ? "bg-white/15 text-white" : "text-white/50 hover:text-white")}>{t}</button>
            ))}
          </div>
          <div className="mt-6 flex items-center gap-2 text-sm text-white/60"><ArrowUpRight className="h-4 w-4 text-[#3DDC97]" /> Action ledger · demo tenant</div>
          <div className="mt-1 flex items-end gap-3">
            <span className="font-display text-6xl font-semibold tabular-nums">{ok}</span>
            <span className="mb-2 text-white/60">verified actions</span>
          </div>
          <div className="mt-2 flex items-center gap-3 text-sm">
            <span className="text-white/70">{inRange.length} attempted</span>
            <span className="rounded-md bg-[#3DDC97]/15 px-2 py-0.5 text-[#3DDC97]">{rate.toFixed(1)}% succeeded</span>
          </div>
          {loading && <Loading />}
          {tab === "overview" && (
            <>
              <div className="mt-4">{inRange.length ? <Chart option={option} height={180} label="Cumulative successful actions over time" /> : <p className="py-10 text-center text-sm text-white/40">No executions in this range.</p>}</div>
              <div className="mt-3 flex justify-between">
                {(Object.keys(RANGES) as (keyof typeof RANGES)[]).map((r) => (
                  <button key={r} onClick={() => setRange(r)} className={cx("rounded-lg px-3 py-1 text-xs", range === r ? "bg-white/15" : "text-white/50")}>{r}</button>
                ))}
              </div>
            </>
          )}
          {tab === "transactions" && (
            <ul className="mt-5 divide-y divide-white/10 text-sm">
              {inRange.map((e) => (
                <li key={e.id} className="flex items-center gap-3 py-2.5">
                  <span className={cx("h-2 w-2 rounded-full", e.status === "succeeded" ? "bg-[#3DDC97]" : "bg-bad")} />
                  <span className="font-mono text-xs text-white/50">{fmtTime(e.started_at)}</span>
                  <span className="flex-1">{e.action_id}<span className="text-white/40"> · {e.result?.message ?? e.error}</span></span>
                  <span className="text-xs text-white/50">{e.attempts}×</span>
                </li>
              ))}
              {!inRange.length && <li className="py-6 text-center text-white/40">No transactions yet.</li>}
            </ul>
          )}
          {tab === "alerts" && (
            <ul className="mt-5 divide-y divide-white/10 text-sm">
              {denied.map((a) => (
                <li key={a.id} className="flex items-start gap-3 py-2.5">
                  <ShieldAlert className="mt-0.5 h-4 w-4 text-bad" />
                  <span className="flex-1"><b>{a.action}</b> {a.outcome} <span className="text-white/50">· {String((a.detail as { reason?: string; error?: string }).reason ?? (a.detail as { error?: string }).error ?? "")}</span></span>
                  <span className="font-mono text-xs text-white/40">{fmtTime(a.at)}</span>
                </li>
              ))}
              {!denied.length && <li className="py-6 text-center text-white/40">No denied or failed operations.</li>}
            </ul>
          )}
        </div>
      </div>
    </section>
  );
}
