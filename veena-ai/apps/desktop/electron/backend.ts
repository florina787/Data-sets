// Launches and supervises the local Python backend.
import { ChildProcess, spawn } from "node:child_process";
import crypto from "node:crypto";
import fs from "node:fs";
import net from "node:net";
import path from "node:path";
import { app } from "electron";

export type BackendStatus = "starting" | "ready" | "restarting" | "failed" | "stopped";

export interface BackendInfo {
  url: string;
  token: string;
  status: BackendStatus;
  error?: string;
}

function freePort(): Promise<number> {
  return new Promise((resolve, reject) => {
    const srv = net.createServer();
    srv.unref();
    srv.on("error", reject);
    srv.listen(0, "127.0.0.1", () => {
      const addr = srv.address();
      srv.close(() => (typeof addr === "object" && addr ? resolve(addr.port) : reject(new Error("no port"))));
    });
  });
}

interface Command {
  cmd: string;
  args: string[];
  cwd: string;
}

/** Packaged: bundled backend executable. Dev: the repo's virtualenv. VEENA_PYTHON overrides. */
export function resolveBackendCommand(): Command {
  const exe = process.platform === "win32" ? "veena-backend.exe" : "veena-backend";
  if (app.isPackaged) {
    const bundled = path.join(process.resourcesPath, "backend", exe);
    if (fs.existsSync(bundled)) return { cmd: bundled, args: [], cwd: path.dirname(bundled) };
    const src = path.join(process.resourcesPath, "backend-src");
    return { cmd: process.env.VEENA_PYTHON || (process.platform === "win32" ? "python" : "python3"), args: ["-m", "backend"], cwd: src };
  }
  const repo = path.resolve(__dirname, "..", "..", "..");
  const venvPy =
    process.platform === "win32" ? path.join(repo, ".venv", "Scripts", "python.exe") : path.join(repo, ".venv", "bin", "python");
  const py = process.env.VEENA_PYTHON || (fs.existsSync(venvPy) ? venvPy : process.platform === "win32" ? "python" : "python3");
  return { cmd: py, args: ["-m", "backend"], cwd: repo };
}

export class BackendSupervisor {
  info: BackendInfo = { url: "", token: crypto.randomBytes(32).toString("base64url"), status: "starting" };
  private proc: ChildProcess | null = null;
  private restarts = 0;
  private stopping = false;
  private log: string[] = [];

  constructor(
    private readonly allowedOrigins: string[],
    private readonly onStatus: (info: BackendInfo) => void,
  ) {}

  private set(status: BackendStatus, error?: string) {
    this.info = { ...this.info, status, error };
    this.onStatus(this.info);
  }

  async start(): Promise<void> {
    const port = await freePort();
    this.info.url = `http://127.0.0.1:${port}`;
    const { cmd, args, cwd } = resolveBackendCommand();
    const dataDir = path.join(app.getPath("userData"), "data");
    const env = {
      ...process.env,
      VEENA_HOST: "127.0.0.1",
      VEENA_PORT: String(port),
      VEENA_TOKEN: this.info.token,
      VEENA_DATA_DIR: dataDir,
      VEENA_ALLOWED_ORIGINS: this.allowedOrigins.join(","),
      PYTHONUNBUFFERED: "1",
      // Analytics-free by default for the libraries that phone home.
      HF_HUB_DISABLE_TELEMETRY: "1",
      DO_NOT_TRACK: "1",
      ANONYMIZED_TELEMETRY: "False",
    };
    this.log = [];
    this.proc = spawn(cmd, args, { cwd, env, windowsHide: true, stdio: ["ignore", "pipe", "pipe"] });
    const ready = new Promise<void>((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error("backend did not start within 90 s")), 90_000);
      const onData = (buf: Buffer) => {
        const text = buf.toString();
        this.log.push(text);
        if (this.log.length > 200) this.log.shift();
        if (text.includes("VEENA_BACKEND_READY")) {
          clearTimeout(timer);
          resolve();
        }
      };
      this.proc!.stdout!.on("data", onData);
      this.proc!.stderr!.on("data", (b: Buffer) => {
        this.log.push(b.toString());
        if (this.log.length > 200) this.log.shift();
      });
      this.proc!.once("exit", (code) => {
        clearTimeout(timer);
        reject(new Error(`backend exited with code ${code}: ${this.log.join("").slice(-800)}`));
      });
      this.proc!.once("error", (e) => {
        clearTimeout(timer);
        reject(e);
      });
    });
    try {
      await ready;
      await this.waitHealthy();
      this.restarts = 0;
      this.set("ready");
    } catch (e) {
      this.set("failed", String(e instanceof Error ? e.message : e));
      return;
    }
    this.proc.once("exit", () => {
      if (this.stopping) return;
      if (this.restarts < 3) {
        this.restarts += 1;
        this.set("restarting", "backend stopped unexpectedly; restarting");
        setTimeout(() => void this.start(), 1000 * this.restarts);
      } else {
        this.set("failed", "backend crashed repeatedly: " + this.log.join("").slice(-800));
      }
    });
  }

  private async waitHealthy(): Promise<void> {
    for (let i = 0; i < 50; i++) {
      try {
        const r = await fetch(`${this.info.url}/api/health`);
        if (r.ok) return;
      } catch {
        /* not listening yet */
      }
      await new Promise((r) => setTimeout(r, 200));
    }
    throw new Error("backend health check failed");
  }

  async restart(): Promise<void> {
    this.stop();
    this.stopping = false;
    this.restarts = 0;
    this.set("starting");
    await this.start();
  }

  stop(): void {
    this.stopping = true;
    if (this.proc && this.proc.exitCode === null) {
      this.proc.kill();
    }
    this.proc = null;
    this.info = { ...this.info, status: "stopped" };
  }

  recentLog(): string {
    return this.log.join("").slice(-4000);
  }
}
