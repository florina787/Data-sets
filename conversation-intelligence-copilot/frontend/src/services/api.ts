import type { AnalysisResult, ChatResponse, GraphDefinition, StreamEvent, Trace } from "@/types/api";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, { ...init, headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) } });
  } catch {
    throw new ApiError(0, "The analytics service is unreachable. Check that the backend is running.");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* non-JSON error */
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

export const api = {
  get: <T,>(path: string) => request<T>(path),
  post: <T,>(path: string, body: unknown) => request<T>(path, { method: "POST", body: JSON.stringify(body) }),
  del: <T,>(path: string) => request<T>(path, { method: "DELETE" }),

  analytics: (operation: string, opts: { params?: Record<string, any>; window?: Record<string, any> | null; topics?: string[];
    sentiments?: string[]; products?: string[]; agents?: string[]; dataset_mode?: string } = {}) =>
    request<AnalysisResult>("/api/analytics/query", { method: "POST", body: JSON.stringify({ operation, params: opts.params ?? {}, ...opts }) }),

  chat: (question: string, session_id?: string | null, extra: Record<string, any> = {}) =>
    request<ChatResponse>("/api/chat", { method: "POST", body: JSON.stringify({ question, session_id, ...extra }) }),

  trace: (id: string) => request<Trace>(`/api/traces/${id}`),
  graph: () => request<GraphDefinition>("/api/agents/graph"),

  uiEvent: (event: string, session_id?: string | null, detail: Record<string, any> = {}) => {
    fetch("/api/telemetry/ui-event", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ event, session_id, detail }) }).catch(() => {});
  },
};

/** POST + Server-Sent Events. Returns an abort function. */
export function streamChat(
  body: { question: string; session_id?: string | null; dataset_mode?: string; selected_conversation_id?: string | null },
  onEvent: (e: StreamEvent) => void,
  onError: (err: Error) => void,
): () => void {
  const controller = new AbortController();
  (async () => {
    try {
      const res = await fetch("/api/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
        body: JSON.stringify(body),
        signal: controller.signal,
      });
      if (!res.ok || !res.body) {
        let detail = res.statusText;
        try { detail = (await res.json()).detail; } catch { /* ignore */ }
        throw new ApiError(res.status, typeof detail === "string" ? detail : JSON.stringify(detail));
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let idx: number;
        while ((idx = buffer.indexOf("\n\n")) >= 0) {
          const block = buffer.slice(0, idx);
          buffer = buffer.slice(idx + 2);
          const data = block.split("\n").filter((l) => l.startsWith("data:")).map((l) => l.slice(5).trim()).join("\n");
          if (data) onEvent(JSON.parse(data) as StreamEvent);
        }
      }
    } catch (err) {
      if ((err as Error).name === "AbortError") return;
      onError(err instanceof Error ? err : new Error(String(err)));
    }
  })();
  return () => controller.abort();
}
