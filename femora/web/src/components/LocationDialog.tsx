import { useState } from "react";
import { MapPin } from "lucide-react";
import { useApp } from "../lib/app-state";
import { REGIONS } from "../modules/nutrition/foods";
import { Button, Field, inputCls } from "./ui";

export const WORLD_REGIONS = REGIONS.filter((r) => r !== "Universal");

/** First-run question: where in the world is she? Used for cuisine, and later for communities, care and weather. */
export function LocationDialog({ onClose }: { onClose?: () => void }) {
  const app = useApp();
  const [region, setRegion] = useState(app.location?.region ?? (app.profile.country === "United States" ? "North America" : ""));
  const [city, setCity] = useState(app.location?.city ?? app.profile.city);
  const ok = region && city.trim().length >= 2;
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4" role="dialog" aria-modal="true" aria-labelledby="loc-title">
      <form className="w-full max-w-md rounded-f-lg bg-surface p-6 shadow-f" onSubmit={(e) => { e.preventDefault(); if (ok) { app.setLocation({ region, city: city.trim() }); onClose?.(); } }}>
        <div className="mb-1 flex items-center gap-2 text-primary"><MapPin size={20} /><span className="text-sm font-semibold uppercase tracking-wide">FEMORA is global</span></div>
        <h2 id="loc-title" className="font-display text-2xl">Where are you, {app.profile.name}?</h2>
        <p className="mt-1 text-sm text-muted">We use your region and city to suggest local dishes, and later to find communities, clinicians and weather near you. It stays in this browser.</p>
        <div className="mt-4 space-y-3">
          <Field label="Region">
            <select className={inputCls} value={region} onChange={(e) => setRegion(e.target.value)} required>
              <option value="" disabled>Choose your region</option>
              {WORLD_REGIONS.map((r) => <option key={r}>{r}</option>)}
            </select>
          </Field>
          <Field label="City" hint="City level only. We never ask for your address."><input className={inputCls} value={city} onChange={(e) => setCity(e.target.value)} placeholder="e.g. Lagos, Mumbai, Toronto, São Paulo" required /></Field>
        </div>
        <div className="mt-5 flex justify-end gap-2">
          {onClose && app.location && <Button onClick={onClose}>Cancel</Button>}
          <Button type="submit" variant="primary" disabled={!ok}>Continue</Button>
        </div>
      </form>
    </div>
  );
}
