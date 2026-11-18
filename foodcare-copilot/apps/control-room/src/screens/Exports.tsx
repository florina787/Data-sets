import { useEffect, useState } from "react";
import { api } from "../api";
import { useApp } from "../context";
import { SignInPrompt, Skeleton } from "../components/pulse/shared";
import { download } from "../components/visuals/Actions";

const GROUPS: [string, string[]][] = [
  ["Executive", ["board", "executive", "decisions", "architecture"]],
  ["Security & savings", ["security_savings", "security_posture", "incident_impact", "availability", "remediation", "licenses", "renewals"]],
  ["Delivery portfolio", ["delivery_board", "portfolio_weekly", "project_status", "tech_dependencies", "commercial_review", "marketing_readiness"]],
  ["Operations", ["technology", "supplier_risk"]],
];

/** Executive Export Studio: real PDFs, filtered by the same server-side policy as the screens. */
export default function Exports() {
  const { user } = useApp();
  const [kinds, setKinds] = useState<Record<string, string> | null>(null);
  const [cls, setCls] = useState("");
  const [msg, setMsg] = useState<Record<string, string>>({});
  useEffect(() => { if (user) api("/api/exports").then((d: any) => { setKinds(d.kinds); setCls(d.classification); }); }, [user?.username]);
  if (!user) return <SignInPrompt what="the Export Studio" />;
  return (
    <div className="mx-auto max-w-7xl space-y-5">
      <header>
        <div className="eyebrow">Reports · Executive Export Studio</div>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight text-ink">Board-ready reports</h1>
        <p className="mt-1 max-w-3xl text-ink-muted">Each PDF is built on the server from policy-filtered data: executive summary, findings, charts with text alternatives, evidence and provenance, reporting period, assumptions and limitations, next steps, timestamp and classification ({cls}). You can also ask Jerry: “Make this board-ready.”</p>
      </header>
      {!kinds ? <Skeleton lines={8} /> : GROUPS.map(([g, ks]) => (
        <section key={g}>
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-[0.12em] text-ink-muted">{g}</h2>
          <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{ks.filter((k) => kinds[k]).map((k) => (
            <li key={k} className="welcome-card flex flex-col gap-2 rounded-2xl border border-surface-line p-4">
              <span aria-hidden className="flex h-9 w-9 items-center justify-center rounded-xl bg-champagne/10 text-champagne">⤓</span>
              <span className="font-semibold text-ink">{kinds[k]}</span>
              <button className="btn-primary mt-auto self-start text-xs" onClick={() => download(`/api/exports/${k}.pdf`, (m) => setMsg({ ...msg, [k]: m }))}>Download PDF</button>
              {msg[k] && <span className="text-[11px] text-ink-muted" role="status">{msg[k]}</span>}
            </li>
          ))}</ul>
        </section>
      ))}
    </div>
  );
}
