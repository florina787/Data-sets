import { BookOpen, ShieldAlert, X } from "lucide-react";
import { useEffect } from "react";
import { Badge, Button } from "@/components/ui";
import type { MessageResponse } from "../types";
import { FinancialChartRenderer } from "./FinancialChartRenderer";

export function EvidenceDrawer({ r, open, onClose }: { r: MessageResponse; open: boolean; onClose: () => void }) {
  useEffect(() => {
    if (!open) return;
    const h = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [open, onClose]);
  if (!open) return null;
  const w = r.workflow;
  const denied = w.tool_calls.filter((t) => t.decision !== "allow");
  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/40" onClick={onClose}>
      <aside role="dialog" aria-modal="true" aria-label="Evidence and governance trace" onClick={(e) => e.stopPropagation()}
        className="flo-slide-left flex h-full w-full max-w-2xl flex-col border-l border-line bg-side shadow-2xl">
        <div className="flex items-center gap-2 border-b border-line px-4 py-3">
          <h2 className="text-sm font-semibold">Evidence & governance trace</h2>
          <Button size="icon" variant="ghost" className="ml-auto" onClick={onClose} aria-label="Close evidence"><X className="h-4 w-4" /></Button>
        </div>
        <div className="flex-1 space-y-4 overflow-y-auto scroll-thin p-4 text-xs">
          <div className="flex flex-wrap gap-1.5">
            <Badge tone="blue">route: {w.route ?? r.intent.domain}</Badge>
            <Badge>{r.intent.classifier}</Badge>
            <Badge>model: {w.model_mode || w.model}</Badge>
            <Badge>{w.latency_ms} ms</Badge>
            <Badge tone="gold">request {r.request_id}</Badge>
            {w.injection?.flagged && <Badge tone="crit">prompt injection flagged</Badge>}
          </div>
          {w.graph && <FinancialChartRenderer spec={w.graph} onFollowup={() => undefined} height={260} />}
          <section>
            <h3 className="mb-1 font-semibold">Intent plan</h3>
            <p className="text-muted">{r.intent.label} · persona {r.persona} · classification {r.intent.risk_classification}
              {r.intent.time_horizon_months ? ` · ${r.intent.time_horizon_months} months` : ""}{r.intent.follow_up_of ? ` · follow-up of ${r.intent.follow_up_of}` : ""}</p>
            <p className="text-muted">Agents permitted: {r.intent.agents_authorized.join(", ") || "none"}</p>
            {r.intent.agents_not_authorized.length > 0 && <p className="text-warn">Not permitted for your identity: {r.intent.agents_not_authorized.join(", ")}</p>}
          </section>
          <section>
            <h3 className="mb-1 font-semibold">Tool calls ({w.tool_calls.length}) · {denied.length} denied</h3>
            <div className="max-h-64 overflow-auto scroll-thin rounded-md border border-line">
              <table className="w-full">
                <thead className="sticky top-0 bg-side text-left text-muted"><tr><th className="px-2 py-1">Tool</th><th className="px-2 py-1">Agent</th><th className="px-2 py-1">Decision</th><th className="px-2 py-1">ms</th></tr></thead>
                <tbody>{w.tool_calls.map((t, i) => (
                  <tr key={i} className="border-t border-line/60"><td className="px-2 py-1">{t.tool}</td><td className="px-2 py-1 text-muted">{t.agent}</td>
                    <td className={t.decision === "allow" ? "px-2 py-1 text-pos" : "px-2 py-1 text-crit"}>{t.decision}{t.rule ? ` (${t.rule})` : ""}</td>
                    <td className="px-2 py-1 tabular-nums text-muted">{t.latency_ms ?? ""}</td></tr>))}</tbody>
              </table>
            </div>
          </section>
          {w.errors.length > 0 && (
            <section><h3 className="mb-1 flex items-center gap-1 font-semibold"><ShieldAlert className="h-3.5 w-3.5 text-warn" />Agent outcomes</h3>
              <ul className="list-disc pl-4 text-muted">{w.errors.map((e, i) => <li key={i}>{e.agent}: {e.failure_class}{e.message ? ` — ${e.message}` : ""}</li>)}</ul></section>
          )}
          {r.citations.length > 0 && (
            <section><h3 className="mb-1 flex items-center gap-1 font-semibold"><BookOpen className="h-3.5 w-3.5" />Citations</h3>
              <ol className="list-decimal pl-4">{r.citations.map((c, i) => <li key={i}>{c.title} v{c.version} — {c.section} <span className="text-muted">({c.document_id})</span></li>)}</ol></section>
          )}
          {r.assumptions.length > 0 && (
            <section><h3 className="mb-1 font-semibold">Assumptions</h3>
              <ul className="space-y-0.5">{r.assumptions.map((a) => <li key={a.name}><code>{a.name}</code> = {String(a.value)} {a.unit} <span className="text-muted">({a.source})</span></li>)}</ul></section>
          )}
          <section className="text-muted"><h3 className="mb-1 font-semibold text-ink">Trace references</h3>{r.trace_ids.join(", ") || "—"}</section>
        </div>
      </aside>
    </div>
  );
}
