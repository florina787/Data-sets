import { useMutation, useQueryClient } from "@tanstack/react-query";
import { RefreshCw, Settings } from "lucide-react";
import { DataTable } from "@/components/DataTable";
import { Card, ErrorBox, Kpi, Loading, PageHeader } from "@/components/ui";
import { post } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { useSession } from "@/lib/store";

type Integrations = { connectors: Record<string, unknown>[]; matrix: Record<string, unknown>[] };
type Status = { seed: string; demo_today: string; counts: Record<string, number>; egress_guard: { installed: boolean; blocked_attempts: number; loopback_connections: number }; offline_mode: boolean; kill_switch: string };
type Config = { version: string; demo_mode: boolean; offline_mode: boolean; llm_enabled: boolean; inference: string; seed: number; demo_today: string; brand_assets_authorized: boolean };

export function SettingsPage() {
  const qc = useQueryClient();
  const integ = useApi<Integrations>(["integrations"], "/api/integrations");
  const status = useApi<Status>(["demo-status"], "/api/demo/status");
  const cfg = useApi<Config>(["config-page"], "/api/config");
  const { theme, setTheme, resetRuns } = useSession();
  const reset = useMutation({ mutationFn: () => post("/api/demo/reset"), onSuccess: () => { resetRuns(); qc.invalidateQueries(); } });
  return (
    <div className="space-y-4">
      <PageHeader title="Integrations & Settings" subtitle="Every connector status below is real: simulated fixtures are labeled simulated; nothing claims a live connection it does not have." icon={<Settings className="h-5 w-5" />} />
      {cfg.data && status.data && (
        <div className="grid grid-cols-2 gap-2 md:grid-cols-6">
          <Kpi label="Version" value={cfg.data.version} />
          <Kpi label="Seed" value={status.data.seed} />
          <Kpi label="Data as of" value={status.data.demo_today} />
          <Kpi label="Inference" value={cfg.data.llm_enabled ? "local LLM + rules" : "rules engine"} />
          <Kpi label="Egress guard" value={status.data.egress_guard.installed ? "on" : "off"} tone={status.data.egress_guard.installed ? "teal" : "amber"} hint={`${status.data.egress_guard.blocked_attempts} blocked attempt(s)`} />
          <Kpi label="Paid API calls" value={0} tone="teal" hint="No hosted inference or paid APIs are used" />
        </div>
      )}
      <Card title="Connectors">
        {integ.isLoading ? <Loading /> : integ.error ? <ErrorBox error={integ.error} /> : <DataTable label="Connectors" columns={[{ key: "id", label: "ID" }, { key: "name", label: "Name" }, { key: "kind", label: "Kind" }, { key: "status", label: "Status" }, { key: "detail", label: "Detail" }]} rows={integ.data!.connectors} />}
      </Card>
      <Card title="Direct API vs MCP vs events vs batch vs RAG">
        {integ.data && <DataTable columns={[{ key: "approach", label: "Approach" }, { key: "use_cases", label: "Use cases" }, { key: "strengths", label: "Strengths" }, { key: "limitations", label: "Limitations" }, { key: "risks", label: "Risks" }, { key: "recommendation", label: "Recommendation" }]} rows={integ.data.matrix} />}
      </Card>
      <div className="grid gap-4 md:grid-cols-2">
        <Card title="Synthetic dataset">
          {status.data && <DataTable columns={[{ key: "table", label: "Table" }, { key: "rows", label: "Rows" }]} rows={Object.entries(status.data.counts).map(([table, rows]) => ({ table, rows }))} />}
        </Card>
        <Card title="Demo controls">
          <div className="space-y-3 text-sm">
            <label className="flex items-center gap-2"><input type="checkbox" checked={theme === "dark"} onChange={(e) => setTheme(e.target.checked ? "dark" : "light")} /> Dark mode</label>
            <button className="btn btn-danger" onClick={() => { if (confirm("Regenerate the synthetic database? All runs, approvals and audit events are reset.")) reset.mutate(); }} disabled={reset.isPending} data-testid="demo-reset">
              <RefreshCw className="h-4 w-4" /> {reset.isPending ? "Resetting..." : "Reset demo data (seed 20261024)"}
            </button>
            {reset.isSuccess && <div role="status" className="text-xs text-teal">Demo data regenerated.</div>}
            {reset.error ? <ErrorBox error={reset.error} /> : null}
            <p className="muted text-xs">Optional local LLM: set LLM_ENABLED=true and LLM_URL to a loopback Ollama/llama.cpp endpoint. It may only rephrase; policy decisions stay deterministic (POL-008).</p>
          </div>
        </Card>
      </div>
    </div>
  );
}
