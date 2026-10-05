"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Badge, Empty, ErrorBox, Spinner, StatusPill } from "@/components/ui";
import { useAppState } from "@/hooks/useAppState";
import { api, ApiError } from "@/lib/api";
import { humanize, statusTone } from "@/lib/format";
import type { Action, CopilotResponse, Evidence, MatterDetail, MatterSummary } from "@/types/api";
import { ContextPanel, type Tab } from "./ContextPanel";
import { CopilotResult } from "./ResultCards";

type Msg = { id: number; role: "user"; text: string } | { id: number; role: "assistant"; resp: CopilotResponse } | { id: number; role: "error"; error: ApiError };

const PROMPTS: Record<string, string[]> = {
  default: [
    "Review our contracts for change-of-control clauses and compare them against the firm's M&A playbook.",
    "Which provisions require escalation?",
    "Show me the evidence for this conclusion.",
    "Draft a due diligence summary using only verified findings.",
    "Verify the citations in the draft memo.",
    "Check the AI recommendation against the playbook.",
    "Can I use external AI for this matter?",
    "Prepare a client-ready draft.",
  ],
  "M-1002": ["Send these documents to the external legal AI provider for analysis.", "Why was this workflow blocked?",
    "Can I use external AI for this matter?", "Review the contracts in this matter for change-of-control clauses."],
  "M-1004": ["Should our client accept the $20 million settlement?", "Extract the timeline.", "Run a privilege review",
    "Research settlement evaluation factors."],
  "M-1005": ["Summarize the findings letter.", "Can I use external AI for this matter?"],
};

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <div><div className="ctx-label">{label}</div><div className="ctx-value">{children}</div></div>;
}

function MatterPanel({ matters, matterId, onMatter, detail, detailError, loading }: {
  matters: MatterSummary[]; matterId: string; onMatter: (id: string) => void; detail: MatterDetail | null; detailError: ApiError | null; loading: boolean;
}) {
  const current = matters.find((m) => m.matter_id === matterId);
  return (
    <div className="matter-ctx">
      <div>
        <label className="ctx-label" htmlFor="matter-select">Matter</label>
        <select id="matter-select" className="select" style={{ width: "100%", marginTop: 4 }} value={matterId} onChange={(e) => onMatter(e.target.value)}>
          {matters.map((m) => <option key={m.matter_id} value={m.matter_id}>{m.access.permitted ? "" : "🔒 "}{m.name}</option>)}
          {matters.length === 0 && <option value={matterId}>{matterId}</option>}
        </select>
      </div>
      {loading && <Spinner label="Loading matter" />}
      {detailError && (
        <div className="status-banner tone-bad" role="alert">
          <div><strong>{detailError.code === "ETHICAL_WALL" ? "Ethical wall" : "Access restricted"}</strong>
            <div className="small">{detailError.message}</div>
            <div className="tiny">Matter details are withheld. Any Copilot request will be denied before retrieval and logged.</div></div>
        </div>
      )}
      {detail && (<>
        <Field label="Client">{detail.client.name}</Field>
        <Field label="Matter">{detail.name}</Field>
        <Field label="Matter number"><span className="mono">{detail.matter_number}</span></Field>
        <Field label="Practice">{detail.practice}</Field>
        <Field label="Jurisdiction">{detail.jurisdiction}</Field>
        <Field label="Responsible partner">{detail.responsible_partner}</Field>
        <div className="ctx-group">
          <Field label="Current user">{detail.current_user}</Field>
          <Field label="Role">{humanize(detail.role)}</Field>
          <Field label="Confidentiality"><Badge tone={statusTone(detail.confidentiality === "highly_confidential" ? "HIGH" : "MEDIUM")}>{humanize(detail.confidentiality)}</Badge></Field>
          <Field label="Ethical wall">{detail.ethical_wall.status}</Field>
          <Field label="Access">{detail.access_via === "practice_group" ? "Practice-group access" : "Named matter team"}</Field>
        </div>
        <div className="ctx-group">
          <Field label="AI use"><StatusPill status={detail.ai_status} label={detail.ai_status_label} /></Field>
          <Field label="Permitted AI systems">{detail.permitted_ai_systems.length ? (
            <ul style={{ margin: "2px 0 0", paddingLeft: 16, fontWeight: 400 }} className="small">{detail.permitted_ai_systems.map((s) => <li key={s}>{s}</li>)}</ul>)
            : <span className="muted">None</span>}</Field>
          <Field label="Risk"><Badge tone={statusTone(detail.risk_level)}>{humanize(detail.risk_level)}</Badge></Field>
          <Field label="Human review">{detail.human_review}<div className="tiny muted" style={{ fontWeight: 400 }}>{detail.human_review_level}</div></Field>
        </div>
        <div className="ctx-group">
          <Field label="Documents">{detail.documents.total} <span className="muted small" style={{ fontWeight: 400 }}>
            ({detail.documents.active} active{detail.documents.duplicates ? `, ${detail.documents.duplicates} duplicates` : ""}{detail.documents.unreadable ? `, ${detail.documents.unreadable} unreadable` : ""})</span></Field>
          <div className="tiny muted">{detail.client_ai_policy}</div>
        </div>
      </>)}
      {!detail && !detailError && !loading && current && <Empty title="No matter selected" />}
    </div>
  );
}

export function CopilotWorkspace() {
  const { userId, matterId, setMatterId } = useAppState();
  const router = useRouter();
  const [matters, setMatters] = useState<MatterSummary[]>([]);
  const [detail, setDetail] = useState<MatterDetail | null>(null);
  const [detailError, setDetailError] = useState<ApiError | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [tab, setTab] = useState<Tab>("evidence");
  const [selected, setSelected] = useState<string | null>(null);
  const [extraEvidence, setExtraEvidence] = useState<Record<string, Evidence>>({});
  const [auditKey, setAuditKey] = useState(0);
  const idRef = useRef(1);
  const convRef = useRef<HTMLDivElement>(null);

  const latest = [...msgs].reverse().find((m) => m.role === "assistant") as Extract<Msg, { role: "assistant" }> | undefined;
  const resp = latest?.resp ?? null;

  useEffect(() => { api.matters(userId).then(setMatters).catch(() => setMatters([])); }, [userId]);
  // Switching matter starts a new conversation; switching user (e.g. to a partner for approval) keeps it.
  useEffect(() => { setMsgs([]); setSelected(null); setExtraEvidence({}); }, [matterId]);
  useEffect(() => {
    setDetail(null); setDetailError(null); setDetailLoading(true);
    api.matter(userId, matterId).then(setDetail).catch(setDetailError).finally(() => setDetailLoading(false));
  }, [userId, matterId]);
  // Scroll only the conversation pane (never the window) so the matter context and top bar stay in view.
  useEffect(() => {
    const el = convRef.current;
    if (!el) return;
    const users = el.querySelectorAll<HTMLElement>(".msg-user");
    const last = users[users.length - 1];
    el.scrollTop = last ? Math.max(0, last.offsetTop - el.offsetTop - 12) : 0;
  }, [msgs, busy]);

  const send = useCallback(async (text: string) => {
    const t = text.trim();
    if (!t || busy) return;
    setInput("");
    setMsgs((m) => [...m, { id: idRef.current++, role: "user", text: t }]);
    setBusy(true);
    try {
      const r = await api.chat(userId, matterId, t);
      setMsgs((m) => [...m, { id: idRef.current++, role: "assistant", resp: r }]);
      setSelected(null); setExtraEvidence({});
      setTab(r.status === "ACCESS_DENIED" ? "trace" : r.status === "BLOCKED" ? "policy" : r.evidence.length || r.findings.length ? "evidence"
        : r.citations.length ? "evidence" : "trace");
    } catch (e) {
      setMsgs((m) => [...m, { id: idRef.current++, role: "error", error: e as ApiError }]);
    } finally { setBusy(false); }
  }, [busy, userId, matterId]);

  const selectFinding = useCallback(async (fid: string) => {
    setSelected(fid); setTab("evidence");
    if (!resp || resp.evidence.some((e) => e.finding_id === fid) || extraEvidence[fid]) return;
    try {
      const r = await api.chat(userId, matterId, "Show me the evidence for this conclusion.", fid);
      const ev = r.evidence.find((e) => e.finding_id === fid);
      if (ev) setExtraEvidence((x) => ({ ...x, [fid]: ev }));
    } catch { /* evidence fetch failure leaves the list usable */ }
  }, [resp, extraEvidence, userId, matterId]);

  const onAction = useCallback((a: Action) => {
    if (a.kind === "copilot") send(a.payload.message);
    else if (a.kind === "panel") setTab(a.payload.tab as Tab);
    else if (a.kind === "review") setTab("approval");
    else if (a.kind === "navigate") router.push(a.payload.href);
  }, [send, router]);

  const prompts = PROMPTS[matterId] ?? PROMPTS.default;

  return (
    <div className="workspace">
      <aside className="ws-left" aria-label="Matter context">
        <MatterPanel matters={matters} matterId={matterId} onMatter={setMatterId} detail={detail} detailError={detailError} loading={detailLoading} />
      </aside>
      <section className="ws-center" aria-label="LexGuard Copilot">
        <div className="conversation" aria-live="polite" ref={convRef}>
          {msgs.length === 0 && (
            <div className="panel" style={{ padding: 20 }}>
              <h2>LexGuard Copilot</h2>
              <p className="muted" style={{ margin: "6px 0 12px" }}>
                One Copilot for the matter. LexGuard checks access, ethical walls and client AI policy before any retrieval,
                routes work to the right agents or providers, verifies every material proposition, and keeps the lawyer as the final decision-maker.
              </p>
              <div className="row small muted"><Badge tone="good">MatterGuard</Badge><Badge tone="good">Permission-aware RAG</Badge>
                <Badge tone="good">Citation verification</Badge><Badge tone="good">PlaybookGuard</Badge><Badge tone="good">Human approval</Badge></div>
            </div>
          )}
          {msgs.map((m) => m.role === "user" ? <div key={m.id} className="msg-user">{m.text}</div>
            : m.role === "assistant" ? <CopilotResult key={m.id} resp={m.resp} onAction={onAction} onFinding={selectFinding} />
            : <ErrorBox key={m.id} error={m.error} />)}
          {busy && <div className="panel" style={{ padding: 12 }}><Spinner label="LexGuard is checking access and policy, then orchestrating agents" /></div>}
        </div>
        <div className="composer">
          <div className={`chips ${msgs.length ? "compact" : ""}`} aria-label="Suggested prompts">
            {prompts.map((p) => <button key={p} className="chip" onClick={() => send(p)} disabled={busy}>{p}</button>)}
          </div>
          <form onSubmit={(e) => { e.preventDefault(); send(input); }}>
            <textarea className="textarea" aria-label="Ask LexGuard" placeholder={`Ask about ${detail?.name ?? "this matter"}…  (Enter to send, Shift+Enter for a new line)`}
              value={input} maxLength={2000} onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(input); } }} />
            <button className="btn btn-primary" type="submit" disabled={busy || !input.trim()}>Send</button>
          </form>
        </div>
      </section>
      <aside className="ws-right" aria-label="Context panel">
        <ContextPanel resp={resp} tab={tab} setTab={setTab} selected={selected} onSelect={selectFinding} extraEvidence={extraEvidence}
          userId={userId} onDecided={() => setAuditKey((k) => k + 1)} auditKey={auditKey} />
      </aside>
    </div>
  );
}
