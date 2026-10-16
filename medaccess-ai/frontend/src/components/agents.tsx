import { useEffect, useState } from "react";

import type { TraceEntry } from "../services/api";

// Main-path order of the patient LangGraph (branches are shown when they executed).
export const PATIENT_FLOW: { node: string; label: string }[] = [
  { node: "intake", label: "Patient Intake" },
  { node: "clinical_safety", label: "Clinical Safety Check" },
  { node: "safety_interruption", label: "Safety Interruption" },
  { node: "service_classification", label: "Service Classification" },
  { node: "facility_discovery", label: "Facility Discovery" },
  { node: "geospatial", label: "Geospatial Filtering" },
  { node: "availability_search", label: "Availability Search" },
  { node: "recovery", label: "Recovery Agent" },
  { node: "data_quality", label: "Data Quality" },
  { node: "availability_verification", label: "Availability Verification" },
  { node: "eligibility", label: "Eligibility Validation" },
  { node: "wait_time", label: "Wait-Time Comparison" },
  { node: "recommendation", label: "Recommendation" },
  { node: "expand_search_options", label: "Expand Search Options" },
  { node: "expansion_approval", label: "Patient Approval (radius)" },
  { node: "patient_review", label: "Patient Review" },
  { node: "booking_preparation", label: "Booking Preparation" },
  { node: "human_approval", label: "Human Approval" },
  { node: "booking_handoff", label: "Booking Handoff" },
  { node: "confirmation_verification", label: "Confirmation Verification" },
  { node: "notification", label: "Notification" },
  { node: "audit", label: "Audit" },
];
const OPTIONAL = new Set(["safety_interruption", "recovery", "expand_search_options", "expansion_approval", "booking_preparation", "human_approval", "booking_handoff", "confirmation_verification", "notification"]);

type NodeState = "pending" | "running" | "completed" | "failed" | "awaiting_approval" | "skipped";

function latest(trace: TraceEntry[]): Record<string, TraceEntry> {
  const m: Record<string, TraceEntry> = {};
  for (const t of trace) m[t.node] = t;
  return m;
}

export function LangGraphVisualizer({ trace, reducedMotion, animate = true }: { trace: TraceEntry[]; reducedMotion?: boolean; animate?: boolean }) {
  const [revealed, setRevealed] = useState(trace.length);
  useEffect(() => {
    if (!animate || reducedMotion) { setRevealed(trace.length); return; }
    setRevealed(0);
    let i = 0;
    const id = window.setInterval(() => { i += 1; setRevealed(i); if (i >= trace.length) window.clearInterval(id); }, 140);
    return () => window.clearInterval(id);
  }, [trace, animate, reducedMotion]);
  const shown = trace.slice(0, revealed);
  const done = latest(shown);
  const executed = new Set(trace.map((t) => t.node));
  const running = revealed < trace.length ? trace[revealed]?.node : null;
  const finished = trace.length > 0 && revealed >= trace.length;
  const nodes = PATIENT_FLOW.filter((n) => !OPTIONAL.has(n.node) || executed.has(n.node));
  const stateOf = (n: string): NodeState => {
    const t = done[n];
    if (n === running) return "running";
    if (t) return t.status === "awaiting_approval" ? "awaiting_approval" : t.status === "failed" ? "failed" : "completed";
    return finished && trace.length ? "skipped" : "pending";
  };
  const icon: Record<NodeState, string> = { pending: "○", running: "●", completed: "✓", failed: "✕", awaiting_approval: "⏸", skipped: "–" };
  const cls: Record<NodeState, string> = {
    pending: "border-slate-200 text-slate-500 bg-white", running: "border-brand bg-brand-50 text-brand node-running",
    completed: "border-green-200 bg-green-50 text-ok", failed: "border-red-200 bg-red-50 text-danger",
    awaiting_approval: "border-amber-300 bg-amber-50 text-[#9A4500]", skipped: "border-slate-100 bg-slate-50 text-slate-400",
  };
  return (
    <ol className="space-y-1.5" aria-label="Agent workflow progress">
      {nodes.map((n, i) => {
        const st = stateOf(n.node);
        const t = done[n.node];
        return (
          <li key={n.node} className="relative">
            {i > 0 && <span className="absolute -top-1.5 left-[15px] h-1.5 w-px bg-slate-300" aria-hidden="true" />}
            <div className={`flex items-start gap-3 rounded-xl border px-3 py-2 transition-colors ${cls[st]}`}>
              <span className="mt-0.5 w-4 text-center font-bold" aria-hidden="true">{icon[st]}</span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="text-sm font-semibold">{n.label}</span>
                  <span className="text-[11px]">{st.replace("_", " ")}{t && t.duration_ms ? ` · ${t.duration_ms.toFixed(1)} ms` : ""}</span>
                </div>
                {t?.action && <div className="truncate text-xs text-slate-600" title={t.action}>{t.agent ? `${t.title}: ` : ""}{t.action}</div>}
              </div>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

export function AgentActivityPanel({ trace }: { trace: TraceEntry[] }) {
  if (!trace.length) return <p className="muted">Run a search to see agent activity.</p>;
  const total = trace.reduce((a, t) => a + (t.duration_ms || 0), 0);
  return (
    <div>
      <div className="mb-2 text-xs text-slate-500">{trace.length} agent steps · {total.toFixed(1)} ms of agent time · explanations are redacted</div>
      <ul className="divide-y divide-slate-100 text-sm">
        {trace.map((t, i) => (
          <li key={i} className="flex flex-wrap items-start justify-between gap-2 py-1.5">
            <span><span className="font-semibold">{t.title}</span> <span className="text-slate-500">({t.node})</span><br /><span className="text-xs text-slate-600">{t.action}</span></span>
            <span className={`text-xs font-semibold ${t.status === "failed" ? "text-danger" : t.status === "awaiting_approval" ? "text-warn" : "text-ok"}`}>{t.status} · {t.duration_ms.toFixed(1)} ms</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
