import { useQuery } from "@tanstack/react-query";
import { Activity } from "lucide-react";
import type { ReactNode } from "react";
import { PageHeader } from "@/components/career";
import { Card, ErrorNote, Pill } from "@/components/ui";
import { api } from "@/lib/api";

function Stat({ k, v, sub }: { k: string; v: any; sub?: string }) {
  return (
    <Card className="p-4">
      <p className="muted text-[11.5px]">{k}</p>
      <p className="font-serif text-3xl leading-tight">{v ?? "—"}</p>
      {sub && <p className="muted text-[11px]">{sub}</p>}
    </Card>
  );
}

function Section({ title, tone, note, children }: { title: string; tone: "emerald" | "amber" | "violet"; note: string; children: ReactNode }) {
  const label = tone === "emerald" ? "measured" : tone === "amber" ? "estimate" : "real records only";
  return (
    <section className="mt-8">
      <div className="mb-3 flex flex-wrap items-center gap-2"><h2 className="text-[15px] font-semibold">{title}</h2><Pill tone={tone}>{label}</Pill></div>
      <p className="muted mb-3 text-[12px]">{note}</p>
      {children}
    </section>
  );
}

const pct = (x: number | null | undefined) => (x == null ? "—" : `${Math.round(x * 1000) / 10}%`);

export function Ops() {
  const q = useQuery({ queryKey: ["ops"], queryFn: () => api<any>("/api/admin/ops"), refetchInterval: 15000 });
  const ready = useQuery({ queryKey: ["ready"], queryFn: () => api<any>("/api/health/ready").catch((e) => e.detail ?? { status: "down" }), refetchInterval: 15000 });
  const d = q.data;
  const m = d?.measured;
  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader eyebrow="Operations" title="Is everything healthy?" sub="Administrator view. Measured values, estimates and revenue are kept apart." />
      <ErrorNote error={q.error} />
      {ready.data && (
        <Card className="flex flex-wrap items-center gap-3 p-4">
          <Activity className="h-4 w-4" />
          <span className="text-[13px] font-semibold">Readiness: {ready.data.status}</span>
          {Object.entries(ready.data.checks ?? {}).map(([k, v]: any) => (
            <Pill key={k} tone={v.ok === false || v.configured === false ? "coral" : "emerald"}>{k}{v.mode ? ` · ${v.mode}` : ""}{v.provider ? ` · ${v.provider}` : ""}</Pill>
          ))}
        </Card>
      )}
      {m && (
        <>
          <Section title="Traffic & reliability" tone="emerald" note={m.note}>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              <Stat k="Active users (15 min)" v={m.api.active_users_15m} sub={`${m.api.active_users_24h} in 24 h`} />
              <Stat k="API success rate" v={pct(m.api.success_rate)} sub={`${m.api.requests} requests`} />
              <Stat k="Latency p50 / p95" v={`${m.api.latency_ms.p50 ?? "—"} / ${m.api.latency_ms.p95 ?? "—"}`} sub="ms" />
              <Stat k="Open conversations" v={m.open_conversations} />
            </div>
          </Section>
          <Section title="Qwen inference & agents" tone="emerald" note={`${m.inference.provider} · ${m.inference.model} · last 30 days, demo accounts excluded`}>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              <Stat k="Time to first token" v={m.inference.avg_ttft_ms} sub="ms (avg)" />
              <Stat k="Tokens / second" v={m.inference.avg_tokens_per_second} />
              <Stat k="Queue / concurrency" v={`${m.inference.queue_depth_now} / ${m.inference.max_concurrency}`} />
              <Stat k="Inference errors" v={m.inference.errors} sub={`of ${m.inference.requests}`} />
              <Stat k="Agent success" v={pct(m.agents.success_rate)} sub={`${m.agents.runs} runs`} />
              <Stat k="MCP calls" v={m.mcp.calls} sub={`${m.mcp.failures} failed · ${m.mcp.denied} denied`} />
              <Stat k="CPU / RAM" v={`${m.resources.cpu_percent}% / ${m.resources.memory_percent}%`} sub={`${m.resources.memory_used_gb} of ${m.resources.memory_total_gb} GB`} />
              <Stat k="Disk" v={`${m.resources.disk_percent}%`} />
            </div>
            <Card className="mt-3 p-4 text-[12.5px]">
              <p className="font-semibold">Feature usage (30 days)</p>
              <div className="mt-2 flex flex-wrap gap-1.5">{Object.entries(m.feature_usage_30d).map(([f, n]: any) => <Pill key={f}>{f} · {n}</Pill>)}</div>
              <p className="muted mt-2">Source of uses: {Object.entries(m.trial_vs_plan_30d).map(([k, v]) => `${k} ${v}`).join(" · ") || "none yet"}</p>
            </Card>
          </Section>
          <Section title="Cost" tone="amber" note={d.estimated.note}>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              <Stat k="Active users (30 d)" v={d.estimated.active_users_30d} />
              <Stat k="Variable cost (30 d)" v={`CA$${d.estimated.variable_cost_cad_30d}`} />
              <Stat k="Fixed infrastructure" v={`US$${d.estimated.fixed_infra_usd_month}`} sub="per month (configured)" />
              <Stat k="Cost per active user" v={d.estimated.cost_per_active_user_usd == null ? "—" : `US$${d.estimated.cost_per_active_user_usd}`} />
            </div>
          </Section>
          <Section title="Revenue" tone="violet" note={d.revenue.note}>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
              <Stat k="MRR" v={d.revenue.mrr_cents == null ? "No revenue yet" : `CA$${(d.revenue.mrr_cents / 100).toFixed(2)}`} />
              <Stat k="Gross margin" v={d.revenue.estimated_gross_margin == null ? "—" : pct(d.revenue.estimated_gross_margin)} />
              <Stat k="Live-mode records" v={d.revenue.livemode_records ? "yes" : "no (test mode)"} />
            </div>
          </Section>
        </>
      )}
    </div>
  );
}
