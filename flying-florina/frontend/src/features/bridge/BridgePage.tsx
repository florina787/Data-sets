import { useMutation } from "@tanstack/react-query";
import { Cable, Check, Download, Play } from "lucide-react";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { DataTable } from "@/components/DataTable";
import { Badge, Card, ErrorBox, Loading, PageHeader } from "@/components/ui";
import { BridgeTestRunner } from "@/components/Workspace";
import { download, get, post } from "@/lib/api";
import { useApi } from "@/lib/hooks";

type Sources = { sources: { id: string; name: string; kind: string; capabilities: string[]; write_operations_excluded: number }[]; capabilities: Record<string, { title: string; source: string; operation: string; mapping: Record<string, unknown>[]; scopes: string[] }> };
type Bundle = { bundle_id: string; files: Record<string, unknown>[]; static_checks: { check: string; passed: boolean }[]; preview: Record<string, string>; test_result?: unknown };
type Tools = { tools: Record<string, unknown>[]; rejected: Record<string, unknown>[] };
type Discover = { connected: boolean; error?: string; tools: Record<string, unknown>[]; calls: { tool: string; result: unknown }[] };

const STEPS = ["Choose source", "Discover metadata", "Select capability", "Map canonical schema", "Auth & policy scopes", "Generate adapter", "MCP tool wrapper", "Run tests", "Results", "Export"];

export function BridgePage() {
  const [params] = useSearchParams();
  const sources = useApi<Sources>(["bridge-sources"], "/api/bridge/sources");
  const tools = useApi<Tools>(["bridge-tools"], "/api/bridge/tools");
  const [step, setStep] = useState(0);
  const [source, setSource] = useState("mro_view");
  const [bundle, setBundle] = useState<Bundle | null>(null);
  const gen = useMutation({
    mutationFn: () => post<Bundle>("/api/bridge/generate", { capability: "part_availability", source_id: source, scopes: ["inventory.read"] }),
    onSuccess: (r) => { setBundle(r.data); setStep(6); },
  });
  const disc = useMutation({ mutationFn: () => get<Discover>("/api/bridge/mcp-discover") });
  const reg = useMutation({ mutationFn: (v: { name: string; version: string }) => post<{ registered: boolean; reason: string }>("/api/bridge/register-tool", v) });

  useEffect(() => {
    const id = params.get("bundle");
    if (id) get<Bundle>(`/api/bridge/${id}`).then((r) => { setBundle(r.data); setStep(6); }).catch(() => undefined);
  }, [params]);

  const cap = sources.data?.capabilities.part_availability;
  return (
    <div className="space-y-4">
      <PageHeader title="API & MCP Bridge Studio" subtitle="Generate a runnable, read-only typed adapter and MCP tool from legacy metadata. MCP is an agent interface - not a replacement for API governance." icon={<Cable className="h-5 w-5" />} />
      <Card title="Trust chain">
        <div className="flex flex-wrap items-center gap-1 text-xs">
          {["LLM / intent (rules)", "Workflow engine", "Tool registry (pinned)", "Policy gateway (deny-by-default)", "MCP server", "Typed API adapter", "Authorized system endpoint (synthetic)"].map((s, i, a) => (
            <span key={s} className="flex items-center gap-1"><span className="rounded-md border border-token bg-[var(--panel-2)] px-2 py-1">{s}</span>{i < a.length - 1 && "→"}</span>
          ))}
        </div>
      </Card>
      <div className="grid gap-4 lg:grid-cols-[220px_1fr]">
        <nav aria-label="Wizard steps" className="panel p-2">
          <ol className="space-y-0.5 text-sm">
            {STEPS.map((s, i) => (
              <li key={s}>
                <button className={`flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left ${step === i ? "bg-purple text-white" : ""}`} onClick={() => setStep(i)} disabled={i >= 6 && !bundle} aria-current={step === i ? "step" : undefined}>
                  <span className="w-5 text-xs">{i < step ? <Check className="h-3.5 w-3.5" /> : i + 1}</span>{s}
                </button>
              </li>
            ))}
          </ol>
        </nav>
        <Card title={`Step ${step + 1}: ${STEPS[step]}`}>
          {sources.isLoading && <Loading />}
          {sources.error ? <ErrorBox error={sources.error} /> : null}
          {sources.data && (
            <div className="space-y-3 text-sm" data-testid={`wizard-step-${step + 1}`}>
              {step === 0 && (
                <div className="space-y-2">
                  {sources.data.sources.map((s) => (
                    <label key={s.id} className="flex items-start gap-2 rounded-lg border border-token p-2">
                      <input type="radio" name="source" checked={source === s.id} onChange={() => setSource(s.id)} />
                      <span><b>{s.name}</b><br /><span className="muted text-xs">{s.kind} · write operations excluded: {s.write_operations_excluded}</span></span>
                    </label>
                  ))}
                </div>
              )}
              {step === 1 && <p>Discovered from <code>{cap?.source}</code>: view V_PART_AVAILABILITY joins MRO_PART_MASTER and MRO_STOCK_LOC. Write endpoints in the Java ERP API (createWorkOrder, closeWorkOrder, /admin/sql) are excluded from bridge candidates.</p>}
              {step === 2 && <p>Selected read-only capability: <b>{cap?.title}</b> · operation <code>{cap?.operation}</code>.</p>}
              {step === 3 && cap && <DataTable columns={[{ key: "legacy", label: "Legacy" }, { key: "canonical", label: "Canonical" }, { key: "type", label: "Type" }, { key: "note", label: "Note" }]} rows={cap.mapping} />}
              {step === 4 && <div className="space-y-1"><div>Required scope: <Badge tone="purple">inventory.read</Badge> (write scopes are rejected by the API).</div><div className="muted text-xs">Adapter validates audience <code>ff-parts-adapter</code>, expiry and scope on every request, never forwards the caller's token upstream, caps pagination at 50 and times out slow backends.</div></div>}
              {step === 5 && (
                <div className="space-y-2">
                  <button className="btn btn-primary" onClick={() => gen.mutate()} disabled={gen.isPending} data-testid="wizard-generate"><Play className="h-4 w-4" /> {gen.isPending ? "Generating..." : "Generate adapter bundle"}</button>
                  {gen.error ? <ErrorBox error={gen.error} /> : null}
                </div>
              )}
              {step === 6 && bundle && <pre className="max-h-96 overflow-auto rounded-lg bg-navy p-3 text-[11px] text-offwhite">{bundle.preview["mcp_server/server.py"] ?? ""}</pre>}
              {step === 7 && bundle && <BridgeTestRunner bundleId={bundle.bundle_id} />}
              {step === 8 && bundle && (
                <div className="space-y-2">
                  <DataTable columns={[{ key: "check", label: "Static check" }, { key: "passed", label: "Passed" }]} rows={bundle.static_checks} />
                  <DataTable columns={[{ key: "path", label: "File" }, { key: "bytes", label: "Bytes" }, { key: "sha256", label: "SHA-256" }]} rows={bundle.files} maxHeight={260} />
                </div>
              )}
              {step === 9 && bundle && (
                <div className="space-y-2">
                  <button className="btn btn-primary" onClick={() => download(`/api/bridge/${bundle.bundle_id}/download`, `${bundle.bundle_id}.zip`)}><Download className="h-4 w-4" /> Download code bundle (.zip)</button>
                  <p className="muted text-xs">Includes README with run instructions and example curl commands, .env.example, OpenAPI, threat model, tests and the MCP server.</p>
                </div>
              )}
              {bundle && <div className="muted text-xs">Current bundle: {bundle.bundle_id}</div>}
              <div className="flex gap-2 pt-2">
                <button className="btn btn-ghost" disabled={step === 0} onClick={() => setStep(step - 1)}>Back</button>
                <button className="btn btn-ghost" disabled={step === 9 || (step >= 5 && !bundle)} onClick={() => setStep(step + 1)} data-testid="wizard-next">Next</button>
              </div>
            </div>
          )}
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Pinned tool registry (POL-006)" subtitle="Tools register only if name, version and schema SHA-256 match the allowlist.">
          {tools.data && <DataTable columns={[{ key: "name", label: "Tool" }, { key: "version", label: "Version" }, { key: "action", label: "Action" }, { key: "label", label: "Label" }, { key: "pin_ok", label: "Pinned" }, { key: "invocations", label: "Invocations" }]} rows={tools.data.tools} />}
          <div className="mt-3 flex flex-wrap gap-2">
            <button className="btn btn-ghost" onClick={() => reg.mutate({ name: "shadow.exfiltrate", version: "1.0.0" })} data-testid="register-untrusted">Try registering untrusted tool</button>
            <button className="btn btn-ghost" onClick={() => reg.mutate({ name: "parts.check_availability", version: "9.9.9" })}>Try version drift</button>
          </div>
          {reg.data && <div role="status" className={`mt-2 rounded-lg border p-2 text-xs ${reg.data.data.registered ? "border-blocked/40" : "border-teal/40 bg-teal/10"}`}>{reg.data.data.registered ? "Registered (unexpected)" : `Rejected: ${reg.data.data.reason}`}</div>}
          {reg.error ? <ErrorBox error={reg.error} /> : null}
        </Card>
        <Card title="Demo MCP server (stdio)" subtitle="Connects to mcp_servers/demo_maintenance, checks schema pins, calls only trusted tools; the server authorizes every call.">
          <button className="btn btn-primary" onClick={() => disc.mutate()} disabled={disc.isPending} data-testid="mcp-discover"><Play className="h-4 w-4" /> {disc.isPending ? "Connecting..." : "Discover & call tools"}</button>
          {disc.error ? <ErrorBox error={disc.error} /> : null}
          {disc.data && (
            <div className="mt-3 space-y-2" data-testid="mcp-result">
              <Badge tone={disc.data.data.connected ? "teal" : "red"}>{disc.data.data.connected ? "connected" : `failed: ${disc.data.data.error}`}</Badge>
              <DataTable columns={[{ key: "name", label: "Tool" }, { key: "status", label: "Status" }, { key: "pin_ok", label: "Pin OK" }, { key: "schema_sha256", label: "Schema SHA-256" }]} rows={disc.data.data.tools} />
              <pre className="max-h-48 overflow-auto rounded-lg bg-navy p-2 text-[10px] text-offwhite">{JSON.stringify(disc.data.data.calls, null, 1).slice(0, 4000)}</pre>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
