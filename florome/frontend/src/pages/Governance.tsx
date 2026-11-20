import { OctagonX, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { Chart, type ChartOption } from "../components/Chart";
import { Badge, Button, ErrorBox, Loading, cx } from "../components/ui";
import { api, post, type AuditItem } from "../lib/api";
import { fmtTime } from "../lib/format";
import { useAsync } from "../lib/useAsync";

interface Policy { policy: Record<string, unknown> & { execution_mode: string; autonomous_allowlist: { action_id: string; environments: string[] }[] }; emergency_stop: boolean }
interface Metrics { requests: number; server_errors: number; p50_ms: number | null; p95_ms: number | null; routes: { path: string; count: number; p50_ms: number; p95_ms: number }[]; note: string }

export default function Governance() {
  const policy = useAsync(() => api<Policy>("/governance/policy"));
  const chain = useAsync(() => api<{ valid: boolean; events_checked: number; broken_at: string | null }>("/governance/audit/verify"));
  const audit = useAsync(() => api<{ total: number; items: AuditItem[] }>("/governance/audit?limit=60"));
  const metrics = useAsync(() => api<Metrics>("/system/metrics"));
  const [error, setError] = useState<string | null>(null);

  const toggleStop = async () => {
    setError(null);
    try {
      await post("/governance/emergency-stop", { active: !policy.data?.emergency_stop, reason: "Toggled from governance console" });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
    void policy.reload();
    void audit.reload();
    void chain.reload();
  };
  const routeChart: ChartOption | null = metrics.data ? {
    grid: { left: 210, right: 20, top: 10, bottom: 24 },
    tooltip: { trigger: "axis" },
    legend: { textStyle: { color: "#ffffffaa" }, bottom: 0 },
    xAxis: { type: "value", name: "ms", axisLabel: { color: "#ffffff88" }, splitLine: { lineStyle: { color: "#ffffff14" } } },
    yAxis: { type: "category", data: metrics.data.routes.map((r) => r.path.replace("/api/v1", "")), axisLabel: { color: "#ffffffcc", fontSize: 10 } },
    series: [
      { name: "p50", type: "bar", data: metrics.data.routes.map((r) => r.p50_ms), itemStyle: { color: "#A3AAFB" } },
      { name: "p95", type: "bar", data: metrics.data.routes.map((r) => r.p95_ms), itemStyle: { color: "#5B63E6" } },
    ],
  } : null;

  return (
    <div className="bg-gradient-to-b from-[#0d1a3a] via-[#0a1024] to-[#3a6fd8] text-white">
      <div className="mx-auto max-w-[1400px] px-6 py-10">
        <div className="relative overflow-hidden rounded-[28px] border border-white/10 bg-[#0b0d16] px-6 py-10 md:px-10">
          <div className="grid-dark absolute inset-0" />
          <div className="relative">
            <p className="max-w-md text-sm text-white/60">Policy-as-code, separation of duties, approvals bound to plan hashes, and a hash-chained audit trail. Controls are designed to support future compliance assessment; no certification is claimed.</p>
            <h1 className="mt-6 font-display text-[clamp(3rem,10vw,8.5rem)] font-black uppercase leading-[0.85] tracking-tight text-white [text-shadow:0_8px_40px_rgba(91,99,230,0.5)]">
              Governance<br />Shield
            </h1>
            <div className="mt-8 grid gap-4 font-mono text-[12px] md:grid-cols-3">
              <div className="space-y-1 text-white/70">
                {chain.loading ? <Loading /> : chain.data && (
                  <>
                    <div><span className="text-dome-300">■</span> audit chain: {chain.data.events_checked} events</div>
                    <div>signature: {chain.data.valid ? <span className="text-emerald-300">verified ✓</span> : <span className="text-red-400">BROKEN at {chain.data.broken_at}</span>}</div>
                    <div>integrity: {chain.data.valid ? "PASSED" : "FAILED"}</div>
                  </>
                )}
              </div>
              <div className="space-y-1 text-white/70">
                <div>$ policy --mode <span className="text-white">{policy.data?.policy.execution_mode}</span></div>
                <div>&gt; separation_of_duties: enforced</div>
                <div>&gt; emergency_stop: <span className={policy.data?.emergency_stop ? "text-red-400" : "text-emerald-300"}>{policy.data?.emergency_stop ? "ACTIVE" : "off"}</span></div>
              </div>
              <div className="space-y-1 text-white/60">
                {(audit.data?.items ?? []).slice(0, 4).map((a) => (
                  <div key={a.id} className="truncate">{fmtTime(a.at)} <span className={a.outcome === "denied" || a.outcome === "failed" ? "text-red-400" : "text-emerald-300"}>{a.outcome.toUpperCase()}</span> {a.action}</div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {error && <div className="mt-4"><ErrorBox error={error} /></div>}
        <div className="mt-6 grid gap-5 lg:grid-cols-3">
          <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-5">
            <h3 className="font-semibold">Emergency stop</h3>
            <p className="mt-1 text-sm text-white/60">Blocks every execution for this tenant immediately, including approved plans. Admin only.</p>
            <Button kind={policy.data?.emergency_stop ? "accent" : "danger"} className="mt-4" onClick={toggleStop}>
              <OctagonX className="h-4 w-4" />{policy.data?.emergency_stop ? "Lift emergency stop" : "Activate emergency stop"}
            </Button>
          </div>
          <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-5 lg:col-span-2">
            <h3 className="font-semibold">Active policy</h3>
            {policy.data && (
              <div className="mt-3 grid gap-3 text-sm md:grid-cols-2">
                {Object.entries(policy.data.policy).filter(([k]) => k !== "autonomous_allowlist").map(([k, v]) => (
                  <div key={k} className="flex justify-between gap-2 border-b border-white/10 pb-1"><span className="text-white/60">{k}</span><span className="font-mono">{JSON.stringify(v)}</span></div>
                ))}
                <div className="md:col-span-2">
                  <div className="text-white/60">Autonomous allow-list (low-risk, reversible, tested only)</div>
                  <div className="mt-1 flex flex-wrap gap-2">{policy.data.policy.autonomous_allowlist.map((a) => <span key={a.action_id} className="rounded-md bg-white/10 px-2 py-1 font-mono text-xs">{a.action_id} @ {a.environments.join("/")}</span>)}</div>
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="mt-5 rounded-2xl border border-white/10 bg-white/[0.04] p-5">
          <div className="flex flex-wrap items-center gap-4">
            <h3 className="font-semibold">System metrics</h3>
            {metrics.data && (
              <div className="flex gap-6 font-mono text-sm">
                <span>{metrics.data.requests} req</span>
                <span>p50 {metrics.data.p50_ms ?? "–"} ms</span>
                <span>p95 {metrics.data.p95_ms ?? "–"} ms</span>
                <span className={metrics.data.server_errors ? "text-red-400" : "text-emerald-300"}>{metrics.data.server_errors} 5xx</span>
              </div>
            )}
            <Button kind="ghost" className="ml-auto !bg-white/10 !text-white" onClick={() => void metrics.reload()}>Refresh</Button>
          </div>
          {metrics.data && <p className="mt-1 text-xs text-white/50">{metrics.data.note}</p>}
          {routeChart && <Chart option={routeChart} height={Math.max(180, (metrics.data?.routes.length ?? 0) * 26 + 50)} label="Latency per API route" />}
        </div>

        <div className="mt-5 rounded-2xl border border-white/10 bg-black/30 p-5">
          <div className="flex items-center gap-2"><ShieldCheck className="h-4 w-4 text-emerald-300" /><h3 className="font-semibold">Audit trail</h3><span className="text-xs text-white/50">{audit.data?.total} events, newest first</span></div>
          <div className="mt-3 max-h-[420px] overflow-auto font-mono text-[11px]">
            {audit.data?.items.map((a) => (
              <div key={a.id} className="grid grid-cols-[70px_150px_160px_1fr_90px] gap-3 border-b border-white/5 py-1.5">
                <span className="text-white/40">{fmtTime(a.at)}</span>
                <span className="truncate text-white/70">{a.actor}</span>
                <span className="truncate">{a.action}</span>
                <span className="truncate text-white/50">{a.target}</span>
                <span className={cx("text-right", a.outcome === "denied" || a.outcome === "failed" ? "text-red-400" : "text-emerald-300")}>{a.outcome}</span>
              </div>
            ))}
          </div>
          {audit.data && <div className="mt-2"><Badge value={chain.data?.valid ? "pass" : "fail"} label={chain.data?.valid ? "hash chain verified" : "hash chain broken"} /></div>}
        </div>
      </div>
    </div>
  );
}
