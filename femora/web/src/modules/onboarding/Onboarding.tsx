import { useState } from "react";
import { ArrowRight, Lock, MapPin, MessageCircleHeart, Sparkles, Heart } from "lucide-react";
import { useApp } from "../../lib/app-state";
import { INTEREST_OPTIONS } from "../../data/examples/profiles";
import { WORLD_REGIONS } from "../../components/LocationDialog";
import { Button, Field, Logo, inputCls } from "../../components/ui";
import { tourStore } from "./tours";

const STEPS = ["Welcome", "Meet your Muse", "Your interests", "Privacy", "Where you are"];

/** First-time experience. Every screen can be skipped; settings can be changed later. */
export function Onboarding({ onDone }: { onDone: () => void }) {
  const app = useApp();
  const [i, setI] = useState(0);
  const [region, setRegion] = useState(app.location?.region ?? (app.profile.country === "United States" ? "North America" : ""));
  const [city, setCity] = useState(app.location?.city ?? app.profile.city);
  const finish = (tour: boolean) => {
    if (region && city.trim()) app.setLocation({ region, city: city.trim() });
    onDone();
    if (tour) setTimeout(() => tourStore.start("home"), 50);
  };
  const toggle = (x: string) => app.updateProfile({ interests: app.profile.interests.includes(x) ? app.profile.interests.filter((y) => y !== x) : [...app.profile.interests, x] });

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/60 p-4 pt-[6vh]" role="dialog" aria-modal="true" aria-labelledby="ob-title">
      <div className="f-rise w-full max-w-xl overflow-hidden rounded-f-lg bg-surface shadow-f">
        <div className="hero-grad px-8 pb-6 pt-8 text-[#f7f1e6]">
          <div className="flex items-center gap-2"><Logo /><span className="font-display text-xl">FEMORA <span className="text-[#d7b57a]">Muse</span></span>
            <button className="ml-auto text-sm text-[#e9e1d2] underline" onClick={() => finish(false)}>Skip</button></div>
          <div className="mt-5 flex gap-1.5" aria-hidden>{STEPS.map((s, k) => <span key={s} className={`h-1 flex-1 rounded-full ${k <= i ? "bg-[#d7b57a]" : "bg-white/20"}`} />)}</div>
          <p className="mt-2 text-xs uppercase tracking-widest text-[#d7b57a]">Step {i + 1} of {STEPS.length} · {STEPS[i]}</p>
        </div>
        <div className="px-8 py-6">
          {i === 0 && <div key="0" className="f-enter"><h2 id="ob-title" className="font-display text-4xl">Welcome, {app.profile.name}.</h2>
            <p className="mt-3 text-muted">FEMORA Muse is a calm, private companion for women's health and life: conversation, food, cycles, health records, reminders, safety and community, all in one place.</p></div>}
          {i === 1 && <div key="1" className="f-enter"><h2 id="ob-title" className="flex items-center gap-2 font-display text-3xl"><MessageCircleHeart className="text-accent" /> Meet your Muse</h2>
            <ul className="mt-3 space-y-2 text-sm">
              <li className="flex gap-2"><Heart size={16} className="mt-0.5 shrink-0 text-accent" />Talk about anything: sleep, cycles, family, work, joy. Muse listens first and encourages often.</li>
              <li className="flex gap-2"><Sparkles size={16} className="mt-0.5 shrink-0 text-accent" />Numbers come from your own records and real data, never guesses.</li>
              <li className="flex gap-2"><Lock size={16} className="mt-0.5 shrink-0 text-accent" />Muse supports your clinicians and never replaces them. In an emergency, Guardian is one tap away.</li></ul></div>}
          {i === 2 && <div key="2" className="f-enter"><h2 id="ob-title" className="font-display text-3xl">What would you like help with?</h2><p className="mt-1 text-sm text-muted">Choose any. You can change this later.</p>
            <div className="mt-3 flex flex-wrap gap-2">{INTEREST_OPTIONS.map((x) => { const on = app.profile.interests.includes(x); return <button key={x} aria-pressed={on} onClick={() => toggle(x)} className={`rounded-full px-3 py-1.5 text-sm ${on ? "bg-primary text-primary-ink" : "bg-surface-2"}`}>{x}</button>; })}</div></div>}
          {i === 3 && <div key="3" className="f-enter"><h2 id="ob-title" className="flex items-center gap-2 font-display text-3xl"><Lock className="text-accent" /> Your privacy</h2>
            <p className="mt-1 text-sm text-muted">Everything stays on this device. Export or delete it anytime.</p>
            <label className="mt-4 flex items-start gap-3 text-sm"><input type="checkbox" className="mt-1" checked={app.memoryEnabled} onChange={(e) => app.setMemoryEnabled(e.target.checked)} /><span><b>Let Muse remember facts I approve</b><br /><span className="text-muted">Muse always asks first. You can review or delete memories.</span></span></label>
            <label className="mt-3 flex items-start gap-3 text-sm"><input type="checkbox" className="mt-1" checked={app.prefs.privateMedication} onChange={(e) => app.setPrefs({ ...app.prefs, privateMedication: e.target.checked })} /><span><b>Hide medication and appointment details in alerts</b><br /><span className="text-muted">Useful on shared screens.</span></span></label></div>}
          {i === 4 && <div key="4" className="f-enter"><h2 id="ob-title" className="flex items-center gap-2 font-display text-3xl"><MapPin className="text-accent" /> Where are you?</h2>
            <p className="mt-1 text-sm text-muted">For local dishes, organisations and emergency numbers. City level only, never your address.</p>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <Field label="Region"><select className={inputCls} value={region} onChange={(e) => setRegion(e.target.value)}><option value="">Choose…</option>{WORLD_REGIONS.map((r) => <option key={r}>{r}</option>)}</select></Field>
              <Field label="City"><input className={inputCls} value={city} onChange={(e) => setCity(e.target.value)} placeholder="e.g. Nashville" /></Field></div></div>}
        </div>
        <div className="flex items-center gap-2 border-t border-line px-8 py-4">
          {i > 0 && <Button onClick={() => setI(i - 1)}>Back</Button>}
          <div className="ml-auto flex gap-2">
            {i < STEPS.length - 1 ? <Button variant="primary" onClick={() => setI(i + 1)}>Continue <ArrowRight size={16} /></Button> : <>
              <Button onClick={() => finish(false)} disabled={!region || !city.trim()}>Start</Button>
              <Button variant="primary" onClick={() => finish(true)} disabled={!region || !city.trim()}>Show me around <ArrowRight size={16} /></Button></>}
          </div>
        </div>
      </div>
    </div>
  );
}
