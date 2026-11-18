import { useEffect, useState } from "react";
import { api, post } from "../api";
import { can, useApp } from "../context";
import { SignInPrompt, Skeleton } from "../components/pulse/shared";
import { openCopilot } from "./Copilot";

const STATE: Record<string, string> = {
  connected: "border-leaf-500/70 text-leaf-700", connection_tested: "border-leaf-500/70 text-leaf-700", read_only: "border-teal/70 text-teal-soft",
  configured: "border-royal-400/70 text-royal-400", adapter_available: "border-champagne/70 text-champagne", simulated: "border-champagne/70 text-champagne",
  planned: "border-surface-line text-ink-faint", failed: "border-risk text-brick-700", write_with_approval: "border-teal text-teal",
};

/** Connect Your Enterprise: every integration with a state that is verified, never assumed. */
export default function Connect() {
  const { user } = useApp();
  const [reg, setReg] = useState<any[] | null>(null);
  const [msg, setMsg] = useState<Record<string, string>>({});
  const load = () => api<{ connectors: any[] }>("/api/connectors").then((d) => setReg(d.connectors));
  useEffect(() => { if (user) load(); }, [user?.username]);
  if (!user) return <SignInPrompt what="your integrations" />;
  const test = (id: string) => post(`/api/connectors/${id}/test`).then((r: any) => { setMsg({ ...msg, [id]: r.detail }); load(); }).catch((e) => setMsg({ ...msg, [id]: (e as Error).message }));
  const groups = reg ? [...new Set(reg.map((r) => r.category))] : [];
  return (
    <div className="mx-auto max-w-7xl space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="eyebrow">Technology · Connect your enterprise</div>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight text-ink">Attach Jerry to the systems you already run</h1>
          <p className="mt-1 max-w-3xl text-ink-muted">Read-only adapters, least-privilege identities and the Privacy Shield in front of everything. A connector is only shown as connected after a real request succeeds. Credentials live in server environment variables — never in the browser.</p>
        </div>
        <button className="btn-primary" onClick={() => openCopilot("How does this connect to Databricks and Kubernetes?")}><span aria-hidden>✦</span> Explain the architecture</button>
      </header>
      {!reg ? <Skeleton lines={8} /> : groups.map((g) => (
        <section key={g} aria-labelledby={`g-${g}`}>
          <h2 id={`g-${g}`} className="mb-2 text-sm font-semibold uppercase tracking-[0.12em] text-ink-muted">{g}</h2>
          <ul className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {reg.filter((r) => r.category === g).map((r) => (
              <li key={r.id} className="panel flex flex-col gap-2" data-testid={`connector-${r.id}`}>
                <div className="flex items-start justify-between gap-2"><span className="font-semibold text-ink">{r.name}</span><span className={`chip ${STATE[r.state] ?? STATE.planned}`}>{r.state.replace(/_/g, " ")}</span></div>
                <p className="text-sm text-ink-muted">{r.detail}</p>
                {r.setup && <details className="text-xs text-ink-muted"><summary className="cursor-pointer text-teal">Setup, permissions and scope</summary>
                  <p className="mt-1"><b className="text-ink">Server variables:</b> {r.setup.env.join(", ")}</p><p><b className="text-ink">Identity:</b> {r.setup.auth}</p><p><b className="text-ink">Scope:</b> {r.setup.scope}</p></details>}
                {r.last_test && <p className={`text-xs ${r.last_test.ok ? "text-leaf-700" : "text-brick-700"}`}>Last test {r.last_test.at.slice(0, 16)}: {r.last_test.detail}</p>}
                {["configured", "connection_tested", "failed"].includes(r.state) && can(user, "connector.test") && <button className="btn-ghost mt-auto self-start text-xs" onClick={() => test(r.id)}>Run read-only test</button>}
                {msg[r.id] && <p className="text-xs text-champagne" role="status">{msg[r.id]}</p>}
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
