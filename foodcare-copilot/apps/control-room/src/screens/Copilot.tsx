import { Fragment, ReactNode, useEffect, useRef, useState } from "react";
import { api, post } from "../api";
import { Provenance } from "../components/ui";
import { useApp } from "../context";
import { useBlob } from "../hooks";

type Source = { id: string; kind: string; label: string; ref: string; detail?: string };
type Answer = {
  conversation_id: string; question: string; answer: string; sources: Source[]; answered: boolean;
  tool_calls: { tool: string; args: Record<string, unknown> }[]; intents: string[]; entities: Record<string, unknown>;
  mode: string; provenance: string; notice: string | null; follow_ups: string[]; follow_up?: boolean;
  attachments?: { type: string; batch_id: string; potato_no: number }[];
};
type Summary = { id: string; title: string; updated_at: string; message_count: number };
type Hit = { message_id: number; conversation_id: string; title: string; snippet: string; created_at: string };
type Turn = { question: string; answer?: Answer; error?: string };

const OPEN_EVENT = "copilot:ask";

/** Opens the copilot drawer and asks a question (from any screen). */
export function openCopilot(question?: string) {
  window.dispatchEvent(new CustomEvent(OPEN_EVENT, { detail: question ?? null }));
}

export function AskButton({ question, label }: { question: string; label: string }) {
  return (
    <button className="btn-green" onClick={() => openCopilot(question)} title={`Asks: “${question}”`}>
      <span aria-hidden>✦</span> {label}
    </button>
  );
}

/** Minimal, safe renderer: **bold**, "- " bullets, paragraphs and [S#] citation chips. */
function Rich({ text, sources, onCite }: { text: string; sources: Source[]; onCite: (id: string) => void }) {
  const inline = (line: string, key: string): ReactNode[] =>
    line.split(/(\*\*[^*]+\*\*|\[S\d+\])/g).map((part, i) => {
      if (part.startsWith("**") && part.endsWith("**")) return <strong key={`${key}-${i}`}>{part.slice(2, -2)}</strong>;
      const m = part.match(/^\[(S\d+)\]$/);
      if (m) {
        const s = sources.find((x) => x.id === m[1]);
        return (
          <button key={`${key}-${i}`} onClick={() => onCite(m[1])} title={s ? `${s.label} · ${s.ref}` : "unknown source"}
            className="mx-0.5 rounded bg-navy-100 px-1 align-baseline font-mono text-[10px] font-semibold text-navy-800 hover:bg-navy-600 hover:text-white">
            {m[1]}
          </button>
        );
      }
      return <Fragment key={`${key}-${i}`}>{part}</Fragment>;
    });
  return (
    <div className="space-y-2 text-sm leading-relaxed">
      {text.split(/\n\n+/).map((para, pi) => {
        const lines = para.split("\n");
        const bullets = lines.filter((l) => l.startsWith("- "));
        const head = lines.filter((l) => !l.startsWith("- "));
        return (
          <div key={pi}>
            {head.map((l, li) => <p key={li}>{inline(l, `${pi}-${li}`)}</p>)}
            {bullets.length > 0 && <ul className="mt-1 list-disc space-y-0.5 pl-5">{bullets.map((b, bi) => <li key={bi}>{inline(b.slice(2), `${pi}-b${bi}`)}</li>)}</ul>}
          </div>
        );
      })}
    </div>
  );
}

function PotatoAttachment({ batchId, no }: { batchId: string; no: number }) {
  const url = useBlob(`/api/inspections/${batchId}/potatoes/${no}/image`);
  return url ? <img src={url} alt={`Potato #${no} from inspection ${batchId}`} className="mt-2 max-h-48 rounded-lg border border-surface-line" /> : null;
}

function AnswerView({ a, onAsk }: { a: Answer; onAsk: (q: string) => void }) {
  const [focus, setFocus] = useState<string | null>(null);
  return (
    <div className="rounded-xl border border-cream-300 bg-white p-3">
      <div className="mb-2 flex flex-wrap items-center gap-2 text-xs">
        <span className="font-semibold text-navy-800">Copilot</span>
        <Provenance kind={a.provenance} />
        <span className="text-navy-600">{a.mode === "live" ? "Written by the local model from the cited data" : "Deterministic answer from read-only queries"}</span>
      </div>
      {a.notice && <p className="mb-2 rounded bg-amber-100 px-2 py-1 text-xs text-amber-700">{a.notice}</p>}
      <Rich text={a.answer} sources={a.sources} onCite={setFocus} />
      {a.attachments?.filter((x) => x.type === "potato").map((x) => <PotatoAttachment key={`${x.batch_id}-${x.potato_no}`} batchId={x.batch_id} no={x.potato_no} />)}
      {a.sources.length > 0 && (
        <div className="mt-3 border-t border-cream-200 pt-2">
          <div className="label mb-1">Sources</div>
          <ul className="space-y-0.5 text-xs">
            {a.sources.map((s) => (
              <li key={s.id} className={`rounded px-1 ${focus === s.id ? "bg-navy-100" : ""}`}>
                <span className="font-mono font-semibold">[{s.id}]</span> {s.label} <span className="font-mono text-navy-600">{s.ref}</span>{s.detail && <span className="text-navy-600"> · {s.detail}</span>}
              </li>
            ))}
          </ul>
        </div>
      )}
      <details className="mt-2 text-xs text-navy-600">
        <summary className="cursor-pointer">How this was answered</summary>
        <div className="mt-1 space-y-0.5">
          <div>Intents: {a.intents.join(", ") || "none recognised"}</div>
          <div>Entities: {JSON.stringify(a.entities)}</div>
          <div>Read-only tools called: {a.tool_calls.map((t) => `${t.tool}(${Object.entries(t.args).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(", ")})`).join("; ") || "none"}</div>
        </div>
      </details>
      {a.follow_ups.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {a.follow_ups.map((f) => <button key={f} onClick={() => onAsk(f)} className="rounded-full border border-cream-300 px-2 py-0.5 text-xs hover:bg-cream-200">{f}</button>)}
        </div>
      )}
    </div>
  );
}

export function Conversation({ pending, onConsumed, compact = false, resume, onSaved }: {
  pending?: string | null; onConsumed?: () => void; compact?: boolean;
  resume?: { id: string | null; nonce: number }; onSaved?: (conversationId: string) => void;
}) {
  const { user, system } = useApp();
  const [turns, setTurns] = useState<Turn[]>([]);
  const [conversation, setConversation] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [requestId, setRequestId] = useState<string | null>(null);
  const [mode, setMode] = useState("demo");
  const [examples, setExamples] = useState<string[]>([]);
  const end = useRef<HTMLDivElement>(null);
  const liveOk = !!system?.live_mode?.available;

  useEffect(() => { api("/api/copilot/examples").then((d) => setExamples(d.examples)).catch(() => undefined); }, []);
  useEffect(() => { end.current?.scrollIntoView({ block: "end" }); }, [turns]);

  // Resume a saved conversation (or start a new one when id is null).
  useEffect(() => {
    if (!resume) return;
    setConversation(resume.id);
    if (!resume.id) { setTurns([]); return; }
    api(`/api/copilot/conversations/${resume.id}`).then((d) => {
      const restored: Turn[] = [];
      for (const m of d.messages as { role: string; content: string; answer: Answer | null }[]) {
        if (m.role === "user") restored.push({ question: m.content });
        else if (restored.length) restored[restored.length - 1].answer = m.answer ?? undefined;
      }
      setTurns(restored);
    }).catch((e) => setTurns([{ question: "(could not load conversation)", error: (e as Error).message }]));
  }, [resume?.id, resume?.nonce]);

  const ask = async (question: string) => {
    if (!question.trim() || busy || !user) return;
    setBusy(true);
    setInput("");
    setTurns((t) => [...t, { question }]);
    const rid = `REQ-${Math.random().toString(36).slice(2, 12)}`;
    setRequestId(mode === "live" ? rid : null);
    try {
      const a: Answer = await post("/api/copilot/ask", { question, conversation_id: conversation, mode, request_id: rid });
      setConversation(a.conversation_id);
      onSaved?.(a.conversation_id);
      setTurns((t) => t.map((x, i) => (i === t.length - 1 ? { ...x, answer: a } : x)));
    } catch (e) {
      setTurns((t) => t.map((x, i) => (i === t.length - 1 ? { ...x, error: (e as Error).message } : x)));
    } finally {
      setBusy(false);
      setRequestId(null);
    }
  };

  const stop = () => { if (requestId) post(`/api/copilot/cancel/${requestId}`).catch(() => undefined); };

  useEffect(() => {
    if (pending && user) {
      ask(pending);
      onConsumed?.();
    }
  }, [pending, user]);

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className={`min-h-0 flex-1 space-y-3 overflow-y-auto ${compact ? "p-3" : "py-2"}`} aria-live="polite">
        {!user && <p className="rounded bg-amber-100 p-2 text-sm text-amber-700">Sign in with any demo account (the viewer works) to ask the copilot.</p>}
        {turns.length === 0 && user && (
          <div className="text-sm text-navy-700">
            <p>I answer read-only questions about FoodCare's sales and promotions, inventory, product compliance, software delivery, incidents and policies. Every figure has a citation. I don't guess, and I can't take actions.</p>
            <div className="mt-2 flex flex-wrap gap-1">
              {examples.map((e) => <button key={e} onClick={() => ask(e)} className="rounded-full border border-cream-300 bg-white px-2 py-1 text-xs hover:bg-cream-200">{e}</button>)}
            </div>
          </div>
        )}
        {turns.map((t, i) => (
          <div key={i} className="space-y-2">
            <div className="ml-auto max-w-[85%] rounded-2xl rounded-br-md bg-royal-600 px-3 py-2 text-sm text-white shadow-glow">{t.question}</div>
            {t.answer ? <AnswerView a={t.answer} onAsk={ask} /> : t.error ? <p role="alert" className="text-sm text-brick-700">{t.error}</p> : <p className="text-sm text-navy-600">Looking it up…</p>}
          </div>
        ))}
        <div ref={end} />
      </div>
      <form className={`flex flex-wrap items-center gap-2 border-t border-cream-300 ${compact ? "p-3" : "pt-3"}`} onSubmit={(e) => { e.preventDefault(); ask(input); }}>
        <label htmlFor={compact ? "copilot-q-drawer" : "copilot-q"} className="sr-only">Ask the copilot</label>
        <input id={compact ? "copilot-q-drawer" : "copilot-q"} className="min-w-0 flex-1 rounded-lg border border-cream-300 px-3 py-2 text-sm" placeholder="Ask about sales, stock, allergens, releases…" value={input} onChange={(e) => setInput(e.target.value)} disabled={!user || busy} maxLength={500} />
        {busy && requestId
          ? <button type="button" className="btn-ghost" onClick={stop} title="Stop the local model">Stop</button>
          : <button className="btn-primary" disabled={!user || busy || !input.trim()}>{busy ? "…" : "Ask"}</button>}
        <label className="flex items-center gap-1 text-xs text-navy-700" title={liveOk ? `The local model (${system?.live_mode?.model}) writes the answer from the same cited data` : system?.live_mode?.reason}>
          <input type="checkbox" checked={mode === "live"} onChange={(e) => setMode(e.target.checked ? "live" : "demo")} /> LIVE {liveOk ? "" : "(not configured)"}
        </label>
      </form>
    </div>
  );
}

export function CopilotDrawer() {
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState<string | null>(null);
  useEffect(() => {
    const handler = (e: Event) => {
      setOpen(true);
      const q = (e as CustomEvent).detail as string | null;
      if (q) setPending(q);
    };
    window.addEventListener(OPEN_EVENT, handler);
    return () => window.removeEventListener(OPEN_EVENT, handler);
  }, []);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  return (
    <aside aria-label="Ask Copilot" aria-hidden={!open}
      className={`fixed inset-y-0 right-0 z-40 flex w-full max-w-xl flex-col border-l border-cream-300 bg-cream-50 shadow-2xl ${open ? "" : "hidden"}`}>
      <div className="flex items-center justify-between bg-navy-900 px-4 py-3 text-cream-50">
        <div><div className="font-semibold">Ask Copilot</div><div className="text-xs text-cream-200">Read-only · cites every figure · synthetic data</div></div>
        <button className="btn border border-cream-300/40 text-cream-50 hover:bg-navy-700" onClick={() => setOpen(false)}>Close</button>
      </div>
      <div className="min-h-0 flex-1"><Conversation compact pending={pending} onConsumed={() => setPending(null)} /></div>
    </aside>
  );
}

function History({ active, refresh, onOpen, onNew }: { active: string | null; refresh: number; onOpen: (id: string) => void; onNew: () => void }) {
  const { user } = useApp();
  const [items, setItems] = useState<Summary[]>([]);
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<Hit[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = () => { if (user) api("/api/copilot/conversations").then((d) => setItems(d.conversations)).catch((e) => setError((e as Error).message)); };
  useEffect(load, [user, refresh]);
  const search = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) { setHits(null); return; }
    try { setHits((await api(`/api/copilot/search?q=${encodeURIComponent(query.trim())}`)).results); } catch (err) { setError((err as Error).message); }
  };
  const remove = async (id: string) => {
    if (!window.confirm("Delete this conversation? This cannot be undone.")) return;
    await api(`/api/copilot/conversations/${id}`, { method: "DELETE" }).catch((e) => setError((e as Error).message));
    if (id === active) onNew();
    load();
  };
  return (
    <aside className="flex min-h-0 w-full flex-col rounded-xl border border-cream-300 bg-white p-3 md:w-72" aria-label="Conversation history">
      <div className="mb-2 flex items-center justify-between">
        <div className="label">History</div>
        <button className="btn-ghost text-xs" onClick={onNew}>New conversation</button>
      </div>
      <form onSubmit={search} className="mb-2 flex gap-1">
        <label htmlFor="history-q" className="sr-only">Search earlier questions</label>
        <input id="history-q" className="min-w-0 flex-1 rounded border border-cream-300 px-2 py-1 text-xs" placeholder="Search earlier questions" value={query} onChange={(e) => { setQuery(e.target.value); if (!e.target.value) setHits(null); }} maxLength={200} />
        <button className="btn-ghost text-xs">Search</button>
      </form>
      {error && <p role="alert" className="mb-1 text-xs text-brick-700">{error}</p>}
      <ul className="min-h-0 flex-1 space-y-1 overflow-y-auto text-xs">
        {hits !== null && hits.length === 0 && <li className="text-navy-600">No earlier question matches.</li>}
        {hits?.map((h) => (
          <li key={h.message_id}>
            <button className="w-full rounded px-2 py-1 text-left hover:bg-cream-200" onClick={() => onOpen(h.conversation_id)}>
              <div className="truncate font-medium text-navy-900">{h.title}</div>
              <div className="text-navy-600">{h.snippet}</div>
            </button>
          </li>
        ))}
        {hits === null && items.length === 0 && <li className="text-navy-600">No saved conversations yet.</li>}
        {hits === null && items.map((c) => (
          <li key={c.id} className={`group flex items-start gap-1 rounded ${c.id === active ? "bg-navy-100" : "hover:bg-cream-200"}`}>
            <button className="min-w-0 flex-1 px-2 py-1 text-left" onClick={() => onOpen(c.id)} aria-current={c.id === active}>
              <div className="truncate font-medium text-navy-900">{c.title}</div>
              <div className="text-navy-600">{new Date(c.updated_at).toLocaleString()} · {c.message_count / 2} question(s)</div>
            </button>
            <button className="px-1 py-1 text-navy-600 hover:text-brick-700" onClick={() => remove(c.id)} aria-label={`Delete conversation: ${c.title}`} title="Delete">✕</button>
          </li>
        ))}
      </ul>
    </aside>
  );
}

export default function CopilotPage() {
  const [resume, setResume] = useState<{ id: string | null; nonce: number }>({ id: null, nonce: 0 });
  const [active, setActive] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);
  const open = (id: string | null) => { setActive(id); setResume((r) => ({ id, nonce: r.nonce + 1 })); };
  return (
    <div className="flex h-[calc(100vh-200px)] min-h-[520px] flex-col">
      <h1 className="text-2xl font-semibold">Ask Copilot</h1>
      <p className="text-sm text-navy-600">Questions go to read-only tools over FoodCare's synthetic enterprise data, the live demo systems, delivery records and policy documents. Answers cite their sources and say plainly when the data cannot answer. Conversations are saved so you can search, resume or delete them.</p>
      <div className="mt-3 flex min-h-0 flex-1 flex-col gap-3 md:flex-row">
        <History active={active} refresh={refresh} onOpen={open} onNew={() => open(null)} />
        <div className="min-h-0 flex-1"><Conversation resume={resume} onSaved={(id) => { setActive(id); setRefresh((n) => n + 1); }} /></div>
      </div>
    </div>
  );
}
