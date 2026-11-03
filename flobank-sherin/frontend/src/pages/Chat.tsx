import { useState } from "react";
import { MessageSquarePlus, Search, Trash2 } from "lucide-react";
import { ChatPanel } from "../components/ChatPanel";
import { Card, PageHeader } from "../components/ui";
import { api, useApi } from "../lib/api";

export default function Chat() {
  const [q, setQ] = useState("");
  const [cid, setCid] = useState<string | null>(null);
  const list = useApi<any[]>("/conversations", q ? { q } : undefined);
  return (
    <div>
      <PageHeader title="Sherin Copilot" subtitle="Ask about money first: revenue, cost, savings, tokens and approvals. Every answer links to the chart it came from." />
      <div className="grid gap-4 lg:grid-cols-[280px_1fr]">
        <Card className="flex h-[calc(100vh-220px)] flex-col p-3">
          <button type="button" onClick={() => setCid(null)} className="mb-2 inline-flex items-center justify-center gap-1.5 rounded-full bg-flo-800 px-3 py-1.5 text-sm font-semibold text-white"><MessageSquarePlus className="h-4 w-4" />New conversation</button>
          <label className="relative mb-2 block"><span className="sr-only">Search conversations</span>
            <Search className="absolute left-2.5 top-2 h-4 w-4 text-muted" /><input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search history" className="w-full rounded-full border border-line py-1.5 pl-8 pr-3 text-sm" /></label>
          <ul className="flex-1 space-y-1 overflow-y-auto scroll-thin" aria-label="Conversation history">
            {(list.data ?? []).map((c) => (
              <li key={c.id} className={`group flex items-center gap-1 rounded-xl px-2 py-1.5 text-sm ${cid === c.id ? "bg-flo-100" : "hover:bg-flo-50"}`}>
                <button type="button" className="min-w-0 flex-1 truncate text-left" onClick={() => setCid(c.id)} title={c.title}>{c.title}</button>
                <button type="button" aria-label={`Delete ${c.title}`} className="opacity-0 group-hover:opacity-100" onClick={async () => { await api(`/conversations/${c.id}`, { method: "DELETE" }); if (cid === c.id) setCid(null); list.reload(); }}><Trash2 className="h-3.5 w-3.5 text-muted" /></button>
              </li>))}
            {list.data?.length === 0 && <li className="px-2 text-xs text-muted">No conversations yet.</li>}
          </ul>
        </Card>
        <Card className="flex h-[calc(100vh-220px)] flex-col overflow-hidden"><ChatPanel conversationId={cid} onConversation={(id) => { setCid(id); list.reload(); }} /></Card>
      </div>
    </div>
  );
}
