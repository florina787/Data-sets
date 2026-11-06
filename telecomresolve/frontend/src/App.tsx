import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, getToken, post, setToken } from "./api";
import { go, useRoute } from "./router";
import { Me, Persona, SystemInfo } from "./types";
import { Overview } from "./pages/Overview";
import { Cases } from "./pages/Cases";
import { Workspace } from "./pages/Workspace";
import { EvidencePage } from "./pages/EvidencePage";
import { Approvals } from "./pages/Approvals";
import { AuditPage } from "./pages/AuditPage";
import { Evaluation } from "./pages/Evaluation";
import { ErrorNote } from "./components/ui";

interface Session { me: Me | null; system: SystemInfo | null; can: (p: string) => boolean; lastCase: string | null;
  setLastCase: (c: string) => void }
const SessionCtx = createContext<Session>({ me: null, system: null, can: () => false, lastCase: null, setLastCase: () => {} });
export const useSession = () => useContext(SessionCtx);

const NAV = [
  ["overview", "Overview"], ["cases", "Cases"], ["workspace", "Copilot Workspace"], ["evidence", "Evidence"],
  ["approvals", "Approvals"], ["audit", "Audit"], ["evaluation", "Evaluation"],
] as const;

export default function App() {
  const route = useRoute();
  const [system, setSystem] = useState<SystemInfo | null>(null);
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [me, setMe] = useState<Me | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastCase, setLastCase] = useState<string | null>(null);

  useEffect(() => {
    api<SystemInfo>("/api/system").then(setSystem).catch((e) => setError(`Backend unavailable: ${e.message}`));
    api<Persona[]>("/api/auth/personas").then(setPersonas).catch(() => setPersonas([]));
    if (getToken()) api<Me>("/api/auth/me").then(setMe).catch(() => setToken(null));
  }, []);

  const login = useCallback(async (id: string) => {
    if (!id) { setToken(null); setMe(null); return; }
    try {
      const r = await post<{ token: string }>("/api/auth/demo-login", { persona_id: id });
      setToken(r.token);
      setMe(await api<Me>("/api/auth/me"));
      setError(null);
    } catch (e) { setError((e as Error).message); }
  }, []);

  const caseId = route.caseId ?? lastCase ?? undefined;
  const can = (p: string) => !!me?.permissions.includes(p);
  const live = system?.generation.live_calls;

  return (
    <SessionCtx.Provider value={{ me, system, can, lastCase, setLastCase }}>
      <a className="skip" href="#main">Skip to content</a>
      <div className="banner" role="note">
        <strong>Independent telecom prototype — synthetic data.</strong> Not affiliated with or endorsed by any operator.
        No real customer, network or operator systems are connected.
      </div>
      <header className="topbar">
        <div className="brand"><span className="logo" aria-hidden="true">◆</span> TelecomResolve Copilot</div>
        <div className="modes" aria-label="Operating modes">
          <span className={`mode ${live ? "mode-live" : "mode-demo"}`}>
            Generation: <strong>{system?.generation.generation_mode ?? "…"}</strong>{live ? ` (${system?.generation.model})` : " (deterministic rules)"}
          </span>
          <span className="mode mode-sim">Connectors: <strong>{system?.connector_mode ?? "…"}</strong></span>
        </div>
        {system?.app_mode === "demo" && (
          <label className="persona">
            <span>Demo persona <span className="muted">(demo mode only — not authentication)</span></span>
            <select value={me?.id ?? ""} onChange={(e) => login(e.target.value)}>
              <option value="">Select a persona…</option>
              {personas.map((p) => <option key={p.id} value={p.id}>{p.display_name} · {p.tenant_id}</option>)}
            </select>
          </label>
        )}
      </header>
      <nav className="nav" aria-label="Primary">
        {NAV.map(([key, label]) => (
          <a key={key} href={key === "workspace" || key === "evidence" ? `#/${key}${caseId ? "/" + encodeURIComponent(caseId) : ""}` : `#/${key}`}
             aria-current={route.page === key ? "page" : undefined}>{label}</a>
        ))}
      </nav>
      <main id="main" tabIndex={-1}>
        <ErrorNote error={error} />
        {!me ? (
          <section className="card intro">
            <h1>Sign in with a demo persona</h1>
            <p>Choose a persona above. Each persona has backend-enforced role and tenant permissions; the selector only
              exists in demo mode. Production mode requires an SSO identity provider and disables this selector.</p>
            <p>Suggested walkthrough: sign in as <strong>Ava (Specialist)</strong>, open case <strong>C-1003</strong> in the
              Copilot Workspace, run the investigation, then switch to <strong>Emma (Supervisor)</strong> to approve.</p>
            <button className="btn" onClick={() => { login("u-spec-ava"); go("workspace", "C-1003"); }}>
              Start as Ava with case C-1003
            </button>
          </section>
        ) : (
          <>
            {route.page === "overview" && <Overview />}
            {route.page === "cases" && <Cases />}
            {route.page === "workspace" && <Workspace caseId={caseId} />}
            {route.page === "evidence" && <EvidencePage caseId={caseId} />}
            {route.page === "approvals" && <Approvals />}
            {route.page === "audit" && <AuditPage caseId={caseId} />}
            {route.page === "evaluation" && <Evaluation />}
          </>
        )}
      </main>
      <footer className="foot">
        Policy {system?.policy_version} · Dataset {system?.dataset_version} · All figures derive from persisted
        application events. Synthetic outcomes do not demonstrate real-world accuracy or savings.
      </footer>
    </SessionCtx.Provider>
  );
}
