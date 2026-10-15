import { useEffect, useState } from "react";
import { api, download } from "../lib/api";
import { toolLabel } from "./CopilotPanel";
import type { Operation, Run, Version, Workbook } from "../lib/types";

interface Props {
  workbook: Workbook;
  canRestore: boolean;
  onClose: () => void;
  onRestore: (version: number) => void;
  onViewVersion: (version: number) => void;
  onError: (msg: string) => void;
}

type Tab = "versions" | "operations" | "runs" | "events";

export function ActivityDrawer({ workbook, canRestore, onClose, onRestore, onViewVersion, onError }: Props) {
  const [tab, setTab] = useState<Tab>("versions");
  const [versions, setVersions] = useState<Version[]>([]);
  const [ops, setOps] = useState<Operation[]>([]);
  const [runs, setRuns] = useState<any[]>([]);
  const [events, setEvents] = useState<any[]>([]);
  const [run, setRun] = useState<Run | null>(null);

  useEffect(() => {
    Promise.all([api.versions(workbook.id), api.operations(workbook.id), api.runs(workbook.id), api.activity(workbook.id)])
      .then(([v, o, r, e]) => { setVersions(v); setOps(o); setRuns(r); setEvents(e.events); })
      .catch((e) => onError(e.message));
  }, [workbook.id, workbook.current_version, onError]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <>
      <div className="drawer-backdrop" onClick={onClose} />
      <aside className="drawer" role="dialog" aria-modal="true" aria-label="Activity and version history">
        <div className="drawer-head">
          <h2>Activity</h2>
          <span className="chip neutral">Current: v{workbook.current_version}</span>
          <button className="icon-btn" style={{ marginLeft: "auto" }} onClick={onClose} aria-label="Close activity">✕</button>
        </div>
        <div className="drawer-tabs" role="tablist">
          {(["versions", "operations", "runs", "events"] as Tab[]).map((t) => (
            <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)}>
              {{ versions: "Versions", operations: "Changes", runs: "Requests & usage", events: "Audit trail" }[t]}
            </button>
          ))}
        </div>
        <div className="drawer-body">
          {tab === "versions" && versions.map((v) => (
            <div key={v.version_no} className="timeline-item">
              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <strong>Version {v.version_no}</strong>
                <span className="chip neutral">{v.kind.replace(/_/g, " ")}</span>
                {v.version_no === workbook.current_version && <span className="chip">current</span>}
              </div>
              <div>{v.note}</div>
              <div className="when">{new Date(v.created_at).toLocaleString()} · {v.created_by}</div>
              <div className="actions">
                <button className="btn small" onClick={() => onViewVersion(v.version_no)}>View</button>
                <button className="btn small" onClick={() => download(api.downloadUrl(workbook.id, v.version_no), `v${v.version_no}.xlsx`).catch((e) => onError(e.message))}>Download</button>
                {v.version_no < workbook.current_version && (
                  <button className="btn small" disabled={!canRestore} onClick={() => onRestore(v.version_no)}>Restore this version…</button>
                )}
              </div>
            </div>
          ))}

          {tab === "operations" && (ops.length ? ops.map((o) => (
            <div key={o.id} className="timeline-item">
              <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                <strong>{o.title}</strong>
                <span className={`chip ${o.status === "APPLIED" ? "" : o.status === "PROPOSED" ? "neutral" : "danger"}`}>{o.status.toLowerCase()}</span>
              </div>
              <div className="small-print">{o.action_type.replace(/_/g, " ")} · based on v{o.base_version}{o.result_version ? ` → v${o.result_version}` : ""} · {o.affected_cells} cell(s)</div>
              {o.validation && <div className="small-print">{o.validation.passed ? `✓ ${o.validation.checks.length} validation checks passed` : `✗ validation failed: ${o.validation.checks.filter((c) => !c.passed).map((c) => c.name).join(", ")}`}</div>}
              <div className="when">{new Date(o.created_at).toLocaleString()} · id {o.id}</div>
            </div>
          )) : <p className="small-print">No changes proposed yet.</p>)}

          {tab === "runs" && (
            <>
              <p className="small-print">Each request runs through FloPilot's harness. Token counts are measured; costs are estimates from configured per-token prices.</p>
              {runs.map((r) => (
                <div key={r.id} className="timeline-item">
                  <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                    <strong>{r.intent ?? "request"}</strong><span className="chip neutral">{r.state.toLowerCase()}</span>
                    <span className="small-print">{r.model}</span>
                  </div>
                  <div className="small-print">v{r.workbook_version} · {r.tokens_in + r.tokens_out} tokens · est. ${Number(r.cost_estimate_usd).toFixed(4)}</div>
                  <div className="when">{new Date(r.created_at).toLocaleString()} · <button className="btn ghost small" onClick={() => api.run(r.id).then(setRun).catch((e) => onError(e.message))}>Show steps</button></div>
                  {run && run.id === r.id && (
                    <ol className="small-print">
                      {run.steps.map((s, i) => (
                        <li key={i}>
                          {s.type === "state" ? `→ ${s.state}` : s.type === "tool_call" ? `${toolLabel(s.tool ?? "")} [${s.status}${s.duration_ms !== undefined ? `, ${s.duration_ms} ms` : ""}]` : s.type.replace(/_/g, " ")}
                        </li>
                      ))}
                    </ol>
                  )}
                </div>
              ))}
            </>
          )}

          {tab === "events" && (
            <>
              <p className="small-print">User-readable audit trail. Cell contents and prompts are not recorded here.</p>
              {events.map((e, i) => (
                <div key={i} className="timeline-item">
                  <strong>{e.event_type.replace(/_/g, " ")}</strong>{e.workbook_version ? ` · v${e.workbook_version}` : ""}
                  <div className="small-print">{Object.entries(e.detail).map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(", ") : v}`).join(" · ")}</div>
                  <div className="when">{new Date(e.ts).toLocaleString()} · {e.user_id}</div>
                </div>
              ))}
            </>
          )}
        </div>
      </aside>
    </>
  );
}
