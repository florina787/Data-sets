import type { Issue, Profile, Workbook } from "../lib/types";

interface Props {
  collapsed: boolean;
  onToggle: () => void;
  workbooks: Workbook[];
  activeId: string | null;
  onOpenWorkbook: (id: string) => void;
  onNewWorkbook: () => void;
  profile: Profile | null;
  activeSheet: string | null;
  onSheet: (name: string) => void;
  onIssue: (issue: Issue) => void;
  conversations: { id: string; title: string; updated_at: string }[];
  activeConversation: string | null;
  onConversation: (id: string) => void;
}

export function LeftPanel(p: Props) {
  if (p.collapsed) {
    return (
      <nav className="left collapsed" aria-label="Workbook navigation (collapsed)">
        <div className="collapse-row"><button className="icon-btn" onClick={p.onToggle} aria-label="Expand workbook navigation">»</button></div>
      </nav>
    );
  }
  const counts = p.profile?.issue_counts ?? {};
  return (
    <nav className="left" aria-label="Workbook navigation">
      <div className="collapse-row"><button className="icon-btn" onClick={p.onToggle} aria-label="Collapse workbook navigation">«</button></div>
      <div className="left-scroll">
        <div className="section-title" style={{ marginTop: 4 }}>
          Workbooks <button className="btn ghost small" onClick={p.onNewWorkbook} aria-label="Upload or open another workbook">+ New</button>
        </div>
        {p.workbooks.map((w) => (
          <button key={w.id} className={`list-btn ${w.id === p.activeId ? "active" : ""}`} onClick={() => p.onOpenWorkbook(w.id)} title={w.name}>
            <span aria-hidden="true">▦</span>
            <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{w.name}</span>
            <span className="meta">v{w.current_version}</span>
          </button>
        ))}

        {p.profile && (
          <>
            <div className="section-title">Sheets</div>
            {p.profile.sheets.map((s) => (
              <button key={s.name} className={`list-btn ${s.name === p.activeSheet ? "active" : ""}`} onClick={() => p.onSheet(s.name)}>
                <span aria-hidden="true">{s.state === "visible" ? "▤" : "◌"}</span>
                <span>{s.name}{s.state !== "visible" ? " (hidden)" : ""}</span>
                <span className="meta">{s.table ? `${s.table.row_count.toLocaleString()} rows` : "empty"}</span>
              </button>
            ))}

            <div className="section-title">Data quality</div>
            <div className="dq-counts">
              <span className="chip danger">{counts.error ?? 0} errors</span>
              <span className="chip warn">{counts.warning ?? 0} warnings</span>
              <span className="chip neutral">{counts.info ?? 0} notes</span>
            </div>
            {p.profile.issues.slice(0, 14).map((i) => (
              <button key={i.id + i.message} className="dq-item" onClick={() => p.onIssue(i)} title={i.suggested_prompt ? `Ask: ${i.suggested_prompt}` : "Show in grid"}>
                <span className={`sev ${i.severity}`} aria-label={i.severity} />
                <span><strong>{i.sheet}</strong>: {i.message}</span>
              </button>
            ))}
            {p.profile.issues.length > 14 && <div className="small-print" style={{ padding: "4px 6px" }}>+{p.profile.issues.length - 14} more — ask “What’s in this workbook?”</div>}
            {p.profile.fidelity.at_risk.length > 0 && (
              <div className="small-print" style={{ padding: "6px" }}>
                ⚠ Contains {p.profile.fidelity.at_risk.map((r) => r.feature.replace(/_/g, " ")).join(", ")} that edits may not preserve. FloPilot checks before applying.
              </div>
            )}
          </>
        )}

        {p.conversations.length > 0 && (
          <>
            <div className="section-title">Recent conversations</div>
            {p.conversations.slice(0, 8).map((c) => (
              <button key={c.id} className={`list-btn ${c.id === p.activeConversation ? "active" : ""}`} onClick={() => p.onConversation(c.id)} title={c.title}>
                <span aria-hidden="true">💬</span>
                <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{c.title}</span>
              </button>
            ))}
          </>
        )}
      </div>
    </nav>
  );
}
