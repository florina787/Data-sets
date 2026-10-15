import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ActivityDrawer } from "./components/ActivityDrawer";
import { FloMinIcon } from "./components/Brand";
import { CopilotPanel, type ChatItem } from "./components/CopilotPanel";
import { Grid, type ActiveInfo, type Selection } from "./components/Grid";
import { LeftPanel } from "./components/LeftPanel";
import { Landing, SignIn } from "./components/Screens";
import { ApiError, api, auth, download, saveText } from "./lib/api";
import { cellRef, parseRange, uid, type SelectionStats } from "./lib/format";
import type { AppConfig, AssistantResult, CellChange, GridRow, Issue, Operation, Profile, Run, Source, User, Workbook } from "./lib/types";

const TERMINAL = new Set(["COMPLETED", "FAILED", "CANCELLED", "ROLLED_BACK", "AWAITING_APPROVAL"]);
type Toast = { id: string; text: string; kind: "ok" | "error" };

export default function App() {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [authError, setAuthError] = useState<string | null>(null);
  const [workbooks, setWorkbooks] = useState<Workbook[]>([]);
  const [wb, setWb] = useState<Workbook | null>(null);
  const [viewVersion, setViewVersion] = useState<number | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [sheet, setSheet] = useState<string | null>(null);
  const [selection, setSelection] = useState<Selection | null>(null);
  const [info, setInfo] = useState<ActiveInfo | null>(null);
  const [stats, setStats] = useState<SelectionStats | null>(null);
  const [items, setItems] = useState<ChatItem[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [conversations, setConversations] = useState<{ id: string; title: string; updated_at: string }[]>([]);
  const [activeRun, setActiveRun] = useState<Run | null>(null);
  const [opsById, setOpsById] = useState<Record<string, Operation>>({});
  const [preview, setPreview] = useState<Operation | null>(null);
  const [compareMode, setCompareMode] = useState<"before" | "after">("after");
  const [find, setFind] = useState("");
  const [filter, setFilter] = useState<{ q: string; rows: GridRow[]; count: number } | null>(null);
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [rightCollapsed, setRightCollapsed] = useState(false);
  const [drawer, setDrawer] = useState(false);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [uploadBusy, setUploadBusy] = useState(false);
  const [landingError, setLandingError] = useState<string | null>(null);
  const [justApplied, setJustApplied] = useState(false);
  const [menu, setMenu] = useState<null | "export" | "user">(null);
  const lastPrompt = useRef<string>("");
  // Incremented on sign-out / workbook switch so late responses from the previous session are ignored.
  const session = useRef(0);

  const version = viewVersion ?? wb?.current_version ?? 1;
  const canApprove = user?.role === "analyst" || user?.role === "admin";

  const toast = useCallback((text: string, kind: Toast["kind"] = "ok") => {
    const id = uid();
    setToasts((t) => [...t, { id, text, kind }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), kind === "error" ? 7000 : 4000);
  }, []);
  const onError = useCallback((m: string) => toast(m, "error"), [toast]);

  // ---------------------------------------------------------------- bootstrap
  useEffect(() => {
    api.config().then(setConfig).catch((e) => setAuthError(e.message));
    if (auth.get()) api.me().then(setUser).catch(() => auth.clear());
  }, []);

  useEffect(() => {
    if (!user) return;
    api.workbooks().then((list) => {
      setWorkbooks(list);
      if (list.length && !wb) setWb(list[0]);
    }).catch((e) => onError(e.message));
  }, [user]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!wb) return;
    setProfile(null);
    setProfileError(null);
    api.profile(wb.id, version).then((p) => {
      setProfile(p);
      setSheet((s) => (s && p.sheets.some((x) => x.name === s) ? s : p.sheets.find((x) => x.state === "visible")?.name ?? p.sheets[0]?.name ?? null));
    }).catch((e) => setProfileError(e.message));
  }, [wb?.id, version]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (wb) api.conversations(wb.id).then(setConversations).catch(() => undefined);
  }, [wb?.id, items.length]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { setFilter(null); setFind(""); }, [sheet, version]);

  // ---------------------------------------------------------------- run polling
  useEffect(() => {
    if (!activeRun || TERMINAL.has(activeRun.state)) return;
    const started = session.current;
    const t = setTimeout(async () => {
      try {
        const run = await api.run(activeRun.id);
        if (started !== session.current) return;
        if (TERMINAL.has(run.state)) {
          finishRun(run);
        } else setActiveRun(run);
      } catch (e) {
        setActiveRun(null);
        onError(e instanceof Error ? e.message : "Lost track of the request.");
      }
    }, 350);
    return () => clearTimeout(t);
  }, [activeRun]); // eslint-disable-line react-hooks/exhaustive-deps

  function finishRun(run: Run) {
    setActiveRun(null);
    const result: AssistantResult = run.result ?? { schema_version: "1.0", type: "error", text: run.error ?? "The request did not finish.", retryable: true };
    setItems((xs) => [...xs, { kind: "bot", id: run.id, result, prompt: lastPrompt.current }]);
    if (result.operations?.length) setOpsById((m) => ({ ...m, ...Object.fromEntries(result.operations!.map((o) => [o.id, o])) }));
  }

  // ---------------------------------------------------------------- actions
  async function pickUser(key: string) {
    try {
      const r = await api.demoLogin(key);
      auth.set(r.token);
      setUser(r.user);
    } catch (e) {
      setAuthError(e instanceof Error ? e.message : "Sign-in failed.");
    }
  }

  function signOut() {
    session.current++;
    auth.clear();
    setUser(null); setWb(null); setWorkbooks([]); setItems([]); setProfile(null); setConversationId(null); setMenu(null);
    setActiveRun(null); setViewVersion(null); setSelection(null); setPreview(null); setOpsById({}); setFilter(null); setSheet(null);
  }

  async function openWorkbook(next: Workbook) {
    session.current++;
    setActiveRun(null);
    setWb(next); setViewVersion(null); setItems([]); setConversationId(null); setSelection(null); setPreview(null); setSheet(null);
  }

  async function upload(file: File) {
    setUploadBusy(true); setLandingError(null);
    try {
      const created = await api.upload(file);
      setWorkbooks((l) => [created, ...l]);
      await openWorkbook(created);
      toast(`Uploaded “${created.name}”. The original is kept as version 1.`);
    } catch (e) {
      setLandingError(e instanceof Error ? e.message : "Upload failed.");
    } finally { setUploadBusy(false); }
  }

  async function loadDemo() {
    setUploadBusy(true); setLandingError(null);
    try {
      const created = await api.loadDemo();
      setWorkbooks((l) => [created, ...l]);
      await openWorkbook(created);
    } catch (e) {
      setLandingError(e instanceof Error ? e.message : "Could not open the demo.");
    } finally { setUploadBusy(false); }
  }

  const selectionLabel = useMemo(() => {
    if (!selection) return null;
    const a = cellRef(selection.anchor.col, selection.anchor.row);
    const f = cellRef(selection.focus.col, selection.focus.row);
    return `${selection.sheet}!${a === f ? a : `${cellRef(Math.min(selection.anchor.col, selection.focus.col), Math.min(selection.anchor.row, selection.focus.row))}:${cellRef(Math.max(selection.anchor.col, selection.focus.col), Math.max(selection.anchor.row, selection.focus.row))}`}`;
  }, [selection]);

  async function send(text: string) {
    if (!wb) return;
    lastPrompt.current = text;
    setItems((xs) => [...xs, { kind: "user", id: uid(), text, selection: selectionLabel }]);
    try {
      const sel = selection ? { sheet: selection.sheet, cell: cellRef(selection.focus.col, selection.focus.row), range: selectionLabel?.split("!")[1] } : null;
      const started = session.current;
      const r = await api.chat(wb.id, text, conversationId, sel);
      if (started !== session.current) return;  // user signed out or switched workbook meanwhile
      setConversationId(r.conversation_id);
      setActiveRun({ id: r.run_id, state: "RECEIVED", progress: "Received your request…", steps: [] } as unknown as Run);
    } catch (e) {
      setItems((xs) => [...xs, { kind: "bot", id: uid(), prompt: text, result: { schema_version: "1.0", type: "error", text: e instanceof Error ? e.message : "Request failed.", retryable: e instanceof ApiError ? e.retryable : true } }]);
    }
  }

  async function cancelRun() {
    if (!activeRun) return;
    try { await api.cancelRun(activeRun.id); } catch (e) { onError(e instanceof Error ? e.message : "Cancel failed."); }
  }

  async function refreshWorkbook() {
    if (!wb) return;
    const fresh = await api.workbook(wb.id);
    setWb(fresh);
    setWorkbooks((l) => l.map((w) => (w.id === fresh.id ? fresh : w)));
  }

  async function approve(op: Operation, ack: boolean, key: string) {
    try {
      const done = await api.approve(op, ack, key);
      setOpsById((m) => ({ ...m, [done.id]: done }));
      setPreview(null);
      if (done.status === "APPLIED") {
        setViewVersion(null);
        await refreshWorkbook();
        setJustApplied(true);
        setTimeout(() => setJustApplied(false), 1200);
        toast(`Applied “${done.title}”. Saved as version ${done.result_version} after ${done.validation?.checks.length ?? 0} validation checks.`);
      } else if (done.status === "FAILED") {
        toast("Validation failed, so nothing was changed. See the details in the proposal.", "error");
      }
    } catch (e) {
      onError(e instanceof Error ? e.message : "Approval failed.");
      try { const latest = await api.operation(op.id); setOpsById((m) => ({ ...m, [latest.id]: latest })); } catch { /* ignore */ }
    }
  }

  async function reject(op: Operation) {
    try {
      const r = await api.reject(op.id);
      setOpsById((m) => ({ ...m, [r.id]: r }));
      setPreview(null);
    } catch (e) { onError(e instanceof Error ? e.message : "Reject failed."); }
  }

  async function refreshOp(op: Operation) {
    try {
      const answer = await api.refresh(op.id);
      setItems((xs) => [...xs, { kind: "bot", id: uid(), result: answer }]);
      setOpsById((m) => ({ ...m, ...Object.fromEntries((answer.operations ?? []).map((o: Operation) => [o.id, o])) }));
      const old = await api.operation(op.id);
      setOpsById((m) => ({ ...m, [old.id]: old }));
    } catch (e) { onError(e instanceof Error ? e.message : "Could not prepare the change again."); }
  }

  async function restore(v: number) {
    if (!wb) return;
    try {
      const answer = await api.restore(wb.id, v);
      setDrawer(false); setRightCollapsed(false);
      if (answer.conversation_id && answer.conversation_id !== conversationId) {
        setConversationId(answer.conversation_id);
      }
      setItems((xs) => [...xs, { kind: "user", id: uid(), text: `Restore version ${v}` }, { kind: "bot", id: uid(), result: answer }]);
      setOpsById((m) => ({ ...m, ...Object.fromEntries((answer.operations ?? []).map((o: Operation) => [o.id, o])) }));
    } catch (e) { onError(e instanceof Error ? e.message : "Restore failed."); }
  }

  function goToSource(s: Source) {
    if (wb && s.version !== wb.current_version && s.status === "stale") toast("This reference belongs to an older version.", "error");
    const range = parseRange(s.range);
    setSheet(s.sheet);
    if (range) setSelection({ sheet: s.sheet, anchor: { col: range.c0, row: range.r0 }, focus: { col: range.c1, row: range.r1 } });
  }

  function onIssue(i: Issue) {
    setSheet(i.sheet);
    const range = i.cell ? parseRange(i.cell) : i.range ? parseRange(i.range) : null;
    if (range) setSelection({ sheet: i.sheet, anchor: { col: range.c0, row: range.r0 }, focus: { col: range.c0, row: range.r0 } });
    if (i.suggested_prompt && !activeRun) void send(i.suggested_prompt);
  }

  function togglePreview(op: Operation | null) {
    setPreview(op);
    setCompareMode("after");
    const first = op?.changes_sample?.[0];
    if (op && first) {
      setViewVersion(null);
      setSheet(first.sheet);
      const r = parseRange(first.cell);
      if (r) setSelection({ sheet: first.sheet, anchor: { col: r.c0, row: r.r0 }, focus: { col: r.c0, row: r.r0 } });
    }
  }

  async function openConversation(id: string) {
    try {
      const msgs = await api.messages(id);
      const next: ChatItem[] = msgs.map((m) => m.role === "user"
        ? { kind: "user", id: m.id, text: m.content.text, selection: m.content.selection ? `${m.content.selection.sheet}!${m.content.selection.range ?? m.content.selection.cell}` : null }
        : { kind: "bot", id: m.id, result: m.content });
      setItems(next);
      setConversationId(id);
      const opIds = next.flatMap((x) => (x.kind === "bot" ? (x.result.operations ?? []).map((o) => o.id) : []));
      const fresh = await Promise.all(opIds.map((oid) => api.operation(oid).catch(() => null)));
      setOpsById((m) => ({ ...m, ...Object.fromEntries(fresh.filter(Boolean).map((o) => [o!.id, o!])) }));
    } catch (e) { onError(e instanceof Error ? e.message : "Could not open the conversation."); }
  }

  async function runFind() {
    if (!wb || !sheet || !find.trim()) { setFilter(null); return; }
    try {
      const r = await api.find(wb.id, sheet, version, find);
      setFilter({ q: find, rows: r.rows, count: r.match_count });
    } catch (e) { onError(e instanceof Error ? e.message : "Find failed."); }
  }

  const changes = useMemo(() => {
    if (!preview?.changes_sample) return null;
    return new Map<string, CellChange>(preview.changes_sample.map((c) => [`${c.sheet}!${c.cell}`, c]));
  }, [preview]);

  // ---------------------------------------------------------------- render
  if (!user) return <SignIn config={config} onPick={pickUser} error={authError} />;

  const header = (
    <header className="header">
      <div className="brand">
        <img src="/flomin-icon.svg" alt="" />
        <div><div className="brand-name">FloPilot</div><div className="brand-sub">Florina’s Excel Copilot</div></div>
      </div>
      <div className="wbname">
        {wb && <><strong title={wb.name}>{wb.name}</strong>
          <span className="save-status" aria-live="polite">{viewVersion && viewVersion !== wb.current_version ? `Viewing v${viewVersion} (read-only)` : `Saved · version ${wb.current_version}`}</span></>}
      </div>
      {config && <span className="mode-badge" title={config.llm.label}>{config.llm.mode === "llm" ? `AI: ${config.llm.model}` : "Demo mode · no AI model"}</span>}
      <div className="header-actions">
        {wb && <button className="btn on-green small" onClick={() => setDrawer(true)}>Activity</button>}
        {wb && (
          <div className="menu">
            <button className="btn on-green small" aria-haspopup="menu" aria-expanded={menu === "export"} onClick={() => setMenu(menu === "export" ? null : "export")}>Export ▾</button>
            {menu === "export" && (
              <div className="menu-list" role="menu" onMouseLeave={() => setMenu(null)}>
                <button role="menuitem" disabled={!canApprove} onClick={() => { setMenu(null); download(api.downloadUrl(wb.id, version), "workbook.xlsx").catch((e) => onError(e.message)); }}>Download workbook (.xlsx) — version {version}</button>
                <button role="menuitem" disabled={!canApprove || !sheet} onClick={() => { setMenu(null); download(api.downloadUrl(wb.id, version, "csv", sheet ?? undefined), "sheet.csv").catch((e) => onError(e.message)); }}>Download “{sheet}” as CSV (values)</button>
                <button role="menuitem" disabled={!canApprove} onClick={() => { setMenu(null); api.summary(wb.id, conversationId).then((t) => saveText(t, `${wb.name} - FloPilot summary.md`)).catch((e) => onError(e.message)); }}>Download analysis summary (.md)</button>
                <div className="hint">Charts in the chat are shown in FloPilot only. Charts added with “Add to workbook” are embedded in the .xlsx.{!canApprove ? " Your role cannot export." : ""}</div>
              </div>
            )}
          </div>
        )}
        <div className="menu">
          <button className="btn on-green small" aria-haspopup="menu" aria-expanded={menu === "user"} onClick={() => setMenu(menu === "user" ? null : "user")}>{user.name.split(" ")[0]} ▾</button>
          {menu === "user" && (
            <div className="menu-list" role="menu" onMouseLeave={() => setMenu(null)}>
              <div className="hint">{user.name} · role {user.role}</div>
              <button role="menuitem" onClick={signOut}>Sign out</button>
            </div>
          )}
        </div>
      </div>
    </header>
  );

  if (!wb) {
    return (
      <div className="app">
        {header}
        <Landing config={config} busy={uploadBusy} error={landingError} onUpload={upload} onDemo={loadDemo} canUpload={canApprove} />
        <Toasts toasts={toasts} />
      </div>
    );
  }

  const sheetProfile = profile?.sheets.find((s) => s.name === sheet);
  return (
    <div className="app">
      {header}
      <div className="body">
        <LeftPanel collapsed={leftCollapsed} onToggle={() => setLeftCollapsed((c) => !c)} workbooks={workbooks} activeId={wb.id}
          onOpenWorkbook={(id) => { const w = workbooks.find((x) => x.id === id); if (w) void openWorkbook(w); }}
          onNewWorkbook={() => { setWb(null); setProfile(null); }} profile={profile} activeSheet={sheet} onSheet={setSheet} onIssue={onIssue}
          conversations={conversations} activeConversation={conversationId} onConversation={openConversation} />

        <main className="center" aria-label="Spreadsheet workspace">
          {viewVersion && viewVersion !== wb.current_version && (
            <div className="banner">Viewing version {viewVersion} (read-only). FloPilot answers questions about the current version. <button className="btn small" onClick={() => setViewVersion(null)}>Back to version {wb.current_version}</button></div>
          )}
          {profileError && <div className="banner error" role="alert">{profileError} <button className="btn small" onClick={() => setWb({ ...wb })}>Retry</button></div>}
          {preview && (
            <div className="compare-bar" role="region" aria-label="Change preview">
              <strong>Previewing:</strong> {preview.title}
              <span className="seg" role="group" aria-label="Show values">
                <button aria-pressed={compareMode === "before"} onClick={() => setCompareMode("before")}>Before</button>
                <button aria-pressed={compareMode === "after"} onClick={() => setCompareMode("after")}>After</button>
              </span>
              <span className="small-print" style={{ color: "#6b4e00" }}>Highlighted: {Math.min(preview.changes_total, preview.changes_sample?.length ?? 0)} of {preview.changes_total} changed cells. Not applied yet.</span>
              <button className="btn small" style={{ marginLeft: "auto" }} onClick={() => setPreview(null)}>Close preview</button>
            </div>
          )}
          <div className="toolbar">
            <label className="sr-only" htmlFor="namebox">Name box</label>
            <input id="namebox" className="namebox" readOnly value={selectionLabel?.split("!")[1] ?? ""} />
            <span className="fx" aria-hidden="true">fx</span>
            <div className={`formula-bar ${info?.formula ? "formula" : ""}`} aria-label="Formula bar" title={info?.formula ?? info?.display ?? ""}>
              {info?.formula ?? info?.display ?? ""}{info?.uncalculated ? "  (no saved result — Excel recalculates on open)" : ""}
            </div>
            <label className="sr-only" htmlFor="find">Find rows</label>
            <input id="find" className="find" placeholder="Filter rows containing…" value={find}
              onChange={(e) => { setFind(e.target.value); if (!e.target.value) setFilter(null); }}
              onKeyDown={(e) => { if (e.key === "Enter") void runFind(); if (e.key === "Escape") { setFind(""); setFilter(null); } }} />
          </div>
          {filter && <div className="banner">{filter.count} row(s) on {sheet} contain “{filter.q}” (header row kept). <button className="btn small" onClick={() => { setFilter(null); setFind(""); }}>Clear filter</button></div>}
          {sheet ? (
            <Grid workbookId={wb.id} version={version} sheet={sheet} selection={selection} onSelect={setSelection}
              changes={changes} compareMode={compareMode} filterRows={filter?.rows ?? null}
              onInfo={(i, s) => { setInfo(i); setStats(s); }} onError={onError} />
          ) : <div className="grid-loading" role="status">{profileError ? "" : "Inspecting your workbook…"}</div>}
          <div className="tabs-bar" role="tablist" aria-label="Sheets">
            {profile?.sheets.map((s) => (
              <button key={s.name} role="tab" aria-selected={s.name === sheet} className={`sheet-tab ${s.name === sheet ? "active" : ""}`} onClick={() => setSheet(s.name)}>
                {s.name}{s.state !== "visible" && <span className="hidden-mark">(hidden)</span>}
              </button>
            ))}
          </div>
          <div className="status-bar" aria-live="polite">
            <span>{activeRun ? activeRun.progress : "Ready"}</span>
            {sheetProfile?.table && <span>{sheetProfile.table.row_count.toLocaleString()} data rows · {sheetProfile.formula_cells} formulas</span>}
            <span className="right">
              {stats && stats.count > 1 && <>
                {stats.average !== null && <span>Average: {stats.average.toLocaleString("en-US", { maximumFractionDigits: 2 })}</span>}
                <span>Count: {stats.count}</span>
                {stats.numericCount > 0 && <span>Sum: {stats.sum.toLocaleString("en-US", { maximumFractionDigits: 2 })}</span>}
              </>}
              <span>Version {version}</span>
              <span>100%</span>
            </span>
          </div>
        </main>

        <CopilotPanel collapsed={rightCollapsed} onToggle={() => setRightCollapsed((c) => !c)} items={items} activeRun={activeRun}
          modeLabel={config?.llm.mode === "llm" ? `AI: ${config.llm.model}` : "Demo mode"} selectionLabel={selectionLabel}
          operations={opsById} canApprove={canApprove} previewOpId={preview?.id ?? null}
          disabled={!!viewVersion && viewVersion !== wb.current_version} justApplied={justApplied}
          onSend={send} onCancel={cancelRun} onSource={goToSource} onPreview={togglePreview} onApprove={approve} onReject={reject}
          onRefresh={refreshOp} onNewConversation={() => { setItems([]); setConversationId(null); setPreview(null); }} />
      </div>
      {drawer && <ActivityDrawer workbook={wb} canRestore={canApprove} onClose={() => setDrawer(false)} onRestore={restore}
        onViewVersion={(v) => { setViewVersion(v === wb.current_version ? null : v); setDrawer(false); setPreview(null); }} onError={onError} />}
      <Toasts toasts={toasts} />
      <span className="sr-only"><FloMinIcon /></span>
    </div>
  );
}

function Toasts({ toasts }: { toasts: Toast[] }) {
  return (
    <div className="toast-area" aria-live="assertive">
      {toasts.map((t) => <div key={t.id} className={`toast ${t.kind === "error" ? "error" : ""}`} role={t.kind === "error" ? "alert" : "status"}>{t.kind === "ok" ? "✓" : "!"} {t.text}</div>)}
    </div>
  );
}
