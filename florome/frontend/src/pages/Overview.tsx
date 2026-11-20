import { ArrowUpRight, PlayCircle } from "lucide-react";
import { Link } from "react-router-dom";
import { DomeStack, type Satellite } from "../components/Iso";
import { Page } from "../components/Layout";
import { DomeMark } from "../components/Logo";
import { Badge, Card, DemoLabel, ErrorBox, Eyebrow, Loading, Stat, cx } from "../components/ui";
import { api, type Summary, type Topology } from "../lib/api";
import { money } from "../lib/format";
import { useAsync } from "../lib/useAsync";

const GROUPS: { label: string; platform: string; glyph: string; x: number; y: number }[] = [
  { label: "AWS", platform: "aws", glyph: "☁", x: -190, y: -20 },
  { label: "Azure", platform: "azure", glyph: "◆", x: -20, y: -190 },
  { label: "Databricks", platform: "databricks", glyph: "◈", x: 150, y: -110 },
  { label: "GitHub", platform: "github", glyph: "⑂", x: 160, y: 60 },
  { label: "MCP", platform: "mcp", glyph: "⚙", x: -110, y: 150 },
  { label: "Business", platform: "business", glyph: "▣", x: 60, y: 170 },
];

const LOOP = ["Detect", "Investigate", "Verify", "Plan", "Approve", "Execute", "Validate", "Learn"];

export default function Overview() {
  const summary = useAsync(() => api<Summary>("/analytics/summary"));
  const topo = useAsync(() => api<Topology>("/topology"));
  const advisor = useAsync(async () => {
    try {
      return (await api<unknown[]>("/architecture/scenarios")).length;
    } catch {
      return -1;
    }
  });

  const platformsWithResources = new Set((topo.data?.nodes ?? []).map((n) => n.platform));
  const sats: Satellite[] = GROUPS.map((g) => ({ ...g, active: platformsWithResources.has(g.platform) }));
  const s = summary.data;

  return (
    <>
      {/* Hero: light, isometric (overall design system) */}
      <section className="grid-canvas relative overflow-hidden border-b border-dome-100">
        <div className="mx-auto grid max-w-[1400px] items-center gap-6 px-6 pb-6 pt-14 lg:grid-cols-[1fr_1.15fr]">
          <div>
            <Eyebrow>All your clouds. One intelligent dome.</Eyebrow>
            <h1 className="mt-5 font-display text-5xl font-semibold leading-[1.05] tracking-tight text-ink md:text-6xl">
              The intelligence dome<br />over <span className="text-dome-500">your enterprise</span>
            </h1>
            <p className="mt-5 max-w-xl text-[15px] leading-relaxed text-ink-soft">
              Florome covers every cloud, pipeline and copilot you run. It finds the root cause with evidence, proposes the fix,
              executes only what policy and a human allow, and checks that the business actually recovered.
            </p>
            <div className="mt-7 flex flex-wrap gap-3">
              <Link to="/rca" className="inline-flex items-center gap-2 rounded-lg bg-ink px-5 py-2.5 text-sm font-medium text-white hover:bg-ink/85">
                Investigate the open incident <ArrowUpRight className="h-4 w-4" />
              </Link>
              <a href="#loop" className="inline-flex items-center gap-2 rounded-lg border border-dome-100 bg-white px-5 py-2.5 text-sm font-medium text-ink hover:bg-dome-50">
                See how it works <PlayCircle className="h-4 w-4 text-ink-mute" />
              </a>
            </div>
          </div>
          <div className="h-[380px] md:h-[440px]">
            {topo.loading ? <Loading label="Mapping your estate" /> : <DomeStack satellites={sats} />}
          </div>
        </div>
      </section>

      <Page>
        {summary.error && <ErrorBox error={summary.error} onRetry={summary.reload} />}
        {summary.loading && <Loading />}
        {s && (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
            <Card><Stat label="Verified connections" value={`${s.connections.verified}/${s.connections.total}`} sub={s.connections.platforms_verified.join(", ") || "none"} /></Card>
            <Card><Stat label="Open incidents" value={s.incidents.open} sub={`${s.incidents.resolved} resolved`} /></Card>
            <Card>
              <Stat label="Root causes" value={Object.values(s.rca.by_conclusion).reduce((a, b) => a + b, 0)}
                sub={<span className="flex flex-wrap gap-1">{Object.entries(s.rca.by_conclusion).map(([k, v]) => <Badge key={k} value={k} label={`${v} ${k}`} />)}{!Object.keys(s.rca.by_conclusion).length && "no RCA run yet"}</span>} />
            </Card>
            <Card><Stat label="Pending approvals" value={s.remediation.pending_approval} sub={`${s.executions.succeeded} actions succeeded · ${s.executions.failed} failed`} /></Card>
            <Card>
              <Stat label={`Cloud + AI spend ${s.cost.period ?? ""}`} value={money(s.cost.amount)}
                sub={<>{s.cost.previous ? `${(((s.cost.amount - s.cost.previous) / s.cost.previous) * 100).toFixed(1)}% vs prior month ` : ""}{s.cost.is_demo && <DemoLabel />}</>} />
            </Card>
          </div>
        )}
        {s?.emergency_stop && <div className="mt-4"><ErrorBox error="Emergency stop is active: no action can execute until an admin lifts it (Governance)." /></div>}
      </Page>

      {/* Copilot layer: dark section with a glowing horizon */}
      <section className="relative overflow-hidden bg-night text-white">
        <div className="pointer-events-none absolute inset-x-0 bottom-[-60%] mx-auto h-[120%] w-[140%] -translate-x-[14%] rounded-[50%] border-t border-dome-300/60 bg-[radial-gradient(ellipse_at_top,rgba(91,99,230,0.45),transparent_60%)] shadow-[0_-30px_120px_-20px_rgba(124,132,242,0.6)]" />
        <div className="relative mx-auto max-w-[1400px] px-6 py-20">
          <div className="mx-auto max-w-3xl text-center">
            <Eyebrow dark>Runs as a layer, not a replacement</Eyebrow>
            <h2 className="mt-5 font-display text-4xl font-semibold tracking-tight md:text-5xl">
              One dome over <em className="font-serif font-normal italic text-dome-200">every copilot you already run</em>
            </h2>
            <p className="mt-4 text-sm text-white/60">
              Florome sits above your existing copilots and platforms. They keep doing their jobs; Florome correlates what they see,
              explains it with evidence, and governs what happens next.
            </p>
          </div>
          <div className="mx-auto mt-12 max-w-4xl space-y-3">
            <Layer top title="Florome" sub="RCA · governed actions · MCP gateway · audit" status="live" />
            <div className="grid gap-3 md:grid-cols-2">
              <Layer title="ArchAI Architecture Advisor" sub="AI investment & architecture assessments (Project B)"
                status={advisor.loading ? "checking" : advisor.data && advisor.data > 0 ? "live" : "unavailable"}
                detail={advisor.data && advisor.data > 0 ? `${advisor.data} scenarios served via adapter` : "Install Project B requirements to enable"} />
              <Layer title="Conversation Intelligence Copilot" sub="Customer-conversation analytics (Project A)" status="imported"
                detail="Code imported unchanged; not yet wired into Florome's API" />
            </div>
            <Layer title="Your platforms" sub="AWS · Azure · Databricks · GitHub · MCP servers · business processes" status="mixed"
              detail="See Integrations for the verified status of each connector" />
          </div>
        </div>
      </section>

      <Page>
        <div id="loop" className="scroll-mt-24">
          <Eyebrow>From root cause to resolution</Eyebrow>
          <h2 className="mt-3 font-display text-3xl font-semibold tracking-tight">Eight steps, every one auditable</h2>
          <ol className="mt-6 grid gap-3 sm:grid-cols-4 lg:grid-cols-8">
            {LOOP.map((step, i) => (
              <li key={step} className="rounded-xl border border-dome-100 bg-white p-3 shadow-tile">
                <div className="font-mono text-[11px] text-dome-500">{String(i + 1).padStart(2, "0")}</div>
                <div className="mt-1 text-sm font-medium">{step}</div>
              </li>
            ))}
          </ol>
        </div>
      </Page>
    </>
  );
}

function Layer({ title, sub, status, detail, top }: { title: string; sub: string; status: string; detail?: string; top?: boolean }) {
  const tone: Record<string, string> = { live: "text-emerald-300", imported: "text-amber-300", unavailable: "text-white/40", checking: "text-white/40", mixed: "text-dome-200" };
  return (
    <div className={cx("flex items-center gap-4 rounded-2xl border px-5 py-4 backdrop-blur",
      top ? "border-dome-300/50 bg-dome-500/15 shadow-[0_0_60px_-10px_rgba(124,132,242,0.6)]" : "border-white/10 bg-white/[0.04]")}>
      {top ? <DomeMark size={36} dark /> : <span className="h-2 w-2 rounded-full bg-white/30" />}
      <div className="flex-1">
        <div className="font-medium">{title}</div>
        <div className="text-xs text-white/55">{sub}</div>
      </div>
      <div className="text-right">
        <div className={cx("font-mono text-[11px] uppercase tracking-wider", tone[status] ?? "text-white/60")}>{status}</div>
        {detail && <div className="text-[11px] text-white/40">{detail}</div>}
      </div>
    </div>
  );
}
