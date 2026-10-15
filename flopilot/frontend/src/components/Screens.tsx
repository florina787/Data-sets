import { useRef, useState, type DragEvent } from "react";
import { FloMinInline } from "./Brand";
import type { AppConfig } from "../lib/types";

export function SignIn({ config, onPick, error }: { config: AppConfig | null; onPick: (key: string) => void; error: string | null }) {
  return (
    <main className="signin">
      <div className="signin-card">
        <img className="wordmark" src="/flopilot-wordmark.svg" alt="FloPilot — Florina’s Excel Copilot" />
        <p className="small-print">FloPilot is Florina’s independently built Excel assistant. It is not a Microsoft product.</p>
        <h1 style={{ fontSize: 18, margin: "18px 0 4px" }}>Choose a demo identity</h1>
        <p className="small-print">Local demo authentication. Enterprise sign-in is a configurable extension point, not enabled here.</p>
        {error && <div className="banner error" role="alert">{error}</div>}
        <div className="user-pick">
          {(config?.demo_users ?? []).filter((u) => u.workspace === "ws_demo").map((u) => (
            <button key={u.key} className="action-card" onClick={() => onPick(u.key)}>
              <span style={{ fontSize: 20 }} aria-hidden="true">{u.role === "admin" ? "🛡️" : u.role === "viewer" ? "👁️" : "📊"}</span>
              <span><span className="t">{u.name}</span><br /><span className="d">Role: {u.role}{u.role === "viewer" ? " (can read, cannot approve changes)" : u.role === "admin" ? " (includes audit log)" : " (analyse, propose and approve)"}</span></span>
              <span className="chev">›</span>
            </button>
          ))}
          {!config && <p className="small-print">Connecting to the FloPilot server…</p>}
        </div>
      </div>
    </main>
  );
}

export function Landing({ config, busy, error, onUpload, onDemo, canUpload }: {
  config: AppConfig | null; busy: boolean; error: string | null; canUpload: boolean;
  onUpload: (file: File) => void; onDemo: () => void;
}) {
  const [over, setOver] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const drop = (e: DragEvent) => {
    e.preventDefault();
    setOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file && canUpload) onUpload(file);
  };
  return (
    <main className="landing">
      <div className="landing-card">
        <FloMinInline size={110} blink label="FloMin" />
        <h1 style={{ margin: "6px 0 2px", fontSize: 26 }}>Hi, I’m FloMin.</h1>
        <p style={{ margin: 0, color: "var(--text-2)" }}>Upload a workbook and ask questions in plain English. I compute every number with real calculations and never change your file without your approval.</p>
        {error && <div className="banner error" role="alert" style={{ marginTop: 12 }}>{error}</div>}
        <div className={`dropzone ${over ? "over" : ""}`} onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)} onDrop={drop}>
          {busy ? (
            <p role="status"><span className="spinner" style={{ display: "inline-block", verticalAlign: -2, marginRight: 8 }} />Uploading and inspecting your workbook…</p>
          ) : (
            <>
              <p style={{ marginTop: 0 }}><strong>Drop an .xlsx or .csv file here</strong></p>
              <input ref={input} type="file" accept=".xlsx,.csv" hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) onUpload(f); e.target.value = ""; }} />
              <div className="actions" style={{ justifyContent: "center" }}>
                <button className="btn primary" onClick={() => input.current?.click()} disabled={!canUpload}>Choose a file</button>
                <button className="btn" onClick={onDemo}>Open the synthetic demo workbook</button>
              </div>
              {!canUpload && <p className="small-print">Your role (viewer) can open the demo workbook but cannot upload files.</p>}
            </>
          )}
        </div>
        <p className="small-print">
          Supported: {config?.supported_formats.join(", ") ?? ".xlsx, .csv"} up to {config?.limits.max_upload_mb ?? 10} MB and {(config?.limits.max_cells ?? 500000).toLocaleString()} cells.
          Not supported: {config?.unsupported_formats.join(", ") ?? ".xls, .xlsm"}. Macros are never run and external links are never followed.
          Uploaded files are kept for {config?.retention_days ?? 30} days.
        </p>
      </div>
    </main>
  );
}
