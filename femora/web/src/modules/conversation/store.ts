import { useCallback } from "react";
import { usePersistent } from "../../lib/usePersistent";
import { uid } from "../../lib/storage";
import type { Conversation, Message, Mode } from "./types";

export function newConversation(mode: Mode = "talk"): Conversation {
  return { id: uid(), title: "New conversation", mode, messages: [], archived: false, updatedAt: Date.now() };
}

export function titleFrom(text: string) {
  const t = text.replace(/\s+/g, " ").trim();
  return t.length > 42 ? t.slice(0, 40).trimEnd() + "…" : t || "New conversation";
}

export function searchConversations(list: Conversation[], q: string) {
  const s = q.trim().toLowerCase();
  if (!s) return list;
  return list.filter((c) => c.title.toLowerCase().includes(s) || c.messages.some((m) => m.text.toLowerCase().includes(s)));
}

export function useConversations(profileId: string) {
  const [list, setList] = usePersistent<Conversation[]>(`conversations:${profileId}`, () => []);
  const upsert = useCallback((c: Conversation) => setList((l) => [c, ...l.filter((x) => x.id !== c.id)]), [setList]);
  const patch = useCallback((id: string, p: Partial<Conversation>) => setList((l) => l.map((c) => (c.id === id ? { ...c, ...p } : c))), [setList]);
  const addMessage = useCallback((id: string, m: Message) => setList((l) => {
    const c = l.find((x) => x.id === id);
    if (!c) return l;
    const next = { ...c, messages: [...c.messages, m], updatedAt: Date.now(), title: c.messages.length === 0 && m.role === "user" ? titleFrom(m.text) : c.title };
    return [next, ...l.filter((x) => x.id !== id)];
  }), [setList]);
  const remove = useCallback((id: string) => setList((l) => l.filter((c) => c.id !== id)), [setList]);
  return { list, upsert, patch, addMessage, remove };
}

export function exportConversation(c: Conversation) {
  const body = [`FEMORA Muse conversation export`, `Title: ${c.title}`, `Exported: ${new Date().toISOString()}`, "",
    ...c.messages.map((m) => `[${new Date(m.at).toLocaleString()}] ${m.role === "user" ? "You" : "Muse"}: ${m.text}`)].join("\n");
  const url = URL.createObjectURL(new Blob([body], { type: "text/plain" }));
  const a = document.createElement("a");
  a.href = url; a.download = `femora-${c.title.replace(/[^a-z0-9]+/gi, "-").toLowerCase()}.txt`; a.click();
  URL.revokeObjectURL(url);
}
