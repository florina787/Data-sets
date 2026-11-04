import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { History, MessageSquarePlus } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Button, ErrorState, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { useApp } from "@/lib/app";
import { ConversationHistory } from "@/flo/components/ConversationHistory";
import { FloConversation } from "@/flo/components/FloConversation";
import { FloMessageComposer, type ComposerHandle } from "@/flo/components/FloMessageComposer";
import { FloWelcome } from "@/flo/components/FloWelcome";
import { IntelligenceWorkspace } from "@/flo/components/IntelligenceWorkspace";
import { PersonaSelector } from "@/flo/components/PersonaSelector";
import type { MessageContext, PersonaCatalogue } from "@/flo/types";
import { useConversation } from "@/flo/useConversation";

const personaKey = (u?: string) => `flo.persona.${u ?? "anon"}`;
const readPersona = (u?: string) => {
  try {
    return localStorage.getItem(personaKey(u));
  } catch {
    return null;
  }
};

export default function FloHome() {
  const { me, lang, askCtx, askOpen, closeAsk } = useApp();
  const qc = useQueryClient();
  const cat = useQuery({ queryKey: ["personas"], queryFn: () => api<PersonaCatalogue>("/api/personas") });
  const recent = useQuery({ queryKey: ["conversations", ""], queryFn: () => api<{ recent_questions: string[] }>("/api/conversations") });
  const [personaId, setPersonaId] = useState<string | null>(readPersona(me?.user_id));
  const persona = cat.data?.personas.find((p) => p.id === (personaId ?? cat.data?.default));
  const pid = persona?.id ?? cat.data?.default ?? "ceo";
  const conv = useConversation(pid, lang);
  const [history, setHistory] = useState(false);
  const composer = useRef<ComposerHandle>(null);
  const welcomeComposer = useRef<ComposerHandle>(null);
  const patchPersona = useMutation({ mutationFn: (p: string) => api(`/api/conversations/${conv.conversationId}`, { method: "PATCH", json: { persona: p } }) });

  const choosePersona = (id: string) => {
    setPersonaId(id);
    try {
      localStorage.setItem(personaKey(me?.user_id), id);
    } catch { /* storage unavailable */ }
    if (conv.conversationId) patchPersona.mutate(id);
  };
  const send = useCallback((q: string, c?: MessageContext) => {
    conv.send(q, c).then(() => qc.invalidateQueries({ queryKey: ["conversations"] }));
  }, [conv, qc]);

  // "Explain with FLO" from any enterprise dashboard lands here as a new question with its chart context
  useEffect(() => {
    if (askOpen && (askCtx.chart_id || askCtx.question)) {
      const q = askCtx.chart_id ? `Explain the "${askCtx.title}" chart and what drives it.` : askCtx.question!;
      closeAsk();
      send(q, { ...(askCtx.chart_id ? { chart_id: askCtx.chart_id } : {}), ...(askCtx.client_id ? { client_id: askCtx.client_id } : {}) });
    }
  }, [askOpen, askCtx, closeAsk, send]);

  const turn = conv.turns[conv.selected];
  const started = conv.turns.length > 0;
  if (cat.error) return <div className="p-6"><ErrorState error={cat.error} /></div>;
  if (!cat.data) return <Spinner label="Preparing FLO" />;
  return (
    <div className="flex h-full min-h-0 flex-col">
      <ConversationHistory open={history} onClose={() => setHistory(false)} activeId={conv.conversationId}
        onOpen={async (id) => { const p = await conv.load(id); if (p) setPersonaId(p); }} onNew={conv.reset} />
      {!started ? (
        <div className="min-h-0 flex-1 overflow-y-auto scroll-thin">
          <FloWelcome catalogue={cat.data} persona={persona} onPersona={choosePersona} onSend={(q) => send(q)} recent={recent.data?.recent_questions ?? []}
            composerRef={welcomeComposer} onHistory={() => setHistory(true)} firstName={me?.display_name.split(" ")[0]} />
        </div>
      ) : (
        <div className="grid min-h-0 flex-1 grid-cols-1 overflow-y-auto pb-28 lg:grid-cols-[minmax(360px,0.9fr)_minmax(0,1.7fr)] lg:overflow-hidden lg:pb-0">
          <div className="flex min-h-0 flex-col border-line lg:border-r">
            <div className="flex items-center gap-2 border-b border-line px-3 py-2">
              <Button size="sm" variant="ghost" onClick={() => setHistory(true)} aria-label="Conversation history"><History className="h-4 w-4" /></Button>
              <div className="min-w-0 flex-1"><PersonaSelector personas={cat.data.personas} value={pid} onChange={choosePersona} compact /></div>
              <Button size="sm" variant="ghost" onClick={conv.reset} aria-label="New conversation"><MessageSquarePlus className="h-4 w-4" /></Button>
            </div>
            <div className="min-h-0 flex-1 p-4 lg:overflow-y-auto lg:scroll-thin">
              <FloConversation turns={conv.turns} selected={conv.selected} onSelect={conv.setSelected} onFollowup={(q) => send(q)} />
            </div>
            <div className="border-t border-line bg-bg/95 p-3 backdrop-blur max-lg:fixed max-lg:inset-x-0 max-lg:bottom-0 max-lg:z-30">
              <FloMessageComposer ref={composer} onSend={(q) => send(q)} onCancel={conv.cancel} busy={conv.busy} personaLabel={persona?.label}
                placeholder="Ask a follow-up — e.g. “Break this down by product” or “What if rates rise 200 bps?”" />
            </div>
          </div>
          <section className="min-h-0 bg-side/30 p-4 md:p-6 lg:overflow-y-auto lg:scroll-thin" aria-label="Intelligence workspace">
            <IntelligenceWorkspace turn={turn} busy={conv.busy} onFollowup={send} onComposerText={(t) => composer.current?.setText(t)} />
          </section>
        </div>
      )}
    </div>
  );
}
