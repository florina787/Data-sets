import { useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { ArrowUp, Paperclip, Plus } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { AgentCursor, type Tone } from "@/components/art/AgentCursor";
import { AgentCard } from "@/components/Cards";
import { TrialMeter } from "@/components/career";
import { IntelPanel } from "@/components/Layout";
import { Button, Pill } from "@/components/ui";
import { api, stream } from "@/lib/api";
import { cn } from "@/lib/utils";

type Msg = { role: "user" | "assistant"; content: string; cards?: any[]; warnings?: string[]; approvals?: any[] };
const TONES: Tone[] = ["violet", "sky", "amber", "coral", "emerald", "rose"];

export default function Assistant() {
  const qc = useQueryClient();
  const meta = useQuery({ queryKey: ["chat-meta"], queryFn: () => api<{ limits: any; suggested_prompts: string[] }>("/api/chat/meta") });
  const [cid, setCid] = useState<string | null>(null);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [agents, setAgents] = useState<{ label: string; agent: string }[]>([]);
  const [conv, setConv] = useState<any>(null);
  const [llm, setLlm] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => end.current?.scrollIntoView({ behavior: "smooth" }), [msgs, agents]);

  async function send(text: string) {
    if (!text.trim() || busy) return;
    setError(null); setBusy(true); setInput(""); setAgents([]);
    let id = cid;
    try {
      if (!id || conv?.closed) { const c = await api<{ id: string }>("/api/chat/conversations", { method: "POST" }); id = c.id; setCid(id); setMsgs([]); }
      setMsgs((m) => [...m, { role: "user", content: text }, { role: "assistant", content: "", cards: [], warnings: [], approvals: [] }]);
      const patch = (f: (a: Msg) => Msg) => setMsgs((m) => [...m.slice(0, -1), f(m[m.length - 1])]);
      await stream(`/api/chat/conversations/${id}/messages`, { content: text }, (e) => {
        if (e.type === "agent" && !["supervisor", "governance"].includes(e.agent)) setAgents((a) => (a.some((x) => x.agent === e.agent) ? a : [...a, e]));
        if (e.type === "agent" && e.agent === "governance") setAgents((a) => [...a, e]);
        if (e.type === "token") patch((a) => ({ ...a, content: a.content + e.text }));
        if (e.type === "card") patch((a) => ({ ...a, cards: [...(a.cards ?? []), e.card] }));
        if (e.type === "warning") patch((a) => ({ ...a, warnings: [...(a.warnings ?? []), e.text] }));
        if (e.type === "approval") patch((a) => ({ ...a, approvals: [...(a.approvals ?? []), e] }));
        if (e.type === "done") { setConv(e.conversation); setLlm(e.llm); }
        if (e.type === "error") setError(e.message);
      });
    } catch (x: any) {
      setError(x?.message ?? String(x));
      setMsgs((m) => (m.at(-1)?.role === "assistant" && !m.at(-1)?.content ? m.slice(0, -1) : m));
    } finally { setBusy(false); qc.invalidateQueries({ queryKey: ["usage"] }); }
  }

  const empty = msgs.length === 0;
  return (
    <div className="flex gap-6">
      <div className="mx-auto flex min-h-[calc(100dvh-120px)] w-full max-w-3xl flex-col">
        {empty ? (
          <div className="relative flex flex-1 flex-col items-center justify-center pb-10 text-center">
            <p className="eyebrow">AI Career Assistant</p>
            <h1 className="display mt-2">What's your next move?</h1>
            <p className="muted mt-3 max-w-md text-sm">Ask in plain words. The supervisor routes your request to specialised agents and shows their work as they go.</p>
            {meta.data && (
              <p className="muted mt-4 text-[12px]">Each conversation: up to {meta.data.limits.max_messages} messages, {meta.data.limits.max_tokens.toLocaleString()} tokens, {meta.data.limits.max_minutes} minutes and {meta.data.limits.max_tool_calls} tool calls.</p>
            )}
            <TrialMeter feature="ai_chat" className="mt-3" />
            <div className="mt-8 grid w-full gap-2 sm:grid-cols-2">
              {meta.data?.suggested_prompts.map((p) => (
                <button key={p} onClick={() => send(p)} className="card p-4 text-left text-[13px] transition hover:-translate-y-0.5 hover:shadow-lift">{p}</button>
              ))}
            </div>
          </div>
        ) : (
          <div className="flex-1 space-y-6 pt-4">
            {msgs.map((m, i) => (
              <motion.div key={i} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className={cn(m.role === "user" && "flex justify-end")}>
                {m.role === "user" ? <p className="max-w-[80%] rounded-3xl bg-ink px-5 py-3 text-[14px] text-white dark:bg-white dark:text-ink">{m.content}</p> : (
                  <div className="space-y-3">
                    {(m.cards ?? []).map((c, j) => <AgentCard key={j} card={c} />)}
                    {m.content && <div className="whitespace-pre-wrap text-[14.5px] leading-relaxed">{m.content}</div>}
                    {(m.warnings ?? []).map((w) => <p key={w} className="rounded-xl bg-amber/10 px-3 py-2 text-[12px] text-amber-800 dark:text-amber-300">{w}</p>)}
                    {(m.approvals ?? []).map((a) => <p key={a.approval_id} className="text-[12.5px]">Waiting for your approval: {a.summary} — <a className="text-violet" href="/app/governance">review</a></p>)}
                  </div>
                )}
              </motion.div>
            ))}
            {busy && (
              <div className="relative h-14" aria-live="polite">
                {agents.map((a, i) => (
                  <div key={a.agent} className="absolute top-0" style={{ left: `${2 + (i % 4) * 24}%` }}>
                    <AgentCursor label={a.label} tone={TONES[i % TONES.length]} className="relative" />
                  </div>
                ))}
                {!agents.length && <p className="muted text-sm">Supervisor is planning…</p>}
              </div>
            )}
            {error && <p role="alert" className="rounded-2xl bg-coral/10 px-4 py-3 text-sm text-red-700">{error}</p>}
            <div ref={end} />
          </div>
        )}
        <form onSubmit={(e) => { e.preventDefault(); send(input); }} className="sticky bottom-4 mt-4">
          <div className="card flex items-end gap-2 p-2">
            <Button type="button" variant="ghost" size="icon" aria-label="New conversation" onClick={() => { setCid(null); setMsgs([]); setConv(null); }}><Plus className="h-4 w-4" /></Button>
            <a href="/app/resume" aria-label="Upload resume" className="grid h-9 w-9 place-items-center rounded-full hover:bg-black/5"><Paperclip className="h-4 w-4" /></a>
            <textarea value={input} onChange={(e) => setInput(e.target.value)} rows={1} placeholder="Find Senior AI Engineer jobs in Toronto paying over CAD 150,000…"
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(input); } }}
              className="max-h-40 flex-1 resize-none bg-transparent px-2 py-2 text-[14px] outline-none" aria-label="Message" />
            <Button size="icon" variant="violet" aria-label="Send" loading={busy}><ArrowUp className="h-4 w-4" /></Button>
          </div>
          {conv && <p className="muted mt-1.5 text-center text-[11px]">{conv.messages}/{conv.limits.max_messages} messages · {conv.tokens.toLocaleString()} tokens{conv.closed && " · conversation limit reached — start a new one"}</p>}
        </form>
      </div>
      <IntelPanel>
        <div className="card p-5">
          <p className="text-[13px] font-semibold">Agents in this run</p>
          {agents.length ? <ul className="mt-2 space-y-1 text-[12.5px]">{agents.map((a) => <li key={a.agent} className="flex items-center gap-2"><span className="h-1.5 w-1.5 rounded-full bg-violet" />{a.label}</li>)}</ul>
            : <p className="muted mt-2 text-[12px]">Idle</p>}
          {llm?.model && <p className="muted mt-3 text-[11.5px]">Qwen <Pill>{llm.model}</Pill> TTFT {llm.ttft_ms} ms · {llm.tokens_per_second ?? "–"} tok/s</p>}
        </div>
      </IntelPanel>
    </div>
  );
}
