import { useState } from "react";
import { Upload } from "lucide-react";
import { Plot } from "../components/Plot";
import { RunInline } from "../components/RunInline";
import { Badge, Button, Card, ChartCard, DataClassBadge, ErrorBox, Note, PageHeader, StatusBadge, Table } from "../components/ui";
import { api, useApi } from "../lib/api";
import { periodParams, useApp } from "../lib/store";
import { SERIES } from "../lib/format";

const SAMPLES: Record<string, { name: string; content: string; request: string }> = {
  pipeline: { name: "azure-pipelines.yml", request: "Repair the failing build pipeline and prepare a deployment", content: `trigger: [main]
pool:
  vmImage: ubuntu-latest
steps:
- task: UsePythonVersion@0
  inputs:
    versionSpec: '3.8'
- task: Cache@2
  inputs:
    key: 'python | "$(Agent.OS)"'
    path: $(PIP_CACHE_DIR)
- script: pip install -r requirements.txt && pytest
  continueOnError: true
` },
  aks: { name: "pricing-pod.log", request: "Diagnose the AKS incident in the pricing service", content: `Warning  BackOff  pod/pricing-7d9f  Back-off restarting failed container pricing
Last State: Terminated  Reason: OOMKilled  Exit Code: 137` },
  adf: { name: "adf-run.log", request: "Diagnose the Azure Data Factory copy failure", content: `Operation on target CopyTransactions failed: ErrorCode=UserErrorSchemaMapping, column 'txn_ref' not found in source` },
  functions: { name: "func.log", request: "Troubleshoot the Azure Functions timeout", content: `Microsoft.Azure.WebJobs.Host.FunctionTimeoutException: Timeout value of 00:05:00 exceeded by function 'ReconcileFx'` },
  infra: { name: "storage.bicep", request: "Review this infrastructure configuration", content: `resource sa 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: 'flodata'
  properties: {
    minimumTlsVersion: 'TLS1_0'
    allowBlobPublicAccess: true
    publicNetworkAccess: 'Enabled'
  }
}` },
  python: { name: "settlement.py", request: "Debug this Python settlement parser and generate tests", content: `import json
def parse(batch, seen=[]):
    try:
        rows = json.loads(batch)
    except:
        return None
    for r in rows:
        if r.get("amount") == None:
            raise ValueError(r)
        seen.append(r["id"])
    return total(rows)
` },
};

export function EngineeringPage({ kind }: { kind: "azure" | "python" }) {
  const s = useApp();
  const dept = kind === "azure" ? "azure_devops" : "python_engineering";
  const wf = useApi<any>("/engineering/workflows", { ...periodParams(s), department: dept, limit: 30 });
  const inc = useApi<any>(kind === "azure" ? "/engineering/incidents" : null);
  const [runId, setRunId] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const run = async (key: string, custom?: { name: string; content: string }) => {
    setErr(null);
    const smp = SAMPLES[key];
    try {
      const r = await api<any>("/harness/runs", { method: "POST", body: { request: smp.request, attachments: [custom ?? { name: smp.name, content: smp.content }] } });
      setRunId(r.run_id);
    } catch (e: any) { setErr(e.message); }
  };
  const rows = wf.data?.workflows ?? [];
  const keys = kind === "azure" ? ["pipeline", "aks", "adf", "functions", "infra"] : ["python"];
  return (
    <div>
      <PageHeader title={kind === "azure" ? "Azure DevOps" : "Python Engineering"}
        subtitle={kind === "azure" ? "Pipeline YAML, Data Factory, Functions, AKS, Monitor and App Insights diagnostics, PR drafts and human-approved deployments, each with its cost."
          : "Python debugging with patch diffs, automated test generation and verified fixes, each with its cost against a human baseline."} />
      <div className="grid gap-4 xl:grid-cols-[1fr_440px]">
        <ChartCard title="Workflow cost vs human baseline" subtitle="Each completed workflow: allocated compute and tooling, human review and rework, against the configured human baseline"
          badges={wf.data && <DataClassBadge dc={wf.data.data_class} />}>
          {rows.length > 0 && <Plot ariaLabel="Workflow cost vs baseline" height={360} data={[
            { type: "bar", name: "Compute + tooling", x: rows.map((r: any) => r.id), y: rows.map((r: any) => r.compute_tooling_cost), marker: { color: SERIES.revenue } },
            { type: "bar", name: "Human review + rework", x: rows.map((r: any) => r.id), y: rows.map((r: any) => r.total_cost - r.compute_tooling_cost), marker: { color: SERIES.ai } },
            { type: "scatter", mode: "markers", name: "Human baseline", x: rows.map((r: any) => r.id), y: rows.map((r: any) => r.human_baseline), marker: { color: SERIES.cost, size: 10, symbol: "line-ew-open", line: { width: 3 } } }]}
            layout={{ barmode: "stack", yaxis: { title: { text: s.currency } }, xaxis: { tickangle: -45 } }} />}
          <ul className="mt-2 max-h-72 space-y-1.5 overflow-y-auto text-sm scroll-thin">{rows.slice(0, 15).map((r: any) => (
            <li key={r.id} className="rounded-lg border border-line px-3 py-2"><div className="flex items-center justify-between gap-2"><strong className="text-flo-900">{r.id}</strong><span className="flex gap-1">{r.verified ? <Badge tone="green">verified</Badge> : <Badge tone="red">not verified</Badge>}<StatusBadge s={r.status === "succeeded" ? "completed" : "failed"} /></span></div>
              <p className="text-[13px] text-muted">{r.sentence}</p></li>))}</ul>
        </ChartCard>
        <div className="space-y-4">
          <Card className="p-4">
            <h2 className="mb-2 font-display text-lg font-semibold text-flo-900">Run Sherin on an artefact</h2>
            <div className="flex flex-wrap gap-1.5">{keys.map((k) => <Button key={k} variant="outline" onClick={() => run(k)}>{SAMPLES[k].request.split(" ").slice(0, 4).join(" ")}…</Button>)}</div>
            <label className="mt-3 flex cursor-pointer items-center gap-2 rounded-xl border border-dashed border-flo-200 p-3 text-sm text-muted hover:bg-flo-50"><Upload className="h-4 w-4" />Upload your own {kind === "azure" ? "YAML / log / Bicep" : ".py"} file
              <input type="file" className="hidden" data-testid="eng-upload" accept={kind === "azure" ? ".yml,.yaml,.log,.txt,.json,.bicep,.tf" : ".py"} onChange={async (e) => { const f = e.target.files?.[0]; if (f) run(keys[0], { name: f.name, content: await f.text() }); }} /></label>
            <ErrorBox error={err} />
            {runId && <RunInline runId={runId} />}
            <Note>Diagnostics run on the uploaded artefact with deterministic analysers. A live Azure DevOps / Azure subscription connection is not configured; opening PRs and deploying are simulated after human approval.</Note>
          </Card>
          {inc.data && <Card className="p-4"><h2 className="mb-2 font-display text-lg font-semibold text-flo-900">Incidents <Badge tone="amber">{inc.data.open} open</Badge></h2>
            <Table dense columns={[{ key: "id", label: "ID" }, { key: "service", label: "Service" }, { key: "severity", label: "Sev" }, { key: "status", label: "Status" }]} rows={inc.data.recent.slice(0, 10)} /></Card>}
        </div>
      </div>
    </div>
  );
}
export function Azure() { return <EngineeringPage kind="azure" />; }
export function Python() { return <EngineeringPage kind="python" />; }
