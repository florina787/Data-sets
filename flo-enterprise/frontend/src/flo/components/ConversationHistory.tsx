import { useQuery } from "@tanstack/react-query";
import { MessageSquarePlus, Search, X } from "lucide-react";
import { useState } from "react";
import { Button, Input, Spinner, cn } from "@/components/ui";
import { api } from "@/lib/api";
import type { ConversationSummary } from "../types";

export function ConversationHistory({ open, onClose, activeId, onOpen, onNew }: {
  open: boolean; onClose: () => void; activeId: string | null; onOpen: (id: string) => void; onNew: () => void;
}) {
  const [q, setQ] = useState("");
  const list = useQuery({ queryKey: ["conversations", q], enabled: open,
    queryFn: () => api<{ conversations: ConversationSummary[] }>(`/api/conversations${q ? `?q=${encodeURIComponent(q)}` : ""}`) });
  if (!open) return null;
  return (
    <aside className="fixed inset-y-0 left-0 z-40 flex w-full max-w-sm flex-col border-r border-line bg-side shadow-2xl flo-slide-in" aria-label="Conversation history">
      <div className="flex items-center gap-2 border-b border-line px-4 py-3">
        <h2 className="text-sm font-semibold">Conversations</h2>
        <Button size="sm" variant="ghost" className="ml-auto" onClick={() => { onNew(); onClose(); }}><MessageSquarePlus className="h-4 w-4" />New</Button>
        <Button size="icon" variant="ghost" onClick={onClose} aria-label="Close history"><X className="h-4 w-4" /></Button>
      </div>
      <div className="relative p-3">
        <Search className="pointer-events-none absolute left-5 top-5 h-4 w-4 text-muted" aria-hidden />
        <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search your conversations…" aria-label="Search conversations" className="pl-8" />
      </div>
      <div className="flex-1 overflow-y-auto scroll-thin px-2 pb-4">
        {list.isLoading && <Spinner />}
        {list.data?.conversations.length === 0 && <p className="p-3 text-sm text-muted">No conversations yet.</p>}
        <ul className="space-y-1">
          {list.data?.conversations.map((c) => (
            <li key={c.id}>
              <button onClick={() => { onOpen(c.id); onClose(); }} aria-current={c.id === activeId}
                className={cn("w-full rounded-lg px-3 py-2 text-left hover:bg-card", c.id === activeId && "bg-card ring-1 ring-gold/40")}>
                <div className="truncate text-sm">{c.title}</div>
                <div className="text-[11px] text-muted">{new Date(c.updated_at + "Z").toLocaleString()} · {c.message_count} question(s){c.last_intent ? ` · ${c.last_intent.replace(/_/g, " ")}` : ""}</div>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </aside>
  );
}
