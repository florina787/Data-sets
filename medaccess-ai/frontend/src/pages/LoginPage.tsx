import { useState } from "react";

import { ChristinaAvatar } from "../components/ChristinaAvatar";
import { MedAccessLogo } from "../components/Logo";
import { Alert, DemoBanner } from "../components/ui";
import { useApp } from "../hooks/AppContext";
import { useAsync } from "../hooks/useAsync";
import { endpoints } from "../services/api";

const DESCRIPTIONS: Record<string, string> = {
  patient: "Search for appointments, chat with Christina, approve booking handoffs.",
  engineer: "AI-SDLC Command Center, QA, architecture, monitoring.",
  release_approver: "Approves production releases (separation of duties).",
  admin: "Governance, administration and all engineering views.",
};

export function LoginPage() {
  const { login, reducedMotion } = useApp();
  const { data, error } = useAsync(() => endpoints.demoUsers(), []);
  const [err, setErr] = useState<string | null>(null);
  return (
    <div className="min-h-screen bg-gradient-to-br from-brand-50 via-canvas to-teal-50 px-4 py-10">
      <div className="mx-auto max-w-4xl">
        <div className="mb-6 flex justify-center"><MedAccessLogo /></div>
        <div className="card grid gap-6 p-6 md:grid-cols-[auto,1fr] md:p-8">
          <div className="flex justify-center"><ChristinaAvatar state="greeting" size={190} reducedMotion={reducedMotion} /></div>
          <div>
            <h1 className="h1">Smarter Healthcare Access. Shorter Waits. Better Choices.</h1>
            <p className="muted mt-2">Meet Dr. Christina, your AI healthcare access assistant. She helps you explore facilities and potentially earlier appointments. <b>Christina is a virtual AI assistant, not a licensed physician.</b></p>
            <div className="mt-4"><DemoBanner /></div>
            <h2 className="h2 mt-5">Sign in with a demo account</h2>
            <p className="text-xs text-slate-500">Demonstration sign-in (synthetic users). Production uses OAuth 2.0 / OIDC — planned.</p>
            {(error || err) && <div className="mt-2"><Alert tone="danger">{error || err}</Alert></div>}
            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              {data?.items.map((u) => (
                <button key={u.id} className="rounded-xl border border-slate-200 bg-white p-3 text-left hover:border-brand hover:bg-brand-50"
                  onClick={() => login(u.id).catch((e) => setErr(String(e)))}>
                  <div className="font-semibold">{u.name}</div>
                  <div className="text-xs text-slate-600">{DESCRIPTIONS[u.role]}</div>
                </button>
              ))}
            </div>
            <p className="mt-4 text-xs text-slate-500">In an emergency, call 911. For health advice in Ontario, call Health811 (811).</p>
          </div>
        </div>
      </div>
    </div>
  );
}
