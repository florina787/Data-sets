import { create } from "zustand";
import { Api, type ChatEvent, type ChatRequest, type Citation, type Collection, type Governance, type Message, type ModelInfo, type Session, type Settings } from "../services/api";
import { bridge, hasBridge, type AppInfo, type BackendInfo } from "../services/bridge";

export type Page = "welcome" | "workspace" | "screen" | "interview" | "knowledge" | "meeting" | "analytics" | "settings" | "setup" | "about";

export interface Status {
  ollama: { running: boolean; version: string | null; url: string };
  models: ModelInfo[];
  tesseract: boolean;
  asr: { model: string; loaded: boolean; device: string }[];
  embedder: { model: string; loaded: boolean };
  onboarded: boolean;
  profile: string | null;
  data_dir: string;
}

export interface LiveAnswer {
  requestId: string | null;
  question: string;
  text: string;
  meta: Extract<ChatEvent, { type: "meta" }> | null;
  done: Extract<ChatEvent, { type: "done" }> | null;
  error: string | null;
  abort: AbortController;
}

export interface Partial {
  utterance_id: number;
  text: string;
  source: string;
}

export interface DetectedQuestion {
  text: string;
  intent: string;
  confidence: number;
  answer_mode: string;
  context_ref: string | null;
  timestamp: number;
  source: string;
}

export interface Toast {
  id: number;
  kind: "info" | "success" | "warning" | "error";
  text: string;
}

interface State {
  backend: BackendInfo | null;
  api: Api | null;
  appInfo: AppInfo | null;
  status: Status | null;
  settings: Settings | null;
  page: Page;
  sidebarOpen: boolean;
  contextOpen: boolean;
  sessions: Session[];
  sessionQuery: string;
  currentSession: Session | null;
  messages: Message[];
  live: LiveAnswer | null;
  partials: Record<string, Partial>;
  questions: DetectedQuestion[];
  collections: Collection[];
  selectedCollections: string[];
  followups: string[];
  toasts: Toast[];

  init(): Promise<void>;
  setPage(p: Page): void;
  toggleSidebar(): void;
  toggleContext(): void;
  refreshStatus(): Promise<void>;
  loadSettings(): Promise<void>;
  updateSettings(patch: Partial_<Settings>): Promise<void>;
  loadSessions(query?: string): Promise<void>;
  newSession(mode?: Session["mode"], title?: string): Promise<Session>;
  openSession(id: string, page?: Page): Promise<void>;
  ensureSession(mode: Session["mode"]): Promise<Session>;
  deleteSession(id: string): Promise<void>;
  reloadMessages(): Promise<void>;
  ask(req: Omit<ChatRequest, "session_id"> & { session_id?: string }): Promise<Extract<ChatEvent, { type: "done" }> | null>;
  cancel(): Promise<void>;
  loadFollowups(): Promise<void>;
  loadCollections(): Promise<void>;
  toggleCollection(id: string): void;
  setPartial(key: string, p: Partial | null): void;
  pushQuestion(q: DetectedQuestion): void;
  appendTranscript(m: Message): void;
  toast(kind: Toast["kind"], text: string): void;
  dismissToast(id: number): void;
}

type Partial_<T> = { [K in keyof T]?: T[K] };

let toastId = 0;

export const useApp = create<State>((set, get) => ({
  backend: null,
  api: null,
  appInfo: null,
  status: null,
  settings: null,
  page: "welcome",
  sidebarOpen: true,
  contextOpen: true,
  sessions: [],
  sessionQuery: "",
  currentSession: null,
  messages: [],
  live: null,
  partials: {},
  questions: [],
  collections: [],
  selectedCollections: [],
  followups: [],
  toasts: [],

  async init() {
    if (!hasBridge()) {
      set({ backend: { url: "", token: "", status: "failed", error: "Preload bridge missing: open VEENA through its desktop app." } });
      return;
    }
    const b = bridge();
    const onInfo = async (info: BackendInfo) => {
      set({ backend: info, api: info.status === "ready" ? new Api(info) : get().api });
      if (info.status === "ready") {
        await Promise.all([get().loadSettings(), get().refreshStatus(), get().loadSessions(), get().loadCollections()]);
        if (get().settings && !get().settings!.onboarded) set({ page: "setup" });
      }
    };
    b.onBackendStatus((i) => void onInfo(i));
    set({ appInfo: await b.appInfo() });
    await onInfo(await b.backendInfo());
  },

  setPage: (page) => set({ page }),
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
  toggleContext: () => set((s) => ({ contextOpen: !s.contextOpen })),

  async refreshStatus() {
    const api = get().api;
    if (!api) return;
    try {
      set({ status: await api.get<Status>("/api/status") });
    } catch (e) {
      get().toast("error", `Status check failed: ${String(e)}`);
    }
  },

  async loadSettings() {
    const api = get().api;
    if (api) set({ settings: await api.get<Settings>("/api/settings") });
  },

  async updateSettings(patch) {
    const api = get().api;
    if (!api) return;
    set({ settings: await api.patch<Settings>("/api/settings", patch) });
  },

  async loadSessions(query) {
    const api = get().api;
    if (!api) return;
    const q = query ?? get().sessionQuery;
    set({ sessionQuery: q, sessions: await api.get<Session[]>(`/api/sessions${q ? `?q=${encodeURIComponent(q)}` : ""}`) });
  },

  async newSession(mode = "conversation", title) {
    const api = get().api!;
    const s = await api.post<Session>("/api/sessions", { mode, ...(title ? { title } : {}) });
    set({ currentSession: s, messages: [], live: null, partials: {}, questions: [], followups: [] });
    await get().loadSessions();
    return s;
  },

  async openSession(id, page) {
    const api = get().api!;
    const r = await api.get<{ session: Session; messages: Message[] }>(`/api/sessions/${id}`);
    const target: Page =
      page ?? (r.session.mode === "screen" ? "screen" : r.session.mode === "meeting" ? "meeting" : r.session.mode === "interview" ? "interview" : "workspace");
    set({ currentSession: r.session, messages: r.messages, live: null, partials: {}, questions: [], followups: [], page: target });
  },

  async ensureSession(mode) {
    const cur = get().currentSession;
    if (cur && cur.mode === mode) return cur;
    return get().newSession(mode);
  },

  async deleteSession(id) {
    const api = get().api!;
    await api.del(`/api/sessions/${id}`);
    if (get().currentSession?.id === id) set({ currentSession: null, messages: [], live: null });
    await get().loadSessions();
    get().toast("success", "Session deleted.");
  },

  async reloadMessages() {
    const api = get().api;
    const s = get().currentSession;
    if (!api || !s) return;
    const r = await api.get<{ session: Session; messages: Message[] }>(`/api/sessions/${s.id}`);
    set({ currentSession: r.session, messages: r.messages });
  },

  async ask(req) {
    const api = get().api;
    if (!api) return null;
    if (get().live && !get().live!.done && !get().live!.error) await get().cancel();
    const session = req.session_id ? { id: req.session_id } : await get().ensureSession(req.mode ?? "conversation");
    const abort = new AbortController();
    const live: LiveAnswer = { requestId: null, question: req.text, text: "", meta: null, done: null, error: null, abort };
    set({ live, followups: [] });
    const body: ChatRequest = {
      ...req,
      session_id: session.id,
      collection_ids: req.collection_ids ?? get().selectedCollections,
      answer_style: req.answer_style ?? null,
    };
    let done: Extract<ChatEvent, { type: "done" }> | null = null;
    const patch = (p: Partial_<LiveAnswer>) => {
      const cur = get().live;
      if (cur && cur.abort === abort) set({ live: { ...cur, ...p } });
    };
    try {
      let text = "";
      let pending = "";
      let raf = 0;
      for await (const ev of api.chat(body, abort.signal)) {
        switch (ev.type) {
          case "accepted":
            patch({ requestId: ev.request_id });
            void get().reloadMessages();
            break;
          case "meta":
            patch({ meta: ev });
            break;
          case "token":
            pending += ev.t;
            // Batch token renders to animation frames to keep the UI smooth.
            if (!raf) {
              raf = requestAnimationFrame(() => {
                raf = 0;
                text += pending;
                pending = "";
                patch({ text });
              });
            }
            break;
          case "done":
            text += pending;
            pending = "";
            done = ev;
            patch({ text, done: ev });
            break;
          case "paused_sensitive":
            patch({ error: ev.message });
            get().toast("warning", ev.message);
            return null;
          case "error":
            patch({ error: ev.message });
            break;
        }
      }
      if (pending) patch({ text: text + pending });
    } catch (e) {
      if ((e as Error).name === "AbortError") {
        patch({ error: null });
      } else {
        patch({ error: `Request failed: ${(e as Error).message}` });
      }
    }
    await get().reloadMessages();
    await get().loadSessions();
    const cur = get().live;
    if (cur && cur.abort === abort && !cur.error) set({ live: null });
    return done;
  },

  async cancel() {
    const live = get().live;
    const api = get().api;
    if (!live) return;
    if (live.requestId && api) {
      try {
        await api.post(`/api/chat/${live.requestId}/cancel`);
      } catch {
        /* the abort below still stops the stream */
      }
    }
    live.abort.abort();
  },

  async loadFollowups() {
    const api = get().api;
    const s = get().currentSession;
    if (!api || !s) return;
    try {
      const r = await api.post<{ followups: string[] }>(`/api/sessions/${s.id}/followups`);
      set({ followups: r.followups });
    } catch {
      set({ followups: [] });
    }
  },

  async loadCollections() {
    const api = get().api;
    if (!api) return;
    const collections = await api.get<Collection[]>("/api/knowledge/collections");
    set((s) => ({ collections, selectedCollections: s.selectedCollections.filter((id) => collections.some((c) => c.id === id)) }));
  },

  toggleCollection(id) {
    set((s) => ({
      selectedCollections: s.selectedCollections.includes(id) ? s.selectedCollections.filter((c) => c !== id) : [...s.selectedCollections, id],
    }));
  },

  setPartial(key, p) {
    set((s) => {
      const partials = { ...s.partials };
      if (p) partials[key] = p;
      else delete partials[key];
      return { partials };
    });
  },

  pushQuestion(q) {
    set((s) => ({ questions: [q, ...s.questions].slice(0, 30) }));
  },

  appendTranscript(m) {
    set((s) => (s.currentSession?.id === m.session_id ? { messages: [...s.messages, m] } : {}));
  },

  toast(kind, text) {
    const id = ++toastId;
    set((s) => ({ toasts: [...s.toasts, { id, kind, text }].slice(-4) }));
    setTimeout(() => get().dismissToast(id), kind === "error" ? 9000 : 5000);
  },

  dismissToast(id) {
    set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) }));
  },
}));

export type { Citation, Governance };
