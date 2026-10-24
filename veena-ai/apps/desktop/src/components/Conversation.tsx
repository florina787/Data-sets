import { AnimatePresence, motion } from "framer-motion";
import { AudioLines, BookOpen, CircleStop, Eye, FileText, MessageSquareQuote, Monitor, ShieldAlert } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { Citation, Message } from "../services/api";
import { type LiveAnswer, useApp } from "../stores/app";
import { CatMark } from "./CatMark";
import { CopyButton, Markdown } from "./Markdown";
import { Badge, Button, cn } from "./ui";

const STYLE_LABEL: Record<string, string> = {
  quick: "Quick",
  detailed: "Detailed",
  deep_dive: "Deep dive",
  code: "Code",
  architecture: "Architecture",
  tutorial: "Tutorial",
  interview: "Practice answer",
  meeting_summary: "Meeting summary",
};

function time(iso: string) {
  return new Date(iso.endsWith("Z") || iso.includes("+") ? iso : iso + "Z").toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function Citations({ items }: { items: Citation[] }) {
  const [open, setOpen] = useState<number | null>(null);
  if (!items.length) return null;
  return (
    <div className="mt-3 space-y-1.5">
      <div className="flex flex-wrap gap-1.5">
        {items.map((c) => (
          <button
            key={c.n}
            type="button"
            onClick={() => setOpen(open === c.n ? null : c.n)}
            className={cn("inline-flex items-center gap-1 rounded-lg border px-2 py-1 text-xs", open === c.n ? "border-caramel bg-cream text-bark" : "border-cream bg-ivory text-mocha hover:border-sand")}
          >
            <FileText size={12} />[{c.n}] {c.filename}
            {c.page ? `, p.${c.page}` : ""}
            <span className="text-caramel">· {c.score.toFixed(2)}</span>
          </button>
        ))}
      </div>
      {open !== null && (
        <blockquote className="rounded-lg border border-cream bg-warm p-3 text-xs leading-relaxed text-mocha">{items.find((c) => c.n === open)?.snippet}…</blockquote>
      )}
    </div>
  );
}

function GovernanceNotes({ meta }: { meta: Record<string, unknown> }) {
  const gov = meta.governance as { flags?: { kind: string; detail: string }[]; notes?: string[] } | undefined;
  const notes = [...((meta.notes as string[]) ?? []), ...(gov?.flags?.map((f) => f.detail) ?? [])];
  const unique = [...new Set(notes)];
  if (!unique.length) return null;
  return (
    <ul className="mt-3 space-y-1">
      {unique.map((n) => (
        <li key={n} className="flex items-start gap-1.5 text-xs text-caramel">
          <ShieldAlert size={13} className="mt-0.5 shrink-0" />
          {n}
        </li>
      ))}
    </ul>
  );
}

function AssistantBubble({ m }: { m: Message }) {
  const stats = m.meta.stats as { first_token_ms?: number; tokens_per_second?: number } | undefined;
  return (
    <div className="flex gap-3">
      <CatMark size={30} className="mt-0.5" />
      <div className="min-w-0 flex-1">
        <div className="mb-1 flex flex-wrap items-center gap-2 text-xs text-caramel">
          <span className="font-semibold text-bark">VEENA</span>
          {m.answer_style && <Badge>{STYLE_LABEL[m.answer_style] ?? m.answer_style}</Badge>}
          {typeof m.meta.agent === "string" && <Badge tone="outline">{m.meta.agent.replace("_", " ")}</Badge>}
          {m.model && <span>{m.model}</span>}
          {stats?.first_token_ms != null && <span>· first token {Math.round(stats.first_token_ms)} ms</span>}
          {stats?.tokens_per_second ? <span>· {stats.tokens_per_second.toFixed(1)} tok/s</span> : null}
          {m.meta.cancelled === true && <Badge tone="outline">stopped</Badge>}
          <span className="ml-auto">{time(m.created_at)}</span>
        </div>
        <div className="rounded-2xl rounded-tl-md border border-cream bg-white px-4 py-3 shadow-[var(--shadow-soft)]">
          <Markdown text={m.content} />
          <Citations items={m.citations} />
          <GovernanceNotes meta={m.meta} />
          <div className="mt-2 flex justify-end">
            <span className="rounded-md bg-espresso">
              <CopyButton text={m.content} label="Copy answer" />
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

function UserBubble({ m }: { m: Message }) {
  const src = m.meta.source as string | undefined;
  const Icon = src === "speech" ? AudioLines : src === "screen" ? Monitor : null;
  return (
    <div className="flex justify-end">
      <div className="max-w-[80%]">
        <div className="mb-1 flex items-center justify-end gap-2 text-xs text-caramel">
          {Icon && <Icon size={12} />}
          {m.meta.has_image === true && (
            <span className="inline-flex items-center gap-1">
              <Eye size={12} /> with screenshot
            </span>
          )}
          {m.intent && <Badge tone="outline">{m.intent.replace("_", " ")}</Badge>}
          <span>{time(m.created_at)}</span>
        </div>
        <div className="whitespace-pre-wrap rounded-2xl rounded-tr-md bg-bark px-4 py-2.5 text-sm text-white">{m.content}</div>
      </div>
    </div>
  );
}

function TranscriptLine({ m }: { m: Message }) {
  return (
    <div className="flex items-start gap-2 pl-1 text-sm text-mocha">
      <MessageSquareQuote size={14} className="mt-1 shrink-0 text-sand" />
      <span className="text-[11px] text-sand tabular-nums">{time(m.created_at)}</span>
      <span>
        {m.meta.source === "system" && <span className="mr-1 text-xs text-caramel">[system audio]</span>}
        {m.content}
      </span>
    </div>
  );
}

export function LiveAnswerView({ live, onStop }: { live: LiveAnswer; onStop: () => void }) {
  const busy = !live.done && !live.error;
  return (
    <div className="flex gap-3" aria-live="polite">
      <CatMark size={30} mood={busy ? "thinking" : "still"} className="mt-0.5" />
      <div className="min-w-0 flex-1">
        <div className="mb-1 flex flex-wrap items-center gap-2 text-xs text-caramel">
          <span className="font-semibold text-bark">VEENA</span>
          {live.meta && <Badge>{STYLE_LABEL[live.meta.style] ?? live.meta.style}</Badge>}
          {live.meta && <Badge tone="outline">{live.meta.agent.replace("_", " ")}</Badge>}
          {live.meta && <span>{live.meta.model}</span>}
          {live.meta?.vision && (
            <span className="inline-flex items-center gap-1">
              <Eye size={12} /> vision
            </span>
          )}
          {live.meta?.citations.length ? (
            <span className="inline-flex items-center gap-1">
              <BookOpen size={12} /> {live.meta.citations.length} sources
            </span>
          ) : null}
        </div>
        <div className="rounded-2xl rounded-tl-md border border-cream bg-white px-4 py-3 shadow-[var(--shadow-soft)]">
          {live.error ? (
            <p className="text-sm text-bark">{live.error}</p>
          ) : live.text ? (
            <Markdown text={live.text} streaming={busy} />
          ) : (
            <p className="text-sm text-caramel">{live.meta ? "Generating…" : "Preparing context…"}</p>
          )}
          {live.meta && <Citations items={live.meta.citations} />}
          {live.meta?.notes.length ? <GovernanceNotes meta={{ notes: live.meta.notes }} /> : null}
          {busy && (
            <div className="mt-2 flex justify-end">
              <Button size="sm" variant="ghost" onClick={onStop} aria-label="Stop generating">
                <CircleStop size={14} /> Stop
              </Button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export function MessageList({ empty }: { empty?: React.ReactNode }) {
  const { messages, live, partials, cancel } = useApp();
  const end = useRef<HTMLDivElement>(null);
  const partialList = Object.entries(partials);
  useEffect(() => {
    end.current?.scrollIntoView({ block: "end" });
  }, [messages.length, live?.text, partialList.length]);

  if (!messages.length && !live && !partialList.length) return <>{empty}</>;
  // The live answer replaces its persisted copy until the stream finishes.
  return (
    <div className="space-y-5">
      {messages
        .filter((m) => !(live?.done && m.id === live.done.message_id))
        .map((m) =>
        m.role === "assistant" ? <AssistantBubble key={m.id} m={m} /> : m.role === "user" ? <UserBubble key={m.id} m={m} /> : m.role === "transcript" ? <TranscriptLine key={m.id} m={m} /> : null,
      )}
      <AnimatePresence>
        {partialList.map(([k, p]) => (
          <motion.div key={k} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="flex items-start gap-2 pl-1 text-sm italic text-sand">
            <AudioLines size={14} className="mt-1 shrink-0" />
            {p.text}
          </motion.div>
        ))}
      </AnimatePresence>
      {live && <LiveAnswerView live={live} onStop={() => void cancel()} />}
      <div ref={end} />
    </div>
  );
}
