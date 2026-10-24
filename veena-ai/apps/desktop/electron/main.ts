// Electron main process: window, security policy, screen-capture consent, IPC.
import fs from "node:fs";
import path from "node:path";
import {
  app,
  BrowserWindow,
  desktopCapturer,
  dialog,
  globalShortcut,
  ipcMain,
  IpcMainInvokeEvent,
  session,
  shell,
  systemPreferences,
} from "electron";
import { BackendInfo, BackendSupervisor } from "./backend";

// Tests and portable installs can isolate all app data in one folder.
if (process.env.VEENA_USER_DATA) app.setPath("userData", process.env.VEENA_USER_DATA);

const DEV_URL = process.env.VITE_DEV_SERVER_URL;
const DEV_ORIGIN = DEV_URL ? new URL(DEV_URL).origin : null;

let win: BrowserWindow | null = null;
let backend: BackendSupervisor;

// ---------- screen capture consent state ----------
// A source can only be captured after the user picks it in VEENA's picker.
// The selection is single-use: getDisplayMedia consumes it.
let listedSources = new Map<string, Electron.DesktopCapturerSource>();
let pendingSelection: { id: string; audio: boolean } | null = null;

function isTrustedSender(e: IpcMainInvokeEvent): boolean {
  const url = e.senderFrame?.url ?? "";
  if (DEV_ORIGIN && url.startsWith(DEV_ORIGIN)) return true;
  return url.startsWith("file://") && url.includes("/dist/index.html");
}

function handle<T>(channel: string, fn: (e: IpcMainInvokeEvent, ...args: unknown[]) => T | Promise<T>) {
  ipcMain.handle(channel, (e, ...args) => {
    if (!isTrustedSender(e)) throw new Error("untrusted sender");
    return fn(e, ...args);
  });
}

function sendToRenderer(channel: string, payload: unknown) {
  if (win && !win.isDestroyed()) win.webContents.send(channel, payload);
}

function createWindow() {
  win = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 960,
    minHeight: 640,
    title: "VEENA.AI",
    backgroundColor: "#FCFAF7",
    icon: path.join(__dirname, "..", "assets", "icon-256.png"),
    show: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
      allowRunningInsecureContent: false,
      spellcheck: true,
    },
  });
  win.once("ready-to-show", () => win?.show());

  // No in-app navigation away from the renderer, no pop-up windows.
  win.webContents.on("will-navigate", (e, url) => {
    if (!(DEV_ORIGIN && url.startsWith(DEV_ORIGIN))) e.preventDefault();
  });
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith("https://")) void shell.openExternal(url);
    return { action: "deny" };
  });

  if (DEV_URL) void win.loadURL(DEV_URL);
  else void win.loadFile(path.join(__dirname, "..", "dist", "index.html"));
}

function configureSession() {
  const ses = session.defaultSession;
  // Only our own renderer gets anything: the microphone (never the camera),
  // display capture (which still requires the user's pick, enforced by the
  // display-media handler below) and clipboard writes for "Copy answer".
  ses.setPermissionRequestHandler((wc, permission, callback, details) => {
    const origin = details.requestingUrl ?? wc.getURL();
    const ours = origin.startsWith("file://") || (DEV_ORIGIN !== null && origin.startsWith(DEV_ORIGIN));
    const mediaTypes = (details as { mediaTypes?: string[] }).mediaTypes ?? [];
    if (ours && permission === "media" && !mediaTypes.includes("video")) return callback(true);
    if (ours && (permission === "display-capture" || permission === "clipboard-sanitized-write")) return callback(true);
    callback(false);
  });
  ses.setPermissionCheckHandler((_wc, permission, origin) => {
    const ours = origin.startsWith("file://") || (DEV_ORIGIN !== null && origin.startsWith(DEV_ORIGIN));
    return ours && ["media", "display-capture", "clipboard-sanitized-write"].includes(permission);
  });
  ses.setDisplayMediaRequestHandler(
    (_request, callback) => {
      const sel = pendingSelection;
      pendingSelection = null;
      const source = sel ? listedSources.get(sel.id) : undefined;
      if (!sel || !source) {
        // Never choose a screen on the user's behalf.
        callback({});
        return;
      }
      const streams: Electron.Streams = { video: source };
      if (sel.audio && process.platform === "win32") streams.audio = "loopback";
      callback(streams);
    },
    { useSystemPicker: false },
  );
}

function registerIpc() {
  handle("backend:info", (): BackendInfo => backend.info);
  handle("backend:restart", async () => {
    await backend.restart();
    return backend.info;
  });
  handle("backend:log", () => backend.recentLog());

  handle("app:info", () => ({
    version: app.getVersion(),
    platform: process.platform,
    arch: process.arch,
    electron: process.versions.electron,
    systemAudioSupported: process.platform === "win32",
    userData: app.getPath("userData"),
  }));

  handle("media:access", async (_e, kind) => {
    if (kind !== "microphone" && kind !== "screen") throw new Error("invalid media kind");
    if (process.platform !== "darwin") return "granted";
    if (kind === "microphone") {
      const status = systemPreferences.getMediaAccessStatus("microphone");
      if (status === "granted") return status;
      return (await systemPreferences.askForMediaAccess("microphone")) ? "granted" : "denied";
    }
    return systemPreferences.getMediaAccessStatus("screen");
  });

  handle("screen:list-sources", async () => {
    // Screens and windows are listed separately: on some Linux/X11 setups window
    // enumeration times out, and a combined query can then come back empty.
    const opts = { thumbnailSize: { width: 360, height: 220 }, fetchWindowIcons: false };
    const list = async (types: ("screen" | "window")[]) => {
      for (let attempt = 0; attempt < 3; attempt++) {
        const found = await desktopCapturer.getSources({ ...opts, types }).catch(() => []);
        if (found.length) return found;
        await new Promise((r) => setTimeout(r, 200));
      }
      return [];
    };
    const [screens, windows] = await Promise.all([list(["screen"]), list(["window"])]);
    const sources = [...screens, ...windows];
    const ownTitle = win?.getTitle();
    listedSources = new Map(sources.filter((s) => s.name !== ownTitle).map((s) => [s.id, s]));
    return [...listedSources.values()].map((s) => ({
      id: s.id,
      name: s.name,
      kind: s.id.startsWith("screen:") ? "screen" : "window",
      thumbnail: s.thumbnail.isEmpty() ? null : s.thumbnail.toDataURL(),
    }));
  });

  handle("screen:select-source", (_e, id, audio) => {
    if (typeof id !== "string" || !listedSources.has(id)) throw new Error("unknown source; list sources first");
    pendingSelection = { id, audio: audio === true };
    return true;
  });

  handle("file:save", async (_e, defaultName, content) => {
    if (typeof defaultName !== "string" || typeof content !== "string") throw new Error("invalid arguments");
    if (content.length > 20 * 2 ** 20) throw new Error("export too large");
    const ext = path.extname(defaultName).toLowerCase();
    if (![".md", ".json", ".txt"].includes(ext)) throw new Error("unsupported export type");
    const safeName = path.basename(defaultName).replace(/[<>:"/\\|?*\x00-\x1f]/g, "_");
    const res = await dialog.showSaveDialog(win!, { defaultPath: safeName, filters: [{ name: ext.slice(1).toUpperCase(), extensions: [ext.slice(1)] }] });
    if (res.canceled || !res.filePath) return { saved: false };
    fs.writeFileSync(res.filePath, content, "utf-8");
    return { saved: true, path: res.filePath };
  });

  handle("shell:open-external", (_e, url) => {
    if (typeof url !== "string" || !/^https:\/\/[^\s]+$/.test(url)) throw new Error("only https links can be opened");
    return shell.openExternal(url);
  });
}

function registerShortcuts() {
  const map: Record<string, string> = {
    "CommandOrControl+Shift+Space": "focus",
    "CommandOrControl+Shift+M": "toggle-mic",
    "CommandOrControl+Shift+S": "capture-screen",
  };
  for (const [accel, action] of Object.entries(map)) {
    globalShortcut.register(accel, () => {
      if (action === "focus") {
        if (win?.isMinimized()) win.restore();
        win?.show();
        win?.focus();
      }
      sendToRenderer("shortcut", action);
    });
  }
}

if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (win?.isMinimized()) win.restore();
    win?.focus();
  });

  app.whenReady().then(async () => {
    // fetch() from a file:// page sends Origin "null"; WebSocket upgrades send "file://".
    const origins = ["null", "file://"];
    if (DEV_ORIGIN) origins.push(DEV_ORIGIN);
    backend = new BackendSupervisor(origins, (info) => sendToRenderer("backend:status", info));
    configureSession();
    registerIpc();
    createWindow();
    registerShortcuts();
    await backend.start();
  });

  app.on("will-quit", () => {
    globalShortcut.unregisterAll();
    backend?.stop();
  });
  app.on("window-all-closed", () => app.quit());
}
