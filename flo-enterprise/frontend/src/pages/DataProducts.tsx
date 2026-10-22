import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Badge, Card, ErrorState, PageHeader, Spinner, Tabs } from "@/components/ui";
import { api } from "@/lib/api";

type Tab = "products" | "metrics" | "integrations";
export default function DataProducts() {
  const [tab, setTab] = useState<Tab>("products");
  const p = useQuery({ queryKey: ["dp"], queryFn: () => api("/api/data/products") });
  const m = useQuery({ queryKey: ["metrics"], queryFn: () => api("/api/data/metrics") });
  const i = useQuery({ queryKey: ["integrations"], queryFn: () => api("/api/integrations") });
  return (
    <div className="space-y-4">
      <PageHeader title="Data Products & Semantic Layer" subtitle="Governed data products with owners, classification, lineage, quality checks, freshness SLAs and access policies. All synthetic." />
      <Tabs value={tab} onChange={setTab} tabs={[{ id: "products", label: "Data products" }, { id: "metrics", label: "Semantic metrics" }, { id: "integrations", label: "Enterprise adapters" }]} />
      {tab === "products" && (p.isLoading ? <Spinner /> : p.error ? <ErrorState error={p.error} /> : <div className="grid gap-4 xl:grid-cols-2">{p.data.data_products.map((d: any) => (
        <Card key={d.id} className="space-y-2 p-4"><div className="flex flex-wrap items-center gap-2"><h3 className="font-semibold">{d.name}</h3><Badge tone="blue">{d.classification}</Badge><Badge>v {d.version}</Badge><Badge tone="gold">synthetic</Badge></div>
          <div className="text-xs"><b>Owner</b> {d.owner} · <b>Freshness SLA</b> {d.freshness_sla}</div><div className="text-xs"><b>Access policy</b> {d.access_policy}</div>
          <div className="text-xs"><b>Lineage</b> {d.lineage.join(" → ")}</div><div className="text-xs"><b>Quality checks</b> {d.quality_checks.join(", ")}</div>
          <details className="text-xs"><summary className="cursor-pointer text-muted">Schema ({d.schema.length} entities)</summary>{d.schema.map((s: any) => <div key={s.entity} className="mt-1"><b>{s.entity}</b> ({s.rows ?? "?"} rows): {s.columns.map((c: any) => `${c.name}:${c.type}`).join(", ")}</div>)}</details>
        </Card>))}</div>)}
      {tab === "metrics" && (m.isLoading ? <Spinner /> : m.error ? <ErrorState error={m.error} /> : <Card className="p-4"><div className="mb-2 text-xs text-muted">Semantic layer v{m.data.version}</div>
        <table className="w-full text-xs"><thead><tr className="text-left text-muted"><th>ID</th><th>Name</th><th>Definition</th><th>Formula</th><th>Unit</th><th>Owner</th></tr></thead>
          <tbody>{m.data.metrics.map((x: any) => <tr key={x.id} className="border-t border-line/50 align-top"><td className="pr-2 text-gold">{x.id}</td><td className="pr-2">{x.name}</td><td className="pr-2">{x.definition}</td><td className="pr-2 font-mono">{x.formula}</td><td className="pr-2">{x.unit}</td><td>{x.owner}</td></tr>)}</tbody></table></Card>)}
      {tab === "integrations" && (i.isLoading ? <Spinner /> : i.error ? <ErrorState error={i.error} /> : <Card className="p-4"><p className="mb-2 text-sm text-warn">{i.data.statement}</p>
        <table className="w-full text-xs"><thead><tr className="text-left text-muted"><th>System</th><th>Category</th><th>Mode</th><th>Production</th><th>Classification</th><th>Freshness</th><th>Auth</th></tr></thead>
          <tbody>{i.data.adapters.map((a: any) => <tr key={a.system} className="border-t border-line/50"><td>{a.system}</td><td>{a.category}</td><td>{a.mode}</td><td>{String(a.connected_to_production)}</td><td>{a.data_classification}</td><td>{a.freshness}</td><td>{a.auth}</td></tr>)}</tbody></table></Card>)}
    </div>
  );
}
