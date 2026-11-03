import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowUpRight, ChevronDown, Download, Loader2, Paperclip, Send, Sparkles, Wrench, X } from "lucide-react";
import { api, chatStream, reportUrl } from "../lib/api";
import { periodParams, useApp } from "../lib/store";
import { SherinAvatar } from "./SherinAvatar";
import { DiffView, Markdown, Badge } from "./ui";
import { Plot } from "./Plot";
import { ApprovalCard } from "./ApprovalCard";
import { RunInline } from "./RunInline";
import { AGENT_COLORS, SERIES, wrap } from "../lib/format";

export interface Turn { role: "user" | "assistant"; content: string; payload?: any; activity?: any[]; streaming?: boolean; attachments?: string[] }

export const OPENING = "Hello, I'm Sherin. I can tell you what FLO Bank earned and spent, what I cost, the verified value I created, and which decisions need a human. Every figure comes from the bank's records.";

export function ChatChart({ c, cur }: { c: any; cur: string }) {
  if (c.kind === "table") {
    const cols = Object.keys(c.rows[0] ?? {});
    return (
      <div className="mt-2 overflow-x-auto rounded-xl border border-line scroll-thin">
        <table className="w-full text-[11px]"><thead><tr className="bg-flo-50">{cols.map((k) => <th key={k} className="px-2 py-1 text-left font-semibold">{k}</th>)}</tr></thead>
          <tbody>{c.rows.map((r: any, i: number) => <tr key={i} className="border-t border-line">{cols.map((k) => <td key={k} className="px-2 py-1 tnum">{typeof r[k] === "number" ? r[k].toLocaleString() : String(r[k])}</td>)}</tr>)}</tbody></table>
      </div>
    );
  }
  let data: any[] = [];
  let layout: any = { margin: { l: 48, r: 8, t: 8, b: 36 }, showlegend: true, legend: { orientation: "h", y: -0.3, font: { size: 10 } } };
  if (c.kind === "pie") { data = [{ type: "pie", hole: 0.5, labels: c.labels, values: c.values, marker: { colors: AGENT_COLORS }, textinfo: "percent" }]; layout = { ...layout, showlegend: false, margin: { l: 4, r: 4, t: 4, b: 4 } }; }
  else if (c.kind === "waterfall") { data = [{ type: "waterfall", x: c.labels.map((l: string) => wrap(l.replace(/ \(.*\)/, ""), 11)), y: c.values, measure: c.measures, increasing: { marker: { color: SERIES.savings } }, decreasing: { marker: { color: SERIES.cost } }, totals: { marker: { color: SERIES.profit } } }]; layout = { ...layout, showlegend: false, margin: { l: 48, r: 8, t: 8, b: 64 }, yaxis: { tickformat: "~s" }, xaxis: { tickangle: 0, tickfont: { size: 9 } } }; }
  else { data = Object.entries(c.series).map(([name, ys]: any, i) => ({ type: c.kind === "line" ? "scatter" : "bar", mode: "lines", name, x: c.x, y: ys, marker: { color: AGENT_COLORS[i] }, line: { color: AGENT_COLORS[i], width: 2 } })); layout = { ...layout, yaxis: { tickformat: "~s" }, barmode: "group" }; }
  return <div className="mt-2 rounded-xl border border-line bg-white p-1"><div className="px-2 pt-1 text-[11px] font-semibold text-muted">{c.title} ({cur})</div><Plot ariaLabel={c.title} height={c.kind === "waterfall" ? 250 : 210} data={data} layout={layout} testId="chat-chart" /></div>;
}

function Activity({ items }: { items: any[] }) {
  const [open, setOpen] = useState(false);
  if (!items?.length) return null;
  return (
    <div className="mt-1.5 rounded-lg border border-line bg-flo-50/70 text-[11px]">
      <button type="button" onClick={() => setOpen(!open)} className="flex w-full items-center justify-between px-2 py-1 font-semibold text-muted" aria-expanded={open}>
        <span className="inline-flex items-center gap-1"><Wrench className="h-3 w-3" />Agent activity ({items.length})</span><ChevronDown className={`h-3 w-3 transition ${open ? "rotate-180" : ""}`} />
      </button>
      {open && <ol className="space-y-0.5 px-2 pb-1.5">{items.map((a, i) => <li key={i}><code className="text-flo-800">{a.tool}</code> — {a.detail}</li>)}</ol>}
    </div>
  );
}

export function ChatPanel({ compact = false, conversationId, onConversation }: { compact?: boolean; conversationId?: string | null; onConversation?: (id: string) => void }) {
  const s = useApp();
  const nav = useNavigate();
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [files, setFiles] = useState<{ name: string; content: string }[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [cid, setCid] = useState<string | null>(conversationId ?? null);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const endRef = useRef<HTMLDivElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => { api<any>("/meta").then((m) => setSuggestions(m.suggestions)).catch(() => {}); }, []);
  useEffect(() => {
    setCid(conversationId ?? null);
    if (!conversationId) { setTurns([]); return; }
    api<any>(`/conversations/${conversationId}`).then((c) => setTurns(c.messages.map((m: any) => ({ role: m.role, content: m.content, payload: m.payload, activity: m.payload?.activity, attachments: m.payload?.attachments })))).catch(() => {});
  }, [conversationId]);
  useEffect(() => { endRef.current?.scrollIntoView({ block: "end" }); }, [turns]);

  const send = async (text: string) => {
    const msg = text.trim();
    if (!msg || busy) return;
    setBusy(true); setErr(null); setInput("");
    const atts = files; setFiles([]);
    setTurns((t) => [...t, { role: "user", content: msg, attachments: atts.map((a) => a.name) }, { role: "assistant", content: "", activity: [], streaming: true }]);
    const patch = (fn: (t: Turn) => Turn) => setTurns((ts) => { const c = [...ts]; c[c.length - 1] = fn(c[c.length - 1]); return c; });
    try {
      await chatStream({ message: msg, conversation_id: cid, currency: s.currency, dc: s.dc, attachments: atts }, {
        activity: (a) => patch((t) => ({ ...t, activity: [...(t.activity ?? []), a] })),
        delta: (d) => patch((t) => ({ ...t, content: t.content + d })),
        final: (p) => { patch((t) => ({ ...t, content: p.text, payload: p, streaming: false })); if (p.conversation_id && p.conversation_id !== cid) { setCid(p.conversation_id); onConversation?.(p.conversation_id); } },
      });
    } catch (e: any) { setErr(e.message); patch((t) => ({ ...t, streaming: false, content: t.content || "I could not answer that request." })); }
    finally { setBusy(false); }
  };

  const onFiles = async (fl: FileList | null) => {
    if (!fl) return;
    const out: { name: string; content: string }[] = [];
    for (const f of Array.from(fl).slice(0, 3)) {
      if (f.size > 200_000) { setErr(`${f.name} is larger than 200 KB`); continue; }
      out.push({ name: f.name, content: await f.text() });
    }
    setFiles((x) => [...x, ...out]);
  };

  const updateApproval = (ti: number, a: any) => setTurns((ts) => ts.map((t, i) => i === ti && t.payload ? { ...t, payload: { ...t.payload, approvals: t.payload.approvals.map((x: any) => (x.id === a.id ? a : x)) } } : t));

  return (
    <div className="flex h-full min-h-0 flex-col" data-testid="chat-panel">
      <div className={`flex-1 space-y-4 overflow-y-auto scroll-thin ${compact ? "p-3" : "p-5"}`} aria-live="polite">
        {turns.length === 0 && (
          <div className="fade-in flex flex-col items-center px-2 pt-2 text-center">
            <SherinAvatar size={compact ? "lg" : "xl"} />
            <h2 className="mt-3 font-display text-2xl font-semibold text-flo-900">Ask Sherin</h2>
            <p className="mt-1 max-w-md text-sm text-muted">{OPENING}</p>
            <div className="mt-4 grid w-full gap-1.5">
              {suggestions.slice(0, compact ? 5 : 10).map((q) => (
                <button key={q} type="button" onClick={() => send(q)} className="rounded-xl border border-line bg-white px-3 py-2 text-left text-[13px] text-flo-900 hover:border-flo-600 hover:bg-flo-50">
                  <Sparkles className="mr-1.5 inline h-3.5 w-3.5 text-gold" aria-hidden />{q}</button>
              ))}
            </div>
          </div>
        )}
        {turns.map((t, i) => t.role === "user" ? (
          <div key={i} className="flex justify-end"><div className="max-w-[85%] rounded-2xl rounded-br-md bg-flo-800 px-3.5 py-2 text-sm text-white">{t.content}
            {t.attachments?.length ? <div className="mt-1 text-[11px] text-flo-100">📎 {t.attachments.join(", ")}</div> : null}</div></div>
        ) : (
          <div key={i} className="flex gap-2.5" data-testid="assistant-turn">
            <SherinAvatar size="sm" />
            <div className="min-w-0 flex-1">
              <div className="rounded-2xl rounded-tl-md border border-line bg-white px-3.5 py-2.5 shadow-sm">
                {t.streaming && !t.content && <span className="inline-flex items-center gap-1.5 text-xs text-muted"><Loader2 className="h-3.5 w-3.5 animate-spin" />Sherin is checking the records…</span>}
                <Markdown text={t.content} />
                {t.payload?.charts?.map((c: any) => <ChatChart key={c.id} c={c} cur={t.payload.currency} />)}
                {t.payload?.diff && <DiffView diff={t.payload.diff} />}
                {t.payload?.run_id && <RunInline runId={t.payload.run_id} />}
                {t.payload?.approvals?.length > 0 && <div className="mt-2 space-y-2">{t.payload.approvals.slice(0, compact ? 2 : 6).map((a: any) => <ApprovalCard key={a.id} a={a} compact onChange={(x) => updateApproval(i, x)} />)}</div>}
                {t.payload && (
                  <div className="mt-2 flex flex-wrap items-center gap-1.5">
                    {t.payload.links?.map((l: any) => <button key={l.route} type="button" onClick={() => nav(l.route)} className="inline-flex items-center gap-1 rounded-full bg-flo-100 px-2.5 py-0.5 text-[11px] font-semibold text-flo-800 hover:bg-flo-200">{l.label}<ArrowUpRight className="h-3 w-3" /></button>)}
                    {t.payload.run_id && <Badge tone="green">run {t.payload.run_id}</Badge>}
                    <a href={reportUrl({ ...periodParams(s), format: "md" })} className="inline-flex items-center gap-1 rounded-full border border-line px-2.5 py-0.5 text-[11px] font-semibold text-muted hover:text-flo-800"><Download className="h-3 w-3" />Report</a>
                  </div>
                )}
                {t.payload?.sources?.length > 0 && <p className="mt-1.5 text-[10px] text-muted">Sources: {t.payload.sources.join(", ")} · {t.payload.period?.label} · {t.payload.currency}</p>}
              </div>
              <Activity items={t.activity ?? []} />
              {t.payload?.followups?.length > 0 && <div className="mt-1.5 flex flex-wrap gap-1">{t.payload.followups.map((f: string) => <button key={f} type="button" onClick={() => send(f)} className="rounded-full border border-line bg-white px-2.5 py-0.5 text-[11px] text-flo-800 hover:bg-flo-50">{f}</button>)}</div>}
            </div>
          </div>
        ))}
        <div ref={endRef} />
      </div>
      {err && <p role="alert" className="mx-3 mb-1 rounded-lg bg-red-light px-2 py-1 text-xs text-red">{err}</p>}
      <form className={`border-t border-line bg-white ${compact ? "p-2.5" : "p-4"}`} onSubmit={(e) => { e.preventDefault(); send(input); }}>
        {files.length > 0 && <div className="mb-1.5 flex flex-wrap gap-1">{files.map((f) => <span key={f.name} className="inline-flex items-center gap-1 rounded-full bg-flo-100 px-2 py-0.5 text-[11px] text-flo-800">📎 {f.name}<button type="button" aria-label={`Remove ${f.name}`} onClick={() => setFiles(files.filter((x) => x !== f))}><X className="h-3 w-3" /></button></span>)}</div>}
        <div className="flex items-end gap-2 rounded-2xl border border-line bg-flo-50/50 px-2 py-1.5 focus-within:border-flo-600">
          <input ref={fileRef} type="file" className="hidden" multiple accept=".py,.yml,.yaml,.log,.txt,.json,.bicep,.tf,.csv,.md" onChange={(e) => { onFiles(e.target.files); e.target.value = ""; }} data-testid="chat-file" />
          <button type="button" aria-label="Attach file" onClick={() => fileRef.current?.click()} className="rounded-full p-1.5 text-muted hover:bg-white hover:text-flo-800"><Paperclip className="h-4 w-4" /></button>
          <textarea aria-label="Message Sherin" value={input} onChange={(e) => setInput(e.target.value)} rows={1} placeholder="Ask about revenue, AI cost, savings, tokens, approvals…"
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(input); } }} className="max-h-32 min-h-[36px] flex-1 resize-none bg-transparent py-1.5 text-sm outline-none" />
          <button type="submit" disabled={busy || !input.trim()} aria-label="Send" className="rounded-full bg-flo-800 p-2 text-white disabled:opacity-40">{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}</button>
        </div>
      </form>
    </div>
  );
}
