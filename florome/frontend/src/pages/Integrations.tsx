import { Plug, RefreshCw, Wrench } from "lucide-react";
import { useMemo, useState } from "react";
import { CubeNetwork, type CubeNode } from "../components/Iso";
import { Page } from "../components/Layout";
import { DomeMark } from "../components/Logo";
import { Badge, Button, Card, ErrorBox, Eyebrow, Loading, SectionTitle, cx } from "../components/ui";
import { api, post, type McpTool, type Platform } from "../lib/api";
import { useAsync } from "../lib/useAsync";

const GROUP_STYLE: Record<string, { bg: string; fg: string; chip: string }> = {
  Microsoft: { bg: "bg-[#3A6FF0]", fg: "text-white", chip: "bg-white/20" },
  AWS: { bg: "bg-[#F29D38]", fg: "text-ink", chip: "bg-black/10" },
  Databricks: { bg: "bg-[#E8553E]", fg: "text-white", chip: "bg-white/20" },
  "Enterprise software": { bg: "bg-[#F5CF4B]", fg: "text-ink", chip: "bg-black/10" },
  "Agentic integration": { bg: "bg-[#7C84F2]", fg: "text-white", chip: "bg-white/20" },
  Test: { bg: "bg-[#1d1f33]", fg: "text-white", chip: "bg-white/15" },
};
const STATUS_LABEL: Record<string, string> = { simulated: "Simulated · verified", implemented: "Built · not verified live", not_implemented: "Planned" };

interface McpServers { allow_list: string[]; servers: { id: string; name: string; status: string; server_info: { name?: string; version?: string }; last_checked: string | null; last_error: string | null }[] }

export function cubeNodes(platforms: Platform[]): CubeNode[] {
  const groups = ["Microsoft", "AWS", "Databricks", "Enterprise software", "Agentic integration", "Test"];
  const nodes: CubeNode[] = [{ id: "core", label: "FLOROME", x: 0, y: 0, state: "core" }];
  groups.forEach((g, gi) => {
    const items = platforms.filter((p) => p.group === g);
    const verified = items.some((p) => p.connected_and_verified);
    const built = items.some((p) => p.status !== "not_implemented");
    const angle = (gi / groups.length) * Math.PI * 2 - Math.PI / 2;
    nodes.push({ id: g, label: `${g} (${items.filter((p) => p.status !== "not_implemented").length}/${items.length})`,
      x: Math.cos(angle) * 220, y: Math.sin(angle) * 130, state: verified ? "verified" : built ? "implemented" : "planned" });
  });
  return nodes;
}

export default function Integrations() {
  const platforms = useAsync(() => api<{ platforms: Platform[] }>("/platforms"));
  const list = platforms.data?.platforms ?? [];
  const groups = useMemo(() => [...new Set(list.map((p) => p.group))], [list]);
  const verified = list.filter((p) => p.connected_and_verified).length;
  const built = list.filter((p) => p.status !== "not_implemented").length;

  return (
    <>
      {/* Connect: dark with ember accents, your estate on one side, Florome on the other */}
      <section className="relative overflow-hidden bg-[#0a0807] text-white">
        <div className="grid-dark absolute inset-0 opacity-60" />
        <div className="relative mx-auto max-w-[1400px] px-6 py-16 text-center">
          <div className="flex items-center justify-center gap-6 md:gap-12">
            <div className="flex flex-col items-end gap-2 font-mono text-[11px] text-white/50">
              {["aws · lambda", "azure · app service", "databricks · jobs", "github · actions"].map((x) => <span key={x} className="rounded border border-white/10 px-2 py-0.5">{x}</span>)}
            </div>
            <svg width="220" height="60" viewBox="0 0 220 60" aria-hidden="true" className="hidden md:block">
              <path d="M0 30 C60 30 70 10 110 30 C150 50 160 30 220 30" fill="none" stroke="#F26B2E" strokeWidth="1.5" strokeDasharray="4 4">
                <animate attributeName="stroke-dashoffset" from="16" to="0" dur="1s" repeatCount="indefinite" />
              </path>
              <rect x="98" y="18" width="24" height="24" rx="6" fill="#F26B2E" opacity="0.9" />
            </svg>
            <DomeMark size={64} dark />
          </div>
          <h1 className="mt-8 font-display text-4xl font-medium tracking-tight md:text-5xl"><span className="text-ember">Connect once.</span> Govern everything.</h1>
          <p className="mx-auto mt-3 max-w-2xl text-sm text-white/60">
            Each connector declares exactly what it can read and do. A platform is shown as connected only after a live health check passes,
            never because a connector exists.
          </p>
          <div className="mt-6 flex justify-center gap-3 text-xs">
            <span className="rounded border border-ember/50 bg-ember/10 px-3 py-1.5 text-ember">{verified} verified connections</span>
            <span className="rounded border border-white/15 px-3 py-1.5">{built} connectors built</span>
            <span className="rounded border border-white/15 px-3 py-1.5 text-white/60">{list.length - built} planned</span>
          </div>
        </div>
      </section>

      {/* Power of integration: cube network on dark, Florome lit at the centre */}
      <section className="bg-black text-white">
        <div className="mx-auto grid max-w-[1400px] items-center gap-8 px-6 py-16 lg:grid-cols-[0.8fr_1.2fr]">
          <div>
            <Eyebrow dark>The power of integration</Eyebrow>
            <h2 className="mt-4 font-display text-4xl font-medium leading-tight tracking-tight">A single foundation<br />for every operation</h2>
            <p className="mt-4 text-sm text-white/60">REST, official SDKs and MCP servers all plug into one contract: discover, read, fetch evidence, list typed actions, execute under policy, verify.</p>
            <ul className="mt-6 space-y-2 font-mono text-xs text-white/70">
              <li className="flex items-center gap-2"><span className="h-3 w-3 border border-dome-200 bg-[#232858]" /> verified connection</li>
              <li className="flex items-center gap-2"><span className="h-3 w-3 border border-white/70 bg-[#111327]" /> connector built, awaiting credentials</li>
              <li className="flex items-center gap-2"><span className="h-3 w-3 border border-dashed border-white/30" /> planned</li>
            </ul>
          </div>
          <div className="h-[420px]">{platforms.data && <CubeNetwork nodes={cubeNodes(list)} />}</div>
        </div>
      </section>

      <Page>
        <SectionTitle eyebrow="Every platform" title="One copilot, many platforms" sub="Status reflects code and verification, not intent." />
        {platforms.error && <ErrorBox error={platforms.error} onRetry={platforms.reload} />}
        {platforms.loading && <Loading />}
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {groups.map((g) => {
            const st = GROUP_STYLE[g] ?? GROUP_STYLE.Test;
            return (
              <div key={g} className={cx("rounded-[22px] p-5 shadow-tile", st.bg, st.fg)} data-testid={`group-${g}`}>
                <div className="font-display text-xl font-bold uppercase tracking-tight">{g}</div>
                <ul className="mt-3 space-y-1.5">
                  {list.filter((p) => p.group === g).map((p) => (
                    <li key={p.platform} className={cx("flex items-center justify-between gap-2 rounded-xl px-3 py-1.5 text-sm", st.chip)} title={p.note}>
                      <span className="capitalize">{p.platform.replace(/_/g, " ")}</span>
                      <span className={cx("rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase", p.connected_and_verified ? "bg-ok text-white" : p.status === "implemented" ? "bg-white text-ink" : "bg-black/15")}>
                        {p.connected_and_verified ? "Connected" : STATUS_LABEL[p.status]}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            );
          })}
        </div>
        <McpPanel />
      </Page>
    </>
  );
}

function McpPanel() {
  const servers = useAsync(() => api<McpServers>("/mcp/servers"));
  const tools = useAsync(() => api<McpTool[]>("/mcp/tools"));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [active, setActive] = useState<McpTool | null>(null);
  const [args, setArgs] = useState<Record<string, string>>({});
  const [out, setOut] = useState<unknown>(null);

  const run = async (fn: () => Promise<unknown>, after?: (r: unknown) => void) => {
    setBusy(true);
    setError(null);
    try {
      const r = await fn();
      after?.(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
      void servers.reload();
      void tools.reload();
    }
  };
  const invoke = (t: McpTool) => {
    const typed = Object.fromEntries(Object.entries(args).filter(([, v]) => v !== "").map(([k, v]) => [k, t.input_schema.properties?.[k]?.type === "integer" ? Number(v) : v]));
    void run(() => post(`/mcp/tools/${t.id}/invoke`, { arguments: typed }), setOut);
  };

  return (
    <Card className="mt-8">
      <div className="flex flex-wrap items-center gap-3">
        <Wrench className="h-5 w-5 text-dome-500" />
        <h3 className="font-semibold">MCP gateway</h3>
        <span className="text-xs text-ink-soft">Allow-list: {servers.data?.allow_list.join(", ")}</span>
      </div>
      {error && <div className="mt-3"><ErrorBox error={error} /></div>}
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <div className="space-y-2">
          {servers.data?.servers.map((s) => (
            <div key={s.id} className="flex items-center gap-3 rounded-xl border border-dome-100 p-3">
              <Plug className="h-4 w-4 text-ink-mute" />
              <div className="flex-1"><div className="text-sm font-medium">{s.name}</div><div className="text-xs text-ink-mute">{s.server_info?.version ? `v${s.server_info.version}` : "not yet discovered"} {s.last_error}</div></div>
              <Badge value={s.status === "healthy" ? "healthy" : s.status === "unreachable" ? "failed" : "pending"} label={s.status} />
              <Button kind="ghost" disabled={busy} onClick={() => run(() => post(`/mcp/servers/${s.id}/discover`))}><RefreshCw className="h-3.5 w-3.5" />Discover</Button>
            </div>
          ))}
          <ul className="space-y-1.5">
            {tools.data?.map((t) => (
              <li key={t.id}>
                <button onClick={() => { setActive(t); setArgs({}); setOut(null); }} className={cx("w-full rounded-lg border p-2.5 text-left text-sm", active?.id === t.id ? "border-dome-500 bg-dome-50" : "border-dome-100")}>
                  <div className="flex items-center gap-2"><span className="font-mono">{t.name}</span><Badge value={t.access === "read" ? "pass" : "warn"} label={t.access} /><span className="ml-auto"><Badge value={t.enabled ? "verified" : "blocked"} label={t.enabled ? "enabled" : "disabled"} /></span></div>
                  <div className="mt-0.5 text-xs text-ink-soft">{t.description}</div>
                  {t.quarantine_reason && <div className="mt-0.5 text-xs text-warn">{t.quarantine_reason}</div>}
                </button>
              </li>
            ))}
          </ul>
        </div>
        <div className="rounded-xl bg-night p-4 text-white">
          {!active && <p className="text-sm text-white/60">Discover a server, then pick a read tool to invoke it through the gateway (schema-pinned, validated, sanitised, audited).</p>}
          {active && (
            <div className="space-y-3">
              <div className="font-mono text-sm">{active.name}</div>
              {Object.entries(active.input_schema.properties ?? {}).map(([k, v]) => (
                <label key={k} className="block text-xs text-white/70">{k} <span className="text-white/40">({v.type}{active.input_schema.required?.includes(k) ? ", required" : ""})</span>
                  <input value={args[k] ?? ""} onChange={(e) => setArgs({ ...args, [k]: e.target.value })} className="mt-1 w-full rounded-md bg-white/10 px-2 py-1.5 text-sm text-white" />
                </label>
              ))}
              <Button kind="accent" disabled={busy} onClick={() => invoke(active)}>Invoke</Button>
              {out !== null && <pre className="max-h-64 overflow-auto rounded-md bg-black/40 p-3 font-mono text-[11px] text-dome-100">{JSON.stringify(out, null, 2)}</pre>}
            </div>
          )}
        </div>
      </div>
    </Card>
  );
}
