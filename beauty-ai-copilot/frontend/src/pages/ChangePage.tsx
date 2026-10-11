import { useCallback, useEffect, useRef, useState } from "react";
import { NavLink, useParams } from "react-router-dom";
import { api } from "../api";
import { TABS, useApp } from "../App";
import { Badge, ErrorBox, SourceLink, usePoll } from "../components";
import { ApprovalsTab, AuditTab, DevelopmentTab, EvidenceTab, ImpactTab, MonitoringTab, OverviewTab, ReleaseTab, RequirementsTab } from "./tabs";
import EvaluationTab from "./EvaluationTab";

const FLOW = ["DRAFT", "NEEDS_CLARIFICATION", "REQUIREMENTS_APPROVED", "IMPACT_REVIEW", "DEVELOPMENT", "EVALUATING", "REVIEW_REQUIRED",
  "RELEASE_APPROVED", "CANARY", "MONITORING", "RELEASED"];

export type TabProps = { d: any; reload: () => void };

function Stepper({ status }: { status: string }) {
  const idx = FLOW.indexOf(status);
  return (
    <div className="stepper" aria-label="Lifecycle">
      {FLOW.map((s, i) => <span key={s} className={s === status ? "current" : idx > i ? "done" : ""}>{s}</span>)}
      {idx < 0 && <span className="current">{status}</span>}
    </div>
  );
}

function Copilot({ d, reload }: TabProps) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<unknown>(null);
  const box = useRef<HTMLDivElement>(null);
  // Scroll only the message list (never the page) to the newest message.
  useEffect(() => { if (box.current) box.current.scrollTop = box.current.scrollHeight; }, [d.messages.length]);
  const send = async (m: string) => {
    if (!m.trim()) return;
    setBusy(true); setErr(null);
    try { await api(`/api/changes/${d.change.id}/copilot`, { method: "POST", body: { message: m } }); setText(""); reload(); }
    catch (e) { setErr(e); } finally { setBusy(false); }
  };
  return (
    <aside className="card copilot" aria-label="Copilot conversation">
      <div className="spread"><h2 style={{ margin: 0 }}>Copilot</h2><span className="small muted">decision summaries, not chain-of-thought</span></div>
      <div className="msgs" data-testid="copilot-messages" ref={box}>
        {d.messages.map((m: any) => (
          <div key={m.id} className={`msg ${m.role}`}>
            <div className="who">{m.author}</div>
            {m.text}
            {m.refs?.length > 0 && <div className="small" style={{ marginTop: 4 }}>{m.refs.slice(0, 4).map((r: any, i: number) => <span key={i}>{i > 0 && " · "}<SourceLink r={r} /></span>)}</div>}
          </div>
        ))}
      </div>
      <ErrorBox error={err} />
      <div className="row" style={{ marginTop: 8 }}>
        {["What's next?", "Why is release blocked?", "Worst cells?"].map((q) => <button key={q} className="small" onClick={() => send(q)} disabled={busy}>{q}</button>)}
      </div>
      <form className="row" style={{ marginTop: 6 }} onSubmit={(e) => { e.preventDefault(); send(text); }}>
        <input aria-label="Ask the copilot" value={text} onChange={(e) => setText(e.target.value)} placeholder="Ask about status, blockers, evidence…" style={{ flex: 1 }} />
        <button type="submit" disabled={busy}>Ask</button>
      </form>
    </aside>
  );
}

export default function ChangePage() {
  const { id = "BR-101", tab = "overview" } = useParams();
  const { version } = useApp();
  const [d, setD] = useState<any>(null);
  const [err, setErr] = useState<unknown>(null);
  const reload = useCallback(() => { api(`/api/changes/${id}`).then((x) => { setD(x); setErr(null); }).catch(setErr); }, [id]);
  useEffect(() => { reload(); try { localStorage.setItem("lastChange", id); } catch { /* ignore */ } }, [reload, version, id]);
  usePoll(reload, d?.change?.status === "EVALUATING", 1000);
  if (err) return <ErrorBox error={err} />;
  if (!d) return <div>Loading…</div>;
  const props = { d, reload };
  const body = {
    overview: <OverviewTab {...props} />, requirements: <RequirementsTab {...props} />, evidence: <EvidenceTab {...props} />,
    impact: <ImpactTab {...props} />, development: <DevelopmentTab {...props} />, evaluation: <EvaluationTab {...props} />,
    approvals: <ApprovalsTab {...props} />, release: <ReleaseTab {...props} />, monitoring: <MonitoringTab {...props} />, audit: <AuditTab {...props} />,
  }[tab] ?? <OverviewTab {...props} />;
  return (
    <div>
      <div className="spread">
        <div>
          <h1><code>{d.change.id}</code> {d.change.title}</h1>
          <div className="row"><span>Status</span><Badge s={d.change.status} /><span className="small muted">trace {d.change.trace_id.slice(0, 8)}</span></div>
        </div>
      </div>
      <Stepper status={d.change.status} />
      <nav className="tabs" aria-label="Change sections">
        {TABS.map(([k, label]) => <NavLink key={k} to={`/changes/${id}/${k}`} className={tab === k ? "active" : ""}>{k === "overview" ? "Overview" : label}</NavLink>)}
      </nav>
      <div className="grid2">
        <div>{body}</div>
        <Copilot {...props} />
      </div>
    </div>
  );
}
