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
}

export interface ScreenSource {
  id: string;
  name: string;
  kind: "screen" | "window";
  thumbnail: string | null;
}

export interface VeenaBridge {
  backendInfo(): Promise<BackendInfo>;
  restartBackend(): Promise<BackendInfo>;
  backendLog(): Promise<string>;
  appInfo(): Promise<AppInfo>;
  mediaAccess(kind: "microphone" | "screen"): Promise<string>;
  listScreenSources(): Promise<ScreenSource[]>;
  selectScreenSource(id: string, audio: boolean): Promise<boolean>;
  saveFile(name: string, content: string): Promise<{ saved: boolean; path?: string }>;
  openExternal(url: string): Promise<void>;
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
