import { Download, MessageCircle, RotateCcw, Send, Sparkles, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { api, post, type AssistantAnswer, type AssistantPage, type AssistantVisual } from "../lib/api";
import { cx } from "./ui";

const PAGE_BY_PATH: Record<string, string> = {
  "/": "overview", "/topology": "topology", "/rca": "rca", "/actions": "actions", "/integrations": "integrations",
  "/sources": "sources", "/governance": "governance", "/finops": "finops", "/shield": "shield",
};
type Turn = { role: "user"; text: string } | { role: "assistant"; answer: AssistantAnswer } | { role: "error"; text: string; retry: string };

export function pageFor(pathname: string): string | null {
  return PAGE_BY_PATH[pathname] ?? null;
}

export function AssistantDock() {
  const loc = useLocation();
  const page = pageFor(loc.pathname);
  const [open, setOpen] = useState(false);
  const [cfg, setCfg] = useState<AssistantPage | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [conv, setConv] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const end = useRef<HTMLDivElement>(null);
  const context = useMemo(() => {
    const sp = new URLSearchParams(loc.search);
    const c: Record<string, string> = {};
    if (sp.get("incident")) c.incident_id = sp.get("incident")!;
    if (sp.get("hypothesis")) c.hypothesis_id = sp.get("hypothesis")!;
    return c;
  }, [loc.search]);

  // A new page starts a new conversation: the assistant is specialised per page.
  useEffect(() => {
    setTurns([]);
    setConv(null);
    setCfg(null);
    if (page) api<AssistantPage>(`/assistant/pages/${page}`).then(setCfg).catch(() => setCfg(null));
  }, [page]);
  useEffect(() => {
    if (open) input.current?.focus();
  }, [open]);
  useEffect(() => {
    end.current?.scrollIntoView?.({ block: "end" });
  }, [turns, busy]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  if (!page) return null;

  const ask = async (q: string) => {
    const question = q.trim();
    if (!question || busy) return;
    setText("");
    setTurns((t) => [...t.filter((x) => x.role !== "error"), { role: "user", text: question }]);
    setBusy(true);
    try {
      const a = await post<AssistantAnswer>("/assistant/ask", { page, question, conversation_id: conv, context });
      setConv(a.conversation_id);
      setTurns((t) => [...t, { role: "assistant", answer: a }]);
    } catch (e) {
      setTurns((t) => [...t, { role: "error", text: e instanceof Error ? e.message : String(e), retry: question }]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      {!open && (
        <button onClick={() => setOpen(true)} aria-expanded={open} aria-controls="florome-assistant"
          className="fixed bottom-6 right-6 z-40 inline-flex items-center gap-2 rounded-full bg-ink px-5 py-3 text-sm font-medium text-white shadow-[0_18px_40px_-12px_rgba(20,22,74,0.6)] ring-1 ring-white/10 transition hover:-translate-y-0.5 motion-reduce:transition-none">
          <Sparkles className="h-4 w-4 text-dome-200" /> Ask Florome
        </button>
      )}
      {open && (
        <aside id="florome-assistant" role="dialog" aria-label={`Florome assistant for ${cfg?.title ?? page}`}
          className="fixed inset-y-0 right-0 z-50 flex w-full max-w-[440px] flex-col border-l border-dome-100 bg-white text-ink shadow-2xl sm:inset-y-3 sm:right-3 sm:rounded-2xl sm:border">
          <header className="flex items-center gap-3 border-b border-dome-100 px-4 py-3">
            <MessageCircle className="h-5 w-5 text-dome-500" />
            <div className="flex-1">
              <div className="text-sm font-semibold">Ask Florome · {cfg?.title ?? page}</div>
              <div className="text-[11px] text-ink-mute">Rule-based · answers only from Florome data · no AI model</div>
            </div>
            <button aria-label="New conversation" title="New conversation" onClick={() => { setTurns([]); setConv(null); }} className="rounded-md p-1.5 hover:bg-dome-50"><RotateCcw className="h-4 w-4" /></button>
            <button aria-label="Close assistant" onClick={() => setOpen(false)} className="rounded-md p-1.5 hover:bg-dome-50"><X className="h-4 w-4" /></button>
          </header>
          <div className="flex-1 space-y-4 overflow-y-auto px-4 py-4" aria-live="polite">
            {turns.length === 0 && (
              <div>
                <p className="text-sm text-ink-soft">Start with one of these, or type your own question.</p>
                <div className="mt-3 grid gap-2">
                  {cfg?.starters.map((s) => (
                    <button key={s} onClick={() => void ask(s)} className="rounded-xl border border-dome-100 bg-canvas px-3 py-2.5 text-left text-sm hover:border-dome-300 hover:bg-dome-50">{s}</button>
                  ))}
                  {!cfg && <p className="text-xs text-ink-mute">Loading questions…</p>}
                </div>
              </div>
            )}
            {turns.map((t, i) =>
              t.role === "user" ? (
                <div key={i} className="ml-10 rounded-2xl rounded-br-md bg-ink px-3.5 py-2 text-sm text-white">{t.text}</div>
              ) : t.role === "error" ? (
                <div key={i} role="alert" className="rounded-xl border border-bad/30 bg-bad/5 p-3 text-sm text-bad">
                  {t.text} <button onClick={() => void ask(t.retry)} className="ml-1 underline">Retry</button>
                </div>
              ) : (
                <AnswerCard key={i} a={t.answer} onAsk={(q) => void ask(q)} latest={i === turns.length - 1} />
              ),
            )}
            {busy && <div className="flex gap-1 px-1" aria-label="Answering"><Dot /><Dot d="150ms" /><Dot d="300ms" /></div>}
            <div ref={end} />
          </div>
          <form onSubmit={(e) => { e.preventDefault(); void ask(text); }} className="flex items-center gap-2 border-t border-dome-100 p-3">
            <input ref={input} value={text} onChange={(e) => setText(e.target.value)} maxLength={500} aria-label="Your question"
              placeholder="Ask about this page…" className="flex-1 rounded-xl border border-dome-100 bg-canvas px-3 py-2 text-sm outline-none focus:border-dome-400" />
            <button type="button" onClick={() => void ask("Summarise this page")} disabled={busy} title="Summarise this page"
              className="rounded-xl border border-dome-100 px-2.5 py-2 text-xs text-ink-soft hover:bg-dome-50 disabled:opacity-40">Brief</button>
            <button type="submit" disabled={busy || !text.trim()} aria-label="Send" className="rounded-xl bg-dome-500 p-2 text-white disabled:opacity-40"><Send className="h-4 w-4" /></button>
          </form>
        </aside>
      )}
    </>
  );
}

function Dot({ d = "0ms" }: { d?: string }) {
  return <span className="h-2 w-2 animate-bounce rounded-full bg-dome-300 motion-reduce:animate-none" style={{ animationDelay: d }} />;
}

function AnswerCard({ a, onAsk, latest }: { a: AssistantAnswer; onAsk: (q: string) => void; latest: boolean }) {
  return (
    <div className="rounded-2xl rounded-bl-md border border-dome-100 bg-canvas/60 p-3.5" data-testid="assistant-answer">
      <p className="text-[14px] font-medium leading-snug">{a.statement}</p>
      {a.bullets.length > 0 && (
        <ul className="mt-2 space-y-1 text-[12.5px] text-ink-soft">{a.bullets.map((b, i) => <li key={i} className="flex gap-2"><span className="text-dome-400">•</span><span>{b}</span></li>)}</ul>
      )}
      {a.visual && <div className="mt-3"><Visual v={a.visual} /></div>}
      {a.evidence.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {a.evidence.map((e, i) => (
            <Link key={i} to={e.href} className="rounded-md bg-white px-2 py-1 text-[11px] font-medium text-dome-600 ring-1 ring-dome-100 hover:ring-dome-300">↗ {e.label}</Link>
          ))}
        </div>
      )}
      {a.input_flags.length > 0 && <p className="mt-2 text-[11px] text-warn">Your message contained instruction-like text; it was treated as a plain question and changed nothing.</p>}
      {latest && a.follow_ups.length > 0 && (
        <div className="mt-3 grid grid-cols-2 gap-1.5">
          {a.follow_ups.map((f) => (
            <button key={f} onClick={() => onAsk(f)} className="rounded-lg bg-white px-2.5 py-1.5 text-left text-[11.5px] text-ink ring-1 ring-dome-100 hover:bg-dome-50 hover:ring-dome-300">{f}</button>
          ))}
        </div>
      )}
    </div>
  );
}

const TONE: Record<string, string> = { root: "bg-bad/15 text-bad", symptom: "bg-warn/15 text-warn", impacted: "bg-dome-50 text-dome-700",
  business: "bg-ok/15 text-ok", weak: "bg-warn/10 text-warn", neutral: "bg-white text-ink ring-1 ring-dome-100" };

export function Visual({ v }: { v: AssistantVisual }) {
  if (v.type === "kpis")
    return (
      <div className="grid grid-cols-3 gap-2">
        {v.items.map((k) => <div key={k.label} className="rounded-lg bg-white p-2 ring-1 ring-dome-100"><div className="font-display text-xl font-semibold tabular-nums">{k.value}</div><div className="text-[10.5px] text-ink-mute">{k.label}</div></div>)}
      </div>
    );
  if (v.type === "bars") {
    const max = Math.max(...v.items.map((x) => x.value), 1);
    return (
      <figure aria-label={`Bar chart, ${v.unit}`} className="space-y-1.5">
        {v.items.map((x) => (
          <div key={x.label} className="text-[11.5px]">
            <div className="flex justify-between gap-2"><span className="truncate">{x.label}</span><span className="tabular-nums text-ink-soft">{x.value.toLocaleString()}</span></div>
            <div className="mt-0.5 h-2 rounded-full bg-dome-50"><div className="h-2 rounded-full bg-dome-500" style={{ width: `${(x.value / max) * 100}%` }} /></div>
          </div>
        ))}
        <figcaption className="text-[10px] text-ink-mute">{v.unit}</figcaption>
      </figure>
    );
  }
  if (v.type === "chain")
    return (
      <div className="flex flex-wrap items-center gap-1 text-[11.5px]">
        {v.items.map((x, i) => (
          <span key={i} className="flex items-center gap-1">
            {i > 0 && <span className="text-ink-mute">→</span>}
            <span className={cx("rounded-md px-1.5 py-0.5", TONE[x.tone] ?? TONE.neutral)} title={x.note}>{x.label}</span>
          </span>
        ))}
      </div>
    );
  if (v.type === "table")
    return (
      <div className="overflow-x-auto rounded-lg bg-white ring-1 ring-dome-100">
        <table className="w-full text-left text-[11.5px]">
          <thead className="text-[10px] uppercase tracking-wider text-ink-mute"><tr>{v.columns.map((c) => <th key={c} className="px-2 py-1.5">{c}</th>)}</tr></thead>
          <tbody>{v.rows.slice(0, 10).map((r, i) => <tr key={i} className="border-t border-dome-50">{r.map((c, j) => <td key={j} className="px-2 py-1.5">{String(c)}</td>)}</tr>)}</tbody>
        </table>
      </div>
    );
  if (v.type === "timeline")
    return (
      <ol className="space-y-1.5 border-l border-dome-100 pl-3 text-[11.5px]">
        {v.items.map((x, i) => (
          <li key={i} className="relative"><span className={cx("absolute -left-[17px] top-1 h-2 w-2 rounded-full", x.tone === "bad" ? "bg-bad" : "bg-dome-500")} />
            <span className="font-mono text-ink-mute">{x.at.slice(11, 16)}</span> <b>{x.label}</b> <span className="text-ink-soft">{x.text}</span></li>
        ))}
      </ol>
    );
  if (v.type === "report") {
    const download = () => {
      const url = URL.createObjectURL(new Blob([v.markdown], { type: "text/markdown" }));
      const el = document.createElement("a");
      el.href = url;
      el.download = "florome-brief.md";
      el.click();
      URL.revokeObjectURL(url);
    };
    return (
      <div className="rounded-lg bg-white p-2.5 ring-1 ring-dome-100">
        <pre className="max-h-40 overflow-auto whitespace-pre-wrap font-mono text-[10.5px] text-ink-soft">{v.markdown}</pre>
        <button onClick={download} className="mt-2 inline-flex items-center gap-1.5 rounded-md bg-ink px-2.5 py-1 text-[11px] text-white"><Download className="h-3.5 w-3.5" />Download brief (.md)</button>
      </div>
    );
  }
  return null;
}
