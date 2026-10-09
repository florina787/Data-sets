"use client";

import { ErrorBox, Kpi, LoadingBlock, PageHead, Panel, StatusPill } from "@/components/ui";
import { useApi } from "@/hooks/useApi";

export default function UseCasesPage() {
  const { data, error, loading } = useApi<any>("/use-cases", null);
  const groups: Record<string, any[]> = {};
  (data?.use_cases ?? []).forEach((u: any) => { (groups[u.category] ??= []).push(u); });
  return (
    <div className="page">
      <PageHead title="Use Case Catalog" description="45 legal-AI use cases with honest implementation status. PARTIAL means a real but limited implementation; nothing unimplemented is marked IMPLEMENTED." />
      <ErrorBox error={error} />
      {loading && !data ? <LoadingBlock /> : data && (<>
        <div className="grid grid-3" style={{ marginBottom: 12 }}>
          <Kpi label="Implemented" value={data.counts.IMPLEMENTED} tone="good" />
          <Kpi label="Partial" value={data.counts.PARTIAL} tone="warn" />
          <Kpi label="Planned" value={data.counts.PLANNED} />
        </div>
        <div className="stack">{Object.entries(groups).map(([cat, items]) => (
          <Panel key={cat} title={cat} bodyClass="table-wrap">
            <table className="table"><tbody>{items.map((u) => <tr key={u.id}><td className="mono small" style={{ width: 60 }}>{u.id}</td>
              <td className="small strong" style={{ width: 240 }}>{u.name}</td><td style={{ width: 120 }}><StatusPill status={u.status} /></td>
              <td className="small">{u.evidence}<div className="tiny mono muted">{u.module}</div></td></tr>)}</tbody></table>
          </Panel>))}</div>
      </>)}
    </div>
  );
}
