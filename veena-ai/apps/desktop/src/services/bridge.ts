// Typed access to the preload bridge (window.veena).

export type BackendStatus = "starting" | "ready" | "restarting" | "failed" | "stopped";

export interface BackendInfo {
  url: string;
  token: string;
  status: BackendStatus;
  error?: string;
}

export interface AppInfo {
  version: string;
  platform: string;
  arch: string;
  electron: string;
  systemAudioSupported: boolean;
  userData: string;
  sessionType?: string | null;
}

export interface ScreenSource {
  id: string;
  name: string;
  kind: "screen" | "window";
  thumbnail: string | null;
  /** false: the source produced no preview (minimized, other desktop, protected, or no permission). */
  previewable?: boolean;
  note?: string | null;
}

export interface VeenaBridge {
  backendInfo(): Promise<BackendInfo>;
  restartBackend(): Promise<BackendInfo>;
  backendLog(): Promise<string>;
  appInfo(): Promise<AppInfo>;
  mediaAccess(kind: "microphone" | "screen"): Promise<string>;
  listScreenSources(): Promise<ScreenSource[]>;
  selectScreenSource(id: string, audio: boolean): Promise<boolean>;
  openScreenPrivacySettings?(): Promise<void>;
  setCaptureProtection?(on: boolean): Promise<{ applied: boolean; supported: boolean }>;
  saveFile(name: string, content: string): Promise<{ saved: boolean; path?: string }>;
  openExternal(url: string): Promise<void>;
  checkForUpdates(): Promise<{ current: string; latest: string | null; newer: boolean; url: string | null; notes: string | null; error?: string }>;
  onBackendStatus(cb: (info: BackendInfo) => void): () => void;
  onShortcut(cb: (action: string) => void): () => void;
}

declare global {
  interface Window {
    veena?: VeenaBridge;
  }
}

export function bridge(): VeenaBridge {
  if (!window.veena) {
    throw new Error("VEENA must run inside its desktop app (preload bridge missing).");
  }
  return window.veena;
}

export const hasBridge = () => typeof window !== "undefined" && !!window.veena;
