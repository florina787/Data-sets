// HTTP client for the local backend. Every call carries the per-launch token.
import type { BackendInfo } from "./bridge";

export interface Citation {
  n: number;
  chunk_id: number;
  document_id: string;
  collection_id: string;
  filename: string;
  page: number | null;
  score: number;
  vector_score: number;
  lexical_score: number;
  snippet: string;
}

export interface Message {
  id: number;
  session_id: string;
  role: "user" | "assistant" | "transcript" | "system";
  content: string;
  intent: string | null;
  answer_style: string | null;
  model: string | null;
  citations: Citation[];
  meta: Record<string, unknown>;
  created_at: string;
}

export interface Session {
  id: string;
  title: string;
  mode: "conversation" | "screen" | "interview" | "meeting";
  summary: string | null;
  created_at: string;
  updated_at: string;
  message_count?: number;
}

export interface ModelInfo {
  name: string;
  size_bytes: number;
  family: string | null;
  parameter_size: string | null;
  quantization: string | null;
  capabilities: string[];
  vision: boolean;
}

export interface Collection {
  id: string;
  name: string;
  kind: string;
  created_at: string;
  chunk_count: number;
  documents: { id: string; filename: string; pages: number; chunk_count: number; created_at: string }[];
}

export type Settings = {
  onboarded: boolean;
  profile: "lite" | "balanced" | "performance" | null;
  text_model: string | null;
  vision_model: string | null;
  asr_model: string;
  asr_language: string | null;
  answer_style: string;
  retention_days: number;
  redact_screens: boolean;
  pause_on_sensitive: boolean;
  question_escalation: boolean;
  auto_answer_questions: boolean;
  context_turns: number;
  continuous_interval_s: number;
  speak_interviewer: boolean;
};

export interface ChatRequest {
  session_id: string;
  text: string;
  source?: "typed" | "speech" | "screen" | "system";
  mode?: Session["mode"];
  answer_style?: string | null;
  intent?: string | null;
  image_b64?: string | null;
  screen_action?: string | null;
  continuous?: boolean;
  collection_ids?: string[];
  resume_collection_id?: string | null;
  job_description?: string | null;
  transcript_context?: string[];
  model?: string | null;
}

export type ChatEvent =
  | { type: "accepted"; request_id: string; user_message_id: number }
  | {
      type: "meta";
      agent: string;
      style: string;
      model: string;
      vision: boolean;
      citations: Citation[];
      notes: string[];
      redaction?: { boxes: number; kinds: string[]; sensitive: boolean } | null;
      timings: Record<string, number>;
    }
  | { type: "token"; t: string }
  | { type: "done"; message_id: number; stats: GenerationStats; total_ms: number; governance: Governance; cancelled: boolean }
  | { type: "error"; code: string; message: string }
  | { type: "paused_sensitive"; message: string };

export interface GenerationStats {
  model: string;
  first_token_ms: number | null;
  total_ms: number;
  eval_tokens: number;
  prompt_tokens: number;
  tokens_per_second: number | null;
  cancelled: boolean;
}

export interface Governance {
  flags: { kind: string; detail: string }[];
  notes: string[];
  cited: number[];
  grounded: boolean;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

export class Api {
  constructor(private info: BackendInfo) {}

  get baseUrl() {
    return this.info.url;
  }

  get wsUrl() {
    return this.info.url.replace(/^http/, "ws");
  }

  get token() {
    return this.info.token;
  }

  private headers(json = true): HeadersInit {
    const h: Record<string, string> = { Authorization: `Bearer ${this.info.token}` };
    if (json) h["Content-Type"] = "application/json";
    return h;
  }

  async request<T>(method: string, path: string, body?: unknown): Promise<T> {
    const r = await fetch(this.info.url + path, {
      method,
      headers: this.headers(body !== undefined && !(body instanceof FormData)),
      body: body === undefined ? undefined : body instanceof FormData ? body : JSON.stringify(body),
    });
    if (!r.ok) {
      let detail = r.statusText;
      try {
        const j = await r.json();
        detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
      } catch {
        /* non-JSON error body */
      }
      throw new ApiError(r.status, detail);
    }
    const ct = r.headers.get("content-type") ?? "";
    return (ct.includes("application/json") ? r.json() : r.text()) as Promise<T>;
  }

  get = <T>(p: string) => this.request<T>("GET", p);
  post = <T>(p: string, b?: unknown) => this.request<T>("POST", p, b ?? {});
  patch = <T>(p: string, b: unknown) => this.request<T>("PATCH", p, b);
  del = <T>(p: string) => this.request<T>("DELETE", p);

  /** Stream newline-delimited JSON events. Aborting the signal cancels generation. */
  async *stream<T>(path: string, body: unknown, signal?: AbortSignal): AsyncGenerator<T> {
    const r = await fetch(this.info.url + path, {
      method: "POST",
      headers: this.headers(),
      body: JSON.stringify(body),
      signal,
    });
    if (!r.ok || !r.body) throw new ApiError(r.status, await r.text());
    yield* readNdjson<T>(r.body);
  }

  chat(req: ChatRequest, signal?: AbortSignal) {
    return this.stream<ChatEvent>("/api/chat", req, signal);
  }

  upload(collectionId: string, file: File) {
    const fd = new FormData();
    fd.append("file", file, file.name);
    return this.request<{ duplicate: boolean; chunks?: number; document: { filename: string } }>(
      "POST",
      `/api/knowledge/collections/${collectionId}/documents`,
      fd,
    );
  }
}

export async function* readNdjson<T>(body: ReadableStream<Uint8Array>): AsyncGenerator<T> {
  const reader = body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let nl: number;
      while ((nl = buf.indexOf("\n")) >= 0) {
        const line = buf.slice(0, nl).trim();
        buf = buf.slice(nl + 1);
        if (line) yield JSON.parse(line) as T;
      }
    }
    if (buf.trim()) yield JSON.parse(buf) as T;
  } finally {
    reader.releaseLock();
  }
}
