import { createContext, useCallback, useContext, useState, type ReactNode } from "react";
import { useApp } from "@/app/AppState";
import { Sheet } from "@/components/common/ui";
import { api } from "@/services/api";
import { SubsetView } from "./SubsetView";
import { TranscriptViewer } from "./TranscriptViewer";

export interface SubsetQuery {
  title: string;
  topics?: string[];
  products?: string[];
  sentiments?: string[];
  window?: Record<string, any> | null;
}

interface Ctx {
  openConversation: (id: string, highlight?: string[]) => void;
  openSubset: (q: SubsetQuery) => void;
}

const EvidenceCtx = createContext<Ctx | null>(null);

export function EvidenceProvider({ children }: { children: ReactNode }) {
  const { sessionId } = useApp();
  const [conv, setConv] = useState<{ id: string; highlight: string[] } | null>(null);
  const [subset, setSubset] = useState<SubsetQuery | null>(null);

  const openConversation = useCallback((id: string, highlight: string[] = []) => {
    setConv({ id, highlight });
    api.uiEvent("evidence.open_conversation", sessionId, { conversation_id: id });
  }, [sessionId]);
  const openSubset = useCallback((q: SubsetQuery) => {
    setSubset(q);
    api.uiEvent("chart.drilldown", sessionId, { title: q.title });
  }, [sessionId]);

  return (
    <EvidenceCtx.Provider value={{ openConversation, openSubset }}>
      {children}
      <Sheet open={!!subset} onOpenChange={(o) => !o && setSubset(null)} title={subset?.title ?? ""} description="Conversations behind this data point, most negative first" wide>
        {subset && <SubsetView query={subset} onOpen={(id) => openConversation(id)} />}
      </Sheet>
      <Sheet open={!!conv} onOpenChange={(o) => !o && setConv(null)} title={conv ? `Conversation ${conv.id}` : ""} description="Source transcript (PII-masked, filler tokens removed)" wide>
        {conv && <TranscriptViewer conversationId={conv.id} highlight={conv.highlight} />}
      </Sheet>
    </EvidenceCtx.Provider>
  );
}

export function useEvidence(): Ctx {
  const v = useContext(EvidenceCtx);
  if (!v) throw new Error("useEvidence must be used inside EvidenceProvider");
  return v;
}
