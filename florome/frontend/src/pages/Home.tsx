import { Activity, ArrowUp, Coins, MessagesSquare, RotateCcw, Scale, ShieldCheck } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { AnswerCard, Dot, useAssistantChat } from "../components/Assistant";
import { DomeMark } from "../components/Logo";
import { cx } from "../components/ui";
import { api, type AssistantSources } from "../lib/api";
import { useAsync } from "../lib/useAsync";

const GROUP_STYLE: Record<string, { icon: ReactNode; ring: string; tint: string }> = {
  Operations: { icon: <Activity className="h-4 w-4" />, ring: "ring-dome-200", tint: "bg-dome-50 text-dome-700" },
  "Security · Shield": { icon: <ShieldCheck className="h-4 w-4" />, ring: "ring-amber-200", tint: "bg-amber-50 text-amber-700" },
  "Customers · Conversation Copilot": { icon: <MessagesSquare className="h-4 w-4" />, ring: "ring-emerald-200", tint: "bg-emerald-50 text-emerald-700" },
  Money: { icon: <Coins className="h-4 w-4" />, ring: "ring-sky-200", tint: "bg-sky-50 text-sky-700" },
  Governance: { icon: <Scale className="h-4 w-4" />, ring: "ring-rose-200", tint: "bg-rose-50 text-rose-700" },
};

function SourcePill({ label, ok, detail }: { label: string; ok: boolean | null; detail: string }) {
  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-dome-100 bg-white px-3 py-1 text-xs text-ink-soft" title={detail}>
      <span className={cx("h-2 w-2 rounded-full", ok === null ? "bg-ink-mute" : ok ? "bg-ok" : "bg-warn")} />
      {label}: <b className="font-medium text-ink">{detail}</b>
    </span>
  );
}

export default function Home() {
  const { cfg, turns, busy, ask, reset } = useAssistantChat("home", {});
  const sources = useAsync(() => api<AssistantSources>("/assistant/sources"));
  const [text, setText] = useState("");
  const end = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    end.current?.scrollIntoView?.({ block: "end", behavior: "smooth" });
  }, [turns, busy]);
  const send = (q: string) => {
    setText("");
    void ask(q);
  };
  const cop = sources.data?.conversation_copilot;
  const started = turns.length > 0;

  const composer = (
    <form onSubmit={(e) => { e.preventDefault(); send(text); }}
      className="flex items-end gap-2 rounded-2xl border border-dome-100 bg-white p-2 shadow-tile focus-within:border-dome-300">
      <textarea ref={input} value={text} rows={1} maxLength={500} aria-label="Ask Florome"
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(text); } }}
        placeholder="Ask anything about your enterprise…"
        className="max-h-40 min-h-[44px] flex-1 resize-none bg-transparent px-3 py-2.5 text-[15px] outline-none" />
      <button type="button" onClick={() => send("Summarise this page")} disabled={busy}
        className="rounded-xl border border-dome-100 px-3 py-2.5 text-xs text-ink-soft hover:bg-dome-50 disabled:opacity-40">Brief</button>
      <button type="submit" disabled={busy || !text.trim()} aria-label="Send"
        className="rounded-xl bg-ink p-2.5 text-white transition hover:bg-ink/85 disabled:opacity-30"><ArrowUp className="h-5 w-5" /></button>
    </form>
  );

  return (
    <div className="grid-canvas min-h-[calc(100vh-110px)]">
      {!started ? (
        <div className="mx-auto max-w-[1100px] px-6 pb-16 pt-14">
          <div className="text-center">
            <div className="mx-auto w-fit"><DomeMark size={56} /></div>
            <h1 className="mt-5 font-display text-4xl font-semibold tracking-tight text-ink md:text-5xl">
              What do you want to know<br />about <span className="text-dome-500">your enterprise?</span>
            </h1>
            <p className="mx-auto mt-3 max-w-2xl text-sm text-ink-soft">
              One sentence back, with a picture and the evidence one click away. Answers come only from recorded data: Florome's own records and,
              for customer conversations, the Conversation Intelligence Copilot.
            </p>
          </div>
          <div className="mx-auto mt-8 max-w-3xl">{composer}</div>
          <div className="mt-4 flex flex-wrap justify-center gap-2">
            <SourcePill label="Florome records" ok={sources.data ? true : null} detail={sources.data ? "live" : "checking…"} />
            <SourcePill label="Conversation Copilot" ok={cop ? cop.reachable : null}
              detail={!cop ? "checking…" : cop.reachable ? `connected (${cop.status})` : cop.configured ? "not running" : "not configured"} />
            <span className="inline-flex items-center rounded-full border border-dome-100 bg-white px-3 py-1 text-xs text-ink-mute">Rule-based · no AI model</span>
          </div>

          <div className="mt-12 grid gap-4 md:grid-cols-2 xl:grid-cols-5">
            {(cfg?.groups ?? []).map((g) => {
              const st = GROUP_STYLE[g.title] ?? GROUP_STYLE.Operations;
              return (
                <section key={g.title} className={cx("rounded-2xl bg-white/90 p-4 shadow-tile ring-1 backdrop-blur", st.ring)} aria-label={g.title}>
                  <div className={cx("inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-[11px] font-semibold", st.tint)}>{st.icon}{g.title}</div>
                  <div className="mt-3 space-y-1.5">
                    {g.questions.map((q) => (
                      <button key={q} onClick={() => send(q)} className="block w-full rounded-lg px-2.5 py-2 text-left text-[13px] text-ink hover:bg-canvas">{q}</button>
                    ))}
                  </div>
                </section>
              );
            })}
            {!cfg && <p className="text-sm text-ink-mute">Loading questions…</p>}
          </div>
          <p className="mt-8 text-center text-xs text-ink-mute">
            Prefer dashboards? See the <Link to="/overview" className="text-dome-600 underline">Overview</Link>. The same helper is on every page as <b>Ask Florome</b>.
          </p>
        </div>
      ) : (
        <div className="mx-auto flex max-w-[860px] flex-col px-4 pb-6 pt-6">
          <div className="mb-4 flex items-center gap-3">
            <DomeMark size={28} />
            <div className="flex-1 text-sm font-semibold">Florome Copilot</div>
            <button onClick={reset} className="inline-flex items-center gap-1.5 rounded-lg border border-dome-100 bg-white px-3 py-1.5 text-xs hover:bg-dome-50">
              <RotateCcw className="h-3.5 w-3.5" />New conversation
            </button>
          </div>
          <div className="flex-1 space-y-4" aria-live="polite">
            {turns.map((t, i) =>
              t.role === "user" ? (
                <div key={i} className="ml-auto w-fit max-w-[80%] rounded-2xl rounded-br-md bg-ink px-4 py-2.5 text-[15px] text-white">{t.text}</div>
              ) : t.role === "error" ? (
                <div key={i} role="alert" className="rounded-xl border border-bad/30 bg-bad/5 p-3 text-sm text-bad">
                  {t.text} <button onClick={() => void ask(t.retry)} className="ml-1 underline">Retry</button>
                </div>
              ) : (
                <div key={i} className="max-w-[92%] text-[15px]"><AnswerCard a={t.answer} onAsk={send} latest={i === turns.length - 1} /></div>
              ),
            )}
            {busy && <div className="flex gap-1 px-1" aria-label="Answering"><Dot /><Dot d="150ms" /><Dot d="300ms" /></div>}
            <div ref={end} className="h-24" aria-hidden="true" />{/* keeps the last follow-ups clear of the pinned composer */}
          </div>
          <div className="sticky bottom-4 mt-2">{composer}</div>
        </div>
      )}
    </div>
  );
}
