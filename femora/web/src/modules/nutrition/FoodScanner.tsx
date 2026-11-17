// Photo-assisted logging: the camera capture is real and stays on this device; she chooses the dish herself.
// Automatic recognition needs a vision model behind a secure gateway and isn't connected.
import { useEffect, useRef, useState } from "react";
import { Camera, ImageUp, X } from "lucide-react";
import { Button } from "../../components/ui";
import { FOODS, type Food } from "./foods";
import { SugarGauge } from "./SugarGauge";
import { sugarPct } from "./engine";

export function FoodScanner({ region, onAdd, onClose }: { region?: string; onAdd: (f: Food) => void; onClose: () => void }) {
  const video = useRef<HTMLVideoElement>(null);
  const stream = useRef<MediaStream | null>(null);
  const [state, setState] = useState<"starting" | "live" | "denied" | "captured">("starting");
  const [photo, setPhoto] = useState<string | null>(null);
  const [pick, setPick] = useState<Food | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (!navigator.mediaDevices?.getUserMedia) { setState("denied"); return; }
    navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" }, audio: false })
      .then((s) => { if (cancelled) { s.getTracks().forEach((t) => t.stop()); return; } stream.current = s; if (video.current) video.current.srcObject = s; setState("live"); })
      .catch(() => setState("denied"));
    return () => { cancelled = true; stream.current?.getTracks().forEach((t) => t.stop()); };
  }, []);

  function capture() {
    const v = video.current;
    if (!v) return;
    const c = document.createElement("canvas");
    c.width = v.videoWidth || 640; c.height = v.videoHeight || 480;
    c.getContext("2d")?.drawImage(v, 0, 0, c.width, c.height);
    setPhoto(c.toDataURL("image/jpeg", 0.8));
    stream.current?.getTracks().forEach((t) => t.stop());
    setState("captured");
  }

  const rank = (f: Food) => (f.region === region ? 2 : f.region === "Universal" ? 1 : 0);
  const candidates = [...FOODS].sort((a, b) => rank(b) - rank(a)).slice(0, 8);

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/50 p-4" role="dialog" aria-modal="true" aria-label="Scan food with camera">
      <div className="max-h-[92vh] w-full max-w-2xl overflow-y-auto rounded-f-lg bg-surface p-5 shadow-f">
        <div className="mb-3 flex items-center gap-2"><Camera size={20} className="text-primary" /><h2 className="font-display text-xl">Scan your plate</h2>
          <button className="ml-auto rounded-full p-1 hover:bg-surface-2" aria-label="Close scanner" onClick={onClose}><X /></button></div>

        <div className="overflow-hidden rounded-f bg-black">
          {state !== "captured" ? <video ref={video} autoPlay playsInline muted className="aspect-video w-full object-cover" aria-label="Camera preview" />
            : photo && <img src={photo} alt="Captured meal" className="aspect-video w-full object-cover" />}
        </div>

        {state === "starting" && <p className="mt-3 text-sm text-muted">Starting camera… allow access when your browser asks.</p>}
        {state === "denied" && (
          <div className="mt-3 text-sm"><p className="text-muted">Camera unavailable or permission denied. You can upload a photo instead.</p>
            <label className="mt-2 inline-flex cursor-pointer items-center gap-2 rounded-full bg-surface-2 px-4 py-2"><ImageUp size={16} /> Upload photo
              <input type="file" accept="image/*" capture="environment" className="sr-only" onChange={(e) => { const f = e.target.files?.[0]; if (f) { setPhoto(URL.createObjectURL(f)); setState("captured"); } }} /></label></div>)}
        {state === "live" && <div className="mt-3 flex justify-center"><Button variant="primary" onClick={capture}><Camera size={16} /> Capture</Button></div>}

        {state === "captured" && (
          <div className="mt-4">
            <p className="text-sm"><b>Which dish is this?</b> <span className="text-muted">Choose the dish in your photo. Dishes from {region ?? "your region"} are listed first. (Automatic recognition isn't available yet.)</span></p>
            <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
              {candidates.map((f) => { const sp = sugarPct(f.n); return (
                <button key={f.id} onClick={() => setPick(f)} aria-pressed={pick?.id === f.id} className={`rounded-f-sm border p-2 text-left text-sm ${pick?.id === f.id ? "border-primary ring-2 ring-primary/30" : "border-line hover:bg-surface-2"}`}>
                  <span className="text-xl" aria-hidden>{f.emoji}</span><div className="font-medium">{f.name}</div><div className="text-xs text-muted">sugar {sp === null ? "–" : `${sp}%`} kcal</div></button>); })}
            </div>
            {pick && (
              <div className="mt-4 grid gap-4 rounded-f bg-surface-2 p-4 sm:grid-cols-2">
                <div><div className="font-display text-lg">{pick.emoji} {pick.name}</div><div className="text-sm text-muted">{pick.serving} · {pick.n.kcal} kcal · {pick.n.protein} g protein · {pick.n.addedSugar ?? "?"} g added sugar</div></div>
                <SugarGauge n={pick.n} label="Sugar share of calories" />
                <div className="sm:col-span-2 flex gap-2"><Button variant="primary" onClick={() => { onAdd(pick); onClose(); }}>Add to my log</Button><Button onClick={() => { setPhoto(null); setPick(null); onClose(); }}>Discard</Button></div>
              </div>)}
            <p className="mt-3 text-xs text-muted">The photo stays in this browser and is never uploaded.</p>
          </div>)}
      </div>
    </div>
  );
}
