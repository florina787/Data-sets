"use client";

import { useState } from "react";
import { Badge, ErrorBox, Kpi, LoadingBlock, PageHead, Panel, StatusPill } from "@/components/ui";
import { useApi } from "@/hooks/useApi";
import { useAppState } from "@/hooks/useAppState";
import { statusTone } from "@/lib/format";

export default function InventoryPage() {
  const { userId } = useAppState();
  const { data, error, loading } = useApi<any>("/inventory", userId);
  const [type, setType] = useState("All");
  const types = data ? ["All", ...Object.keys(data.counts)] : ["All"];
  const items = (data?.items ?? []).filter((i: any) => type === "All" || i.type === type);
  return (
    <div className="page">
      <PageHead title="AI Inventory" description="Applications, agents, models, providers, prompts, RAG pipelines and workflows - with owners, versions, risk, approval, evaluation and deployment status." />
      <ErrorBox error={error} />
      {loading && !data ? <LoadingBlock /> : data && (<>
        <div className="grid grid-6" style={{ marginBottom: 12 }}>{Object.entries(data.counts).map(([k, v]) => <Kpi key={k} label={k} value={v as number} />)}</div>
        <Panel title="Register" actions={<select className="select" value={type} onChange={(e) => setType(e.target.value)} aria-label="Filter by type">{types.map((t) => <option key={t}>{t}</option>)}</select>} bodyClass="table-wrap">
          <table className="table"><thead><tr><th>Item</th><th>Type</th><th>Owner</th><th>Version</th><th>Risk</th><th>Approval</th><th>Last evaluation</th><th>Deployment</th></tr></thead>
            <tbody>{items.map((i: any) => <tr key={i.id}><td><div className="small strong">{i.name}</div><div className="tiny mono muted">{i.id}</div>
              {i.gates && <div className="row" style={{ marginTop: 2 }}>{i.gates.map((g: string) => <Badge key={g} tone="neutral">{g}</Badge>)}</div>}</td>
              <td className="small">{i.type}</td><td className="small">{i.owner}</td><td className="mono small">{i.version}{i.candidate_version ? ` → ${i.candidate_version}` : ""}</td>
              <td><Badge tone={statusTone(i.risk)}>{i.risk}</Badge></td><td><StatusPill status={i.approval_status === "APPROVED" ? "APPROVED" : "PENDING_REVIEW"} label={i.approval_status} /></td>
              <td className="small">{i.last_evaluation ? <StatusPill status={i.last_evaluation.gates_passed ? "PASS" : "FAIL"} /> : <span className="muted">—</span>}</td>
              <td className="small">{i.deployment_status}</td></tr>)}</tbody></table>
        </Panel>
      </>)}
    </div>
  );
}
