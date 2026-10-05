"use client";

import { useRouter } from "next/navigation";
import { Badge, ErrorBox, LoadingBlock, PageHead, Panel, StatusPill } from "@/components/ui";
import { useApi } from "@/hooks/useApi";
import { useAppState } from "@/hooks/useAppState";
import { statusTone } from "@/lib/format";
import type { MatterSummary } from "@/types/api";

export default function MattersPage() {
  const { userId, setMatterId } = useAppState();
  const { data, error, loading, reload } = useApi<MatterSummary[]>("/matters", userId);
  const router = useRouter();
  return (
    <div className="page">
      <PageHead title="Matters" description="Matters visible to the signed-in user. Matters you cannot access are redacted - client and description are withheld." />
      <ErrorBox error={error} onRetry={reload} />
      <Panel title="Matter register" bodyClass="table-wrap">
        {loading && !data ? <LoadingBlock /> : (
          <table className="table">
            <thead><tr><th>Matter</th><th>Number</th><th>Client</th><th>Practice</th><th>AI status</th><th>Risk</th><th>Access</th><th /></tr></thead>
            <tbody>{(data ?? []).map((m) => (
              <tr key={m.matter_id}>
                <td className="strong">{m.access.permitted ? m.name : <span className="muted">🔒 {m.name}</span>}</td>
                <td className="mono small">{m.matter_number}</td><td>{m.client}</td><td>{m.practice}</td>
                <td>{m.ai_status ? <StatusPill status={m.ai_status === "AI PROHIBITED" ? "PROHIBITED" : m.ai_status === "INTERNAL AI ONLY" ? "RESTRICTED" : "PERMITTED_WITH_CONTROLS"} label={m.ai_status} /> : "-"}</td>
                <td>{m.risk_level ? <Badge tone={statusTone(m.risk_level)}>{m.risk_level}</Badge> : "-"}</td>
                <td>{m.access.permitted ? <Badge tone="good">Permitted</Badge> : <Badge tone="bad" title={m.access.reason}>{m.access.code === "ETHICAL_WALL" ? "Ethical wall" : "Denied"}</Badge>}</td>
                <td><button className="btn btn-sm" onClick={() => { setMatterId(m.matter_id); router.push("/"); }}>Open in Copilot</button></td>
              </tr>))}</tbody>
          </table>)}
      </Panel>
    </div>
  );
}
