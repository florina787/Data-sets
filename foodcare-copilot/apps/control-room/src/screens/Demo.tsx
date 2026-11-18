import { useState } from "react";
import { useApp } from "../context";
import { SignInPrompt } from "../components/pulse/shared";
import { Conversation } from "./Copilot";

const TRACKS: Record<string, { title: string; blurb: string; lines: string[] }> = {
  command: {
    title: "Your Enterprise. Under Your Command.",
    blurb: "One conversation: systems, risk, evidence, integrations, privacy, a motion story, a recommendation and a board PDF.",
    lines: ["Jerry, show me my enterprise.", "Which factories need attention?", "Where did the information come from?",
      "How do you connect to Databricks?", "How do you interact with Kubernetes?", "Hide confidential details.",
      "Animate how these systems work together.", "What do you recommend?", "Prepare a board-ready PDF."],
  },
  defense: {
    title: "Enterprise Defense Command",
    blurb: "A detected security issue, affected services, an approval-gated containment proposal, and a separate licence-savings opportunity.",
    lines: ["Are we under attack?", "Which business applications are affected?", "Can we isolate the affected endpoint?",
      "Who must approve containment?", "Which licenses are unused?", "Which renewals should we renegotiate?",
      "Prepare a security and savings board report."],
  },
  teams: {
    title: "Cross-functional Team Intelligence",
    blurb: "A Marketing initiative that depends on Commercial approval and Technology delivery.",
    lines: ["Jerry, summarize what every team is building and what needs my attention.", "What is Marketing building?",
      "Which business initiatives are blocked by data engineering?", "Which projects are exceeding budget?",
      "What decisions need my approval this week?", "Prepare a board-ready enterprise delivery briefing PDF"],
  },
};

/** Guided CTO demonstration: scripted lines sent to the real Jerry, in one continuous conversation. */
export default function Demo() {
  const { user } = useApp();
  const [track, setTrack] = useState<keyof typeof TRACKS>("command");
  const [step, setStep] = useState(0);
  const [pending, setPending] = useState<string | null>(null);
  const [key, setKey] = useState(0);
  if (!user) return <SignInPrompt what="the guided demonstration" />;
  const t = TRACKS[track];
  const choose = (k: keyof typeof TRACKS) => { setTrack(k); setStep(0); setKey((x) => x + 1); };
  const next = () => { if (step < t.lines.length) { setPending(t.lines[step]); setStep(step + 1); } };
  return (
    <div className="mx-auto max-w-7xl space-y-4">
      <header className="jerry-hero rounded-3xl border border-surface-line px-6 py-8">
        <div className="eyebrow">Guided CTO demonstration · synthetic company, labelled simulations</div>
        <h1 className="mt-2 text-3xl font-light tracking-tight text-ink md:text-4xl">{t.title}</h1>
        <p className="mt-2 max-w-3xl text-ink-muted">{t.blurb} Unconnected systems are shown with their real state; nothing is executed.</p>
        <div role="tablist" aria-label="Demo track" className="mt-4 flex flex-wrap gap-2">
          {(Object.keys(TRACKS) as (keyof typeof TRACKS)[]).map((k) => (
            <button key={k} role="tab" aria-selected={track === k} onClick={() => choose(k)} className={track === k ? "btn-primary text-xs" : "btn-ghost text-xs"}>{TRACKS[k].title}</button>
          ))}
        </div>
      </header>
      <div className="grid gap-4 lg:grid-cols-[300px_1fr]">
        <ol className="panel space-y-2 self-start" aria-label="Script">
          {t.lines.map((l, i) => (
            <li key={l} className={`rounded-lg px-3 py-2 text-sm ${i < step ? "text-ink-muted line-through decoration-ink-faint" : i === step ? "selected-glow bg-teal/10 text-ink" : "text-ink-muted"}`}>
              <span className="mr-2 text-champagne">{i + 1}.</span>{l}
            </li>
          ))}
          <li className="pt-2">
            <button className="btn-primary w-full justify-center" onClick={next} disabled={step >= t.lines.length} data-testid="demo-next">
              {step >= t.lines.length ? "Demo complete" : step === 0 ? "Start" : "Next question"}
            </button>
          </li>
        </ol>
        <div className="panel flex min-h-[560px] flex-col">
          <Conversation key={key} pending={pending} onConsumed={() => setPending(null)} />
        </div>
      </div>
    </div>
  );
}
