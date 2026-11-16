import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Archive, Download, Mic, Pencil, Plus, Search, Send, Trash2, ArchiveRestore, BookOpen } from "lucide-react";
import { useApp } from "../../lib/app-state";
import { uid } from "../../lib/storage";
import { Markdown } from "../../lib/markdown";
import { Badge, Button, Notice, inputCls } from "../../components/ui";
import { STAGE_LABEL } from "../../data/examples/profiles";
import { foodFacts } from "../nutrition/summary";
import { journeyFacts, type Period } from "../journey/logic";
import { load } from "../../lib/storage";
import { MODES, type Action, type Message, type Mode } from "./types";
import { reply, currentProvider } from "./router";
import { exportConversation, newConversation, searchConversations, useConversations } from "./store";
import { SOURCES, sourceById } from "./sources";

const STARTERS = ["Make me laugh", "Tell me an inspiring story", "I've been feeling lonely lately", "I'm sleeping badly and my periods are changing", "How much protein did I eat this week?", "Suggest meals from my cuisine", "Help me prepare for a doctor's appointment"];

export function CopilotPage() {
  const app = useApp();
  const nav = useNavigate();
  const { list, upsert, patch, addMessage, remove } = useConversations(app.profile.id);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [showArchived, setShowArchived] = useState(false);
  const [draft, setDraft] = useState("");
  const [mode, setMode] = useState<Mode>("talk");
  const [typing, setTyping] = useState<string | null>(null);
  const [openSource, setOpenSource] = useState<string | null>(null);
  const [handledMemory, setHandledMemory] = useState<string[]>([]);
  const [listening, setListening] = useState(false);
  const [brief, setBrief] = useState(false);
  const scroller = useRef<HTMLDivElement>(null);

  const active = list.find((c) => c.id === activeId) ?? null;
  const shown = useMemo(() => searchConversations(list.filter((c) => c.archived === showArchived), q), [list, q, showArchived]);

  useEffect(() => { setActiveId(null); }, [app.profile.id]);
  useEffect(() => { const el = scroller.current; if (el) el.scrollTop = el.scrollHeight; }, [active?.messages.length, typing]);

  async function send(text: string) {
    const t = text.trim();
    if (!t || typing !== null) return;
    let conv = active;
    if (!conv) { conv = newConversation(mode); upsert(conv); setActiveId(conv.id); }
    const userMsg: Message = { id: uid(), role: "user", text: t, mode, at: Date.now() };
    addMessage(conv.id, userMsg);
    setDraft("");
    setTyping("");
    const r = await reply({
      text: t, mode, brief, history: [...conv.messages, userMsg],
      profile: { name: app.profile.name, stage: app.profile.stage ? STAGE_LABEL[app.profile.stage] : undefined, cuisine: app.profile.cuisine, diet: app.profile.diet, livesAlone: app.profile.livesAlone },
      memory: app.memoryEnabled ? app.memory.map((m) => m.text) : [],
      food: foodFacts(app.profile.id),
      journey: journeyFacts(load<Period[]>(`periods:${app.profile.id}`, []), app.symptoms),
    });
    setTyping(null);
    addMessage(conv.id, { id: uid(), role: "assistant", text: r.text, mode, at: Date.now(), sources: r.sources, actions: r.actions, followUps: r.followUps, memory: r.memory, safety: r.safety, provider: r.provider });
  }

  function runAction(a: Action) {
    if (a.kind === "open") nav(a.payload);
    if (a.kind === "log-symptom") app.logSymptom(a.payload, 2, "copilot");
    if (a.kind === "joy") { const last = [...(active?.messages ?? [])].reverse().find((m) => m.role === "user"); app.addJoy("Moments", last?.text ?? "A good moment"); }
  }

  function voice() {
    const SR = (window as unknown as { SpeechRecognition?: new () => any; webkitSpeechRecognition?: new () => any }).SpeechRecognition
      ?? (window as unknown as { webkitSpeechRecognition?: new () => any }).webkitSpeechRecognition;
    if (!SR) { alert("Voice input isn't supported in this browser. Try Chrome or Edge."); return; }
    const rec = new SR();
    rec.lang = "en-US"; rec.interimResults = false;
    rec.onresult = (e: any) => setDraft((d) => (d ? d + " " : "") + e.results[0][0].transcript);
    rec.onend = () => setListening(false);
    setListening(true); rec.start();
  }

  return (
    <div className="grid h-[calc(100dvh-8.5rem)] min-h-[520px] gap-4 lg:grid-cols-[280px_1fr]">
      {/* Conversation list */}
      <aside className="hidden flex-col gap-3 overflow-hidden rounded-f bg-surface p-4 shadow-f lg:flex" aria-label="Conversations">
        <Button variant="primary" onClick={() => { const c = newConversation(mode); upsert(c); setActiveId(c.id); }}><Plus size={16} /> New conversation</Button>
        <label className="relative"><span className="sr-only">Search conversations</span>
          <Search size={15} className="absolute left-3 top-3 text-muted" />
          <input className={inputCls + " pl-9"} placeholder="Search conversations" value={q} onChange={(e) => setQ(e.target.value)} />
        </label>
        <div className="flex gap-1 text-sm">
          <button className={`rounded-full px-3 py-1 ${!showArchived ? "bg-surface-2 font-medium" : "text-muted"}`} onClick={() => setShowArchived(false)}>Active</button>
          <button className={`rounded-full px-3 py-1 ${showArchived ? "bg-surface-2 font-medium" : "text-muted"}`} onClick={() => setShowArchived(true)}>Archived</button>
        </div>
        <ul className="-mx-1 flex-1 space-y-1 overflow-y-auto">
          {shown.length === 0 && <li className="px-2 py-4 text-sm text-muted">{q ? "No matches." : showArchived ? "Nothing archived." : "Your conversations will appear here."}</li>}
          {shown.map((c) => (
            <li key={c.id} className={`group rounded-f-sm px-2 py-2 ${c.id === activeId ? "bg-surface-2" : "hover:bg-surface-2"}`}>
              <button className="w-full text-left" onClick={() => { setActiveId(c.id); setMode(c.mode); }}>
                <div className="truncate text-sm font-medium">{c.title}</div>
                <div className="text-xs text-muted">{c.messages.length} messages · {new Date(c.updatedAt).toLocaleDateString()}</div>
              </button>
              <div className="mt-1 hidden gap-1 group-hover:flex group-focus-within:flex">
                <IconBtn label="Rename" onClick={() => { const t = prompt("Rename conversation", c.title); if (t?.trim()) patch(c.id, { title: t.trim() }); }}><Pencil size={14} /></IconBtn>
                <IconBtn label={c.archived ? "Unarchive" : "Archive"} onClick={() => { patch(c.id, { archived: !c.archived }); if (c.id === activeId) setActiveId(null); }}>{c.archived ? <ArchiveRestore size={14} /> : <Archive size={14} />}</IconBtn>
                <IconBtn label="Export" onClick={() => exportConversation(c)}><Download size={14} /></IconBtn>
                <IconBtn label="Delete" onClick={() => { if (confirm("Delete this conversation permanently?")) { remove(c.id); if (c.id === activeId) setActiveId(null); } }}><Trash2 size={14} /></IconBtn>
              </div>
            </li>
          ))}
        </ul>
      </aside>

      {/* Chat */}
      <section className="flex min-h-0 flex-col overflow-hidden rounded-f bg-surface shadow-f" aria-label="Muse conversation">
        <header className="flex flex-wrap items-center gap-2 border-b border-line px-5 py-3">
          <h1 className="font-display text-xl">Muse</h1>
          <Badge tone={currentProvider().live ? "good" : "neutral"}>{currentProvider().live ? "Model connected" : "Offline mode"}</Badge>
          <span className="text-xs text-muted">{currentProvider().label}</span>
          <label className="ml-auto flex items-center gap-2 text-sm"><input type="checkbox" checked={brief} onChange={(e) => setBrief(e.target.checked)} /> Brief answers</label>
          <div className="flex lg:hidden"><Button size="sm" onClick={() => { const c = newConversation(mode); upsert(c); setActiveId(c.id); }}><Plus size={14} /> New</Button></div>
        </header>
        <nav aria-label="Copilot mode" className="flex gap-2 overflow-x-auto border-b border-line px-5 py-2">
          {MODES.map((m) => (
            <button key={m.id} title={m.blurb} aria-pressed={mode === m.id} onClick={() => { setMode(m.id); if (active) patch(active.id, { mode: m.id }); }}
              className={`shrink-0 rounded-full px-3 py-1.5 text-sm ${mode === m.id ? "bg-primary text-primary-ink" : "bg-surface-2 text-ink hover:bg-line"}`}>{m.label}</button>
          ))}
        </nav>

        <div ref={scroller} className="flex-1 space-y-4 overflow-y-auto px-5 py-5" aria-live="polite">
          {!active || active.messages.length === 0 ? (
            <div className="mx-auto max-w-xl py-8 text-center">
              <div className="font-display text-3xl">Hi {app.profile.name}, how are you, really?</div>
              <p className="mt-2 text-muted">{MODES.find((m) => m.id === mode)!.blurb}. Talk about anything, from sleep and cycles to family, work and the things that make you happy.</p>
              <div className="mt-6 flex flex-wrap justify-center gap-2">
                {STARTERS.map((s) => <button key={s} onClick={() => send(s)} className="rounded-full border border-line px-3 py-2 text-sm hover:bg-surface-2">{s}</button>)}
              </div>
            </div>
          ) : active.messages.map((m) => (
            <div key={m.id} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[85%] rounded-f px-4 py-3 ${m.role === "user" ? "bg-primary text-primary-ink" : m.safety ? "border-2 border-danger bg-surface" : "bg-surface-2"}`}>
                {m.role === "assistant" && m.safety && <div className="mb-1"><Badge tone="danger">{m.safety === "crisis" ? "Safety response" : "Seek medical care"}</Badge></div>}
                {m.role === "user" ? <p className="whitespace-pre-wrap text-[15px]">{m.text}</p> : <Markdown text={m.text} onCite={setOpenSource} />}
                {m.role === "assistant" && (
                  <div className="mt-2 space-y-2">
                    {m.sources?.length ? <div className="flex flex-wrap gap-1 text-xs text-muted"><BookOpen size={13} /> Sources: {m.sources.map((s) => <button key={s} className="underline" onClick={() => setOpenSource(s)}>{s} {sourceById(s)?.publisher.split(",")[0]}</button>)}</div> : null}
                    {m.actions?.length ? <div className="flex flex-wrap gap-2">{m.actions.map((a) => <Button key={a.label} size="sm" variant="ghost" className="border border-line" onClick={() => runAction(a)}>{a.label}</Button>)}</div> : null}
                    {m.memory && !handledMemory.includes(m.id) && (
                      <div className="rounded-f-sm border border-line bg-surface p-2 text-sm">
                        Remember this? <b>“{m.memory}”</b>{!app.memoryEnabled && <span className="text-muted"> (memory is off, so approving will turn it on)</span>}
                        <div className="mt-1 flex gap-2"><Button size="sm" variant="primary" onClick={() => { app.setMemoryEnabled(true); app.addMemory(m.memory!); setHandledMemory((h) => [...h, m.id]); }}>Remember</Button><Button size="sm" onClick={() => setHandledMemory((h) => [...h, m.id])}>Not now</Button></div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          ))}
          {typing !== null && <div className="flex justify-start"><div className="max-w-[85%] rounded-f bg-surface-2 px-4 py-3">{typing ? <Markdown text={typing} /> : <span className="inline-flex items-center gap-2 text-muted"><span className="h-2 w-2 animate-pulse rounded-full bg-accent" /> Muse is thinking…</span>}</div></div>}
          {active && !typing && (() => { const last = active.messages[active.messages.length - 1]; return last?.role === "assistant" && last.followUps?.length ? (
            <div className="flex flex-wrap gap-2">{last.followUps.map((f) => <button key={f} onClick={() => send(f)} className="rounded-full border border-line px-3 py-1.5 text-sm hover:bg-surface-2">{f}</button>)}</div>) : null; })()}
        </div>

        {openSource && (() => { const s = sourceById(openSource); return s ? (
          <div className="border-t border-line bg-surface-2 px-5 py-3 text-sm">
            <b>{s.id}</b> {s.title}. {s.publisher}, {s.year}. <a className="text-primary underline" href={s.url} target="_blank" rel="noreferrer">Open source</a>
            <button className="ml-3 text-muted underline" onClick={() => setOpenSource(null)}>Close</button>
          </div>) : null; })()}

        <form className="border-t border-line p-4" onSubmit={(e) => { e.preventDefault(); send(draft); }}>
          <div className="flex items-end gap-2">
            <label className="flex-1"><span className="sr-only">Message Muse</span>
              <textarea rows={2} className={inputCls + " resize-none"} placeholder="Write as much as you like…" value={draft}
                onChange={(e) => setDraft(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(draft); } }} />
            </label>
            <Button aria-label="Voice input" onClick={voice} className={listening ? "!bg-warm text-white" : ""}><Mic size={18} /></Button>
            <Button type="submit" variant="primary" aria-label="Send" disabled={!draft.trim() || typing !== null}><Send size={18} /></Button>
          </div>
          <p className="mt-2 text-xs text-muted">Enter to send · Shift+Enter for a new line. Muse is an AI companion, not a clinician. {currentProvider().live ? "Replies come from your connected model; numbers and safety rules come from Muse’s own tools." : `Offline mode uses Muse’s reviewed response library and cites ${SOURCES.length} reference sources.`} In an emergency, call your local emergency number.</p>
        </form>
      </section>
      {app.memoryEnabled && <span className="sr-only">Memory is on</span>}
      <noscript><Notice>JavaScript is required.</Notice></noscript>
    </div>
  );
}

function IconBtn({ label, onClick, children }: { label: string; onClick: () => void; children: React.ReactNode }) {
  return <button type="button" aria-label={label} title={label} onClick={onClick} className="rounded-md p-1.5 text-muted hover:bg-line hover:text-ink">{children}</button>;
}
