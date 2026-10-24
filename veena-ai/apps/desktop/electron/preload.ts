// Narrow, typed bridge between the sandboxed renderer and the main process.
import { contextBridge, ipcRenderer, IpcRendererEvent } from "electron";

type Listener<T> = (payload: T) => void;

function subscribe<T>(channel: string, cb: Listener<T>): () => void {
  const fn = (_e: IpcRendererEvent, payload: T) => cb(payload);
  ipcRenderer.on(channel, fn);
  return () => ipcRenderer.removeListener(channel, fn);
}

const api = {
  backendInfo: () => ipcRenderer.invoke("backend:info"),
  restartBackend: () => ipcRenderer.invoke("backend:restart"),
  backendLog: () => ipcRenderer.invoke("backend:log"),
  appInfo: () => ipcRenderer.invoke("app:info"),
  mediaAccess: (kind: "microphone" | "screen") => ipcRenderer.invoke("media:access", kind),
  listScreenSources: () => ipcRenderer.invoke("screen:list-sources"),
  selectScreenSource: (id: string, audio: boolean) => ipcRenderer.invoke("screen:select-source", id, audio),
  saveFile: (name: string, content: string) => ipcRenderer.invoke("file:save", name, content),
  openExternal: (url: string) => ipcRenderer.invoke("shell:open-external", url),
  onBackendStatus: (cb: Listener<unknown>) => subscribe("backend:status", cb),
  onShortcut: (cb: Listener<string>) => subscribe("shortcut", cb),
};

contextBridge.exposeInMainWorld("veena", api);

export type VeenaBridge = typeof api;
