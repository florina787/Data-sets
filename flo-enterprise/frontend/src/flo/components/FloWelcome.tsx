import { Clock, History, ShieldCheck } from "lucide-react";
import type { RefObject } from "react";
import { LogoMark } from "@/components/Logo";
import type { Persona, PersonaCatalogue } from "../types";
import { FloMessageComposer, type ComposerHandle } from "./FloMessageComposer";
import { PersonaSelector } from "./PersonaSelector";
import { SuggestedPromptCards } from "./SuggestedPromptCards";

export function FloWelcome({ catalogue, persona, onPersona, onSend, recent, composerRef, onHistory, firstName }: {
  catalogue?: PersonaCatalogue; persona?: Persona; onPersona: (id: string) => void; onSend: (t: string) => void; recent: string[];
  composerRef: RefObject<ComposerHandle>; onHistory: () => void; firstName?: string;
}) {
  return (
    <div className="flo-hero relative flex min-h-full flex-col items-center px-4 pb-10 pt-8 sm:pt-14">
      <div className="w-full max-w-6xl space-y-7">
        <header className="space-y-3 text-center flo-rise">
          <div className="flex justify-center"><LogoMark className="h-12 w-12" title="FLO" /></div>
          <p className="text-[11px] font-medium uppercase tracking-[0.28em] text-gold">FLO Investment Intelligence</p>
          <h1 className="text-3xl font-semibold leading-tight tracking-tight text-ink sm:text-5xl">
            <span className="whitespace-nowrap">Your wealth.</span> <span className="whitespace-nowrap">Your strategy.</span>{" "}
            <span className="whitespace-nowrap text-gold">Your intelligence.</span>
          </h1>
          <p className="mx-auto max-w-2xl text-sm text-muted sm:text-base">
            {firstName ? `Good to see you, ${firstName}. ` : ""}Ask FLO anything about your investments, portfolios, clients, business performance, or growth strategy.
          </p>
        </header>
        <div className="mx-auto max-w-4xl flo-rise" style={{ animationDelay: "60ms" }}>
          <div className="flo-edge shadow-[0_20px_60px_-25px_rgb(59_130_246/0.45)]">
            <FloMessageComposer ref={composerRef} size="hero" onSend={onSend} personaLabel={persona?.label} />
          </div>
        </div>
        {catalogue && (
          <div className="flo-rise" style={{ animationDelay: "120ms" }}>
            <PersonaSelector personas={catalogue.personas} value={persona?.id ?? catalogue.default} onChange={onPersona} note={catalogue.note} />
          </div>
        )}
        {catalogue && <SuggestedPromptCards prompts={catalogue.starter_prompts} onPick={onSend} />}
        {persona && (
          <section aria-label={`Suggested for ${persona.label}`} className="space-y-2 flo-rise" style={{ animationDelay: "200ms" }}>
            <h2 className="text-xs font-medium uppercase tracking-wider text-muted">For {persona.label}</h2>
            <div className="flex flex-wrap gap-2">
              {persona.prompts.map((p) => (
                <button key={p} onClick={() => onSend(p)} className="rounded-full border border-line px-3 py-1.5 text-xs text-ink/90 hover:border-gold/60">{p}</button>
              ))}
            </div>
          </section>
        )}
        <div className="flex flex-wrap items-start gap-6 text-xs text-muted">
          {recent.length > 0 && (
            <section aria-label="Recently explored questions" className="min-w-0 flex-1 space-y-2">
              <h2 className="flex items-center gap-1 font-medium uppercase tracking-wider"><Clock className="h-3.5 w-3.5" />Recently explored</h2>
              <div className="flex flex-wrap gap-2">
                {recent.slice(0, 6).map((r) => (
                  <button key={r} onClick={() => onSend(r)} className="max-w-full truncate rounded-md bg-card/70 px-2 py-1 text-ink/80 hover:text-ink">{r}</button>
                ))}
              </div>
            </section>
          )}
          <div className="flex items-center gap-3">
            <button onClick={onHistory} className="flex items-center gap-1 hover:text-ink"><History className="h-3.5 w-3.5" />Conversation history</button>
            <span className="flex items-center gap-1"><ShieldCheck className="h-3.5 w-3.5 text-pos" />Policy-enforced · synthetic data</span>
          </div>
        </div>
      </div>
    </div>
  );
}
