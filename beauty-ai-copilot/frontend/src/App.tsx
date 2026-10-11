import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { NavLink, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { api, getPersona, setPersona } from "./api";
import { ErrorBox } from "./components";
import ChangePage from "./pages/ChangePage";
import Workspace from "./pages/Workspace";

export type Meta = {
  banner: string;
  modes: any;
  personas: { id: string; display_name: string; persona: string; roles: string[]; tenant_id: string }[];
  persona_selector_enabled: boolean;
  states: string[];
};

type Ctx = { meta: Meta | null; me: any; persona: string; switchPersona: (p: string) => void; version: number; bump: () => void };
export const AppCtx = createContext<Ctx>({ meta: null, me: null, persona: "u-po", switchPersona: () => {}, version: 0, bump: () => {} });
export const useApp = () => useContext(AppCtx);

export const TABS = [
  ["overview", "Change Workspace"], ["requirements", "Requirements"], ["evidence", "Evidence"], ["impact", "Impact"],
  ["development", "Development"], ["evaluation", "Evaluation"], ["approvals", "Approvals"], ["release", "Release"],
  ["monitoring", "Monitoring"], ["audit", "Audit"],
] as const;

function ModeBar({ meta }: { meta: Meta }) {
  const m = meta.modes;
  return (
    <div className="banner" role="region" aria-label="Operating modes">
      <strong data-testid="banner">{meta.banner}</strong>
      <div className="modes">
        <span className="mode" title={m.language_generation.status}>Language: <b>{m.language_generation.mode}</b></span>
        <span className="mode" title={m.beauty_prediction.status}>Prediction: <b>{m.beauty_prediction.mode === "synthetic_fixture" ? "synthetic fixtures (not CV inference)" : m.beauty_prediction.mode}</b></span>
        <span className="mode" title={m.deployment.status}>Deployment: <b>{m.deployment.mode}</b></span>
        <span className="mode">Retrieval: <b>lexical</b></span>
        <span className="mode">Env: <b>{m.app_env}</b></span>
      </div>
    </div>
  );
}

function Side({ meta }: { meta: Meta }) {
  const { persona, switchPersona } = useApp();
  const loc = useLocation();
  const m = loc.pathname.match(/^\/changes\/([^/]+)/);
  const current = m?.[1] ?? (typeof localStorage !== "undefined" ? (() => { try { return localStorage.getItem("lastChange"); } catch { return null; } })() : null) ?? "BR-101";
  return (
    <nav className="side" aria-label="Main navigation">
      <NavLink to="/" end>Change Workspace</NavLink>
      {TABS.slice(1).map(([k, label]) => <NavLink key={k} to={`/changes/${current}/${k}`}>{label}</NavLink>)}
      <div className="persona">
        <label htmlFor="persona">Demo persona (demo mode only)</label>
        <select id="persona" data-testid="persona" value={persona} disabled={!meta.persona_selector_enabled}
          onChange={(e) => switchPersona(e.target.value)}>
          {meta.personas.map((p) => <option key={p.id} value={p.id}>{p.display_name} — {p.persona}</option>)}
        </select>
        <div className="small muted" style={{ marginTop: 4 }}>Selects a seeded fictional user. Permissions are enforced by the server.</div>
      </div>
    </nav>
  );
}

export default function App() {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [me, setMe] = useState<any>(null);
  const [persona, setP] = useState(getPersona());
  const [version, setVersion] = useState(0);
  const [err, setErr] = useState<unknown>(null);
  const nav = useNavigate();
  useEffect(() => { api<Meta>("/api/meta").then(setMeta).catch(setErr); }, []);
  useEffect(() => { api("/api/me").then(setMe).catch(() => setMe(null)); }, [persona]);
  const switchPersona = useCallback((p: string) => { setPersona(p); setP(p); setVersion((v) => v + 1); }, []);
  const bump = useCallback(() => setVersion((v) => v + 1), []);
  if (err) return <div style={{ padding: 20 }}><ErrorBox error={err} /><p>Is the API running? (see README)</p></div>;
  if (!meta) return <div style={{ padding: 20 }}>Loading…</div>;
  return (
    <AppCtx.Provider value={{ meta, me, persona, switchPersona, version, bump }}>
      <ModeBar meta={meta} />
      <div className="layout">
        <Side meta={meta} />
        <main>
          <Routes>
            <Route path="/" element={<Workspace onOpen={(id) => nav(`/changes/${id}/overview`)} />} />
            <Route path="/changes/:id" element={<Navigate to="overview" replace />} />
            <Route path="/changes/:id/:tab" element={<ChangePage />} />
            <Route path="*" element={<Navigate to="/" />} />
          </Routes>
        </main>
      </div>
    </AppCtx.Provider>
  );
}
