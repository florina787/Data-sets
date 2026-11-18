import { FormEvent, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { post } from "../../api";
import { useApp } from "../../context";
import { openCopilot } from "../../screens/Copilot";
import { freshness, Priority, ProvenanceChip, SEVERITY } from "./shared";

const OPEN = "investigate:open";

/** Opens the guided investigation panel for a priority, from any screen. */
export function openInvestigation(p: Priority) {
  window.dispatchEvent(new CustomEvent(OPEN, { detail: p }));
}

const STEPS = ["Alert", "Explanation", "Evidence", "Impact", "Recommended action", "Ownership", "Follow-up"];

/**
 * Alert → Explanation → Evidence → Impact → Recommended action → Ownership → Follow-up, in one panel.
 * Saving here records an investigation or decision in Flo & Jerry only; nothing is executed elsewhere.
 */
export function InvestigationPanel() {
  const { user, geo } = useApp();
  const [p, setP] = useState<Priority | null>(null);
  const [saved, setSaved] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [decision, setDecision] = useState("");
  const [followUp, setFollowUp] = useState("");
  const closeBtn = useRef<HTMLButtonElement>(null);
  const opener = useRef<Element | null>(null);

  useEffect(() => {
    const on = (e: Event) => {
      opener.current = document.activeElement;
      setP((e as CustomEvent).detail);
      setSaved(null);
      setError(null);
      setDecision("");
      setFollowUp("");
    };
    window.addEventListener(OPEN, on);
    return () => window.removeEventListener(OPEN, on);
  }, []);
  useEffect(() => {
    if (!p) return;
    closeBtn.current?.focus();
    const esc = (e: KeyboardEvent) => e.key === "Escape" && close();
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [p]);
  const close = () => {
    setP(null);
    (opener.current as HTMLElement | null)?.focus?.();
  };
  if (!p) return null;

  const saveInvestigation = () => post("/api/investigations", { title: p.title, priority_id: p.id, geo: geo.country || geo.node ? geo : null })
    .then(() => setSaved("Investigation saved. Resume it from My Priorities; it compares new evidence against today's."))
    .catch((e) => setError((e as Error).message));
  const recordDecision = (e: FormEvent) => {
    e.preventDefault();
    post("/api/decisions", { title: p.title, decision, priority_id: p.id, follow_up_on: followUp || null })
      .then(() => setSaved("Decision recorded in your journal (Flo & Jerry only — nothing was executed in other systems)."))
      .catch((err) => setError((err as Error).message));
  };

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/50" onClick={close}>
      <aside role="dialog" aria-modal="true" aria-labelledby="inv-title" onClick={(e) => e.stopPropagation()}
        className="flex h-full w-full max-w-xl flex-col overflow-y-auto border-l border-surface-line bg-midnight p-6 shadow-2xl">
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="eyebrow">Guided investigation</div>
            <h2 id="inv-title" className="mt-1 text-xl font-semibold text-ink">{p.title}</h2>
          </div>
          <button ref={closeBtn} className="btn-ghost" onClick={close}>Close</button>
        </div>
        <ol className="mt-3 flex flex-wrap gap-1 text-[11px] text-ink-faint" aria-label="Investigation steps">
          {STEPS.map((s, i) => <li key={s}>{i > 0 && "→ "}{s}</li>)}
        </ol>

        <section className="mt-4 space-y-4 text-sm">
          <Step n={1} title="Alert">
            <span className={`chip ${SEVERITY[p.severity]}`}>{p.severity} priority</span> <ProvenanceChip kind={p.provenance} />
            <span className="ml-1 text-xs text-ink-faint">{freshness(p.as_of)}</span>
          </Step>
          <Step n={2} title="Explanation"><p className="text-ink">{p.why}</p></Step>
          <Step n={3} title="Evidence">
            <ul className="space-y-1.5">{p.evidence.map((e) => (
              <li key={e.label} className="rounded-lg border border-surface-line bg-elevated/60 px-3 py-2">
                <div className="text-ink">{e.label}</div>
                <div className="mt-0.5 flex flex-wrap items-center gap-2 text-xs text-ink-muted">
                  <code>{e.ref}</code><ProvenanceChip kind={e.provenance} /><span>{freshness(e.as_of)}</span>
                </div>
              </li>
            ))}</ul>
          </Step>
          <Step n={4} title="Impact">
            <p className="text-ink-muted">Affects: {p.areas.join(", ")}.</p>
          </Step>
          <Step n={5} title="Recommended action">
            <p className="text-ink">{p.next_step}</p>
            <p className="mt-1 text-xs text-ink-muted">A recommendation, not an action: consequential steps need a person with the right role to approve them in the workflow screens.</p>
          </Step>
          <Step n={6} title="Ownership"><p className="text-ink-muted">{p.owner}</p></Step>
          <Step n={7} title="Follow-up">
            {!user ? <p className="text-ink-muted">Sign in to save an investigation or record a decision.</p> : saved ? (
              <p className="rounded-lg border border-teal/50 bg-teal/10 px-3 py-2 text-teal-soft" role="status">{saved}</p>
            ) : (
              <div className="space-y-3">
                <div className="flex flex-wrap gap-2">
                  <button className="btn-primary" onClick={() => { openCopilot(p.jerry_question); close(); }}><span aria-hidden>✦</span> Ask Jerry to explain</button>
                  <button className="btn-ghost" onClick={saveInvestigation}>Save investigation</button>
                  <Link className="btn-ghost" to={p.link} onClick={close}>Open the detailed page</Link>
                </div>
                <form onSubmit={recordDecision} className="space-y-2 rounded-xl border border-surface-line bg-elevated/50 p-3">
                  <label className="block text-xs text-ink-muted">Decision (for your journal)
                    <input required value={decision} onChange={(e) => setDecision(e.target.value)} className="mt-1 w-full rounded-lg border px-2 py-1.5 text-sm" placeholder="e.g. Expedite the next purchase order" />
                  </label>
                  <label className="block text-xs text-ink-muted">Follow-up date (optional)
                    <input type="date" value={followUp} onChange={(e) => setFollowUp(e.target.value)} className="mt-1 rounded-lg border px-2 py-1.5 text-sm" />
                  </label>
                  <button className="btn-green" type="submit">Record decision</button>
                </form>
              </div>
            )}
            {error && <p className="mt-2 text-xs text-brick-700" role="alert">{error}</p>}
          </Step>
        </section>
      </aside>
    </div>
  );
}

function Step({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[28px_1fr] gap-3">
      <span className="mt-0.5 flex h-6 w-6 items-center justify-center rounded-full border border-champagne/50 text-xs font-semibold text-champagne">{n}</span>
      <div><h3 className="mb-1 text-xs font-semibold uppercase tracking-[0.1em] text-ink-muted">{title}</h3>{children}</div>
    </div>
  );
}
