import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Camera, FileText, ImageUp, ScanLine, Stethoscope, Download } from "lucide-react";
import { useApp } from "../../lib/app-state";
import { Badge, Button, Card, Notice, PageHeader, StatusBadge } from "../../components/ui";
import { HomeTest } from "./HomeTest";
import { COMMON, RED_FLAGS, SAMPLE_REPORTS, explain, flagOf, questionsFor, triage } from "./logic";

function ReportCapture({ onDone }: { onDone: () => void }) {
  const v = useRef<HTMLVideoElement>(null);
  const s = useRef<MediaStream | null>(null);
  const [mode, setMode] = useState<"idle" | "camera" | "denied">("idle");
  useEffect(() => () => s.current?.getTracks().forEach((t) => t.stop()), []);
  const start = async () => {
    try { s.current = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } }); setMode("camera"); setTimeout(() => { if (v.current) v.current.srcObject = s.current; }); }
    catch { setMode("denied"); }
  };
  const capture = () => { s.current?.getTracks().forEach((t) => t.stop()); onDone(); };
  return (
    <div className="space-y-3">
      {mode === "camera" ? <><video ref={v} autoPlay playsInline muted className="aspect-video w-full rounded-f bg-black object-cover" aria-label="Camera preview" /><Button variant="primary" onClick={capture}><ScanLine size={16} /> Capture report</Button></> :
        <div className="flex flex-wrap gap-2">
          <Button variant="primary" onClick={start}><Camera size={16} /> Scan with camera</Button>
          <label className="inline-flex cursor-pointer items-center gap-2 rounded-full bg-surface-2 px-4 py-2.5 text-[15px] font-medium"><ImageUp size={16} /> Upload photo or PDF<input type="file" accept="image/*,application/pdf" className="sr-only" onChange={(e) => e.target.files?.length && onDone()} /></label>
          <Button variant="ghost" onClick={onDone}><FileText size={16} /> Use sample report</Button>
        </div>}
      {mode === "denied" && <p className="text-sm text-muted">Camera unavailable. Upload a photo instead, or use the sample report.</p>}
      <p className="text-xs text-muted">Files stay in this browser. In this demo, reading the report is simulated: the fictional sample report for this profile is shown.</p>
    </div>
  );
}

export function MedScanPage() {
  const { profile } = useApp();
  const [scanned, setScanned] = useState(false);
  const [red, setRed] = useState<string[]>([]);
  const [sym, setSym] = useState<string[]>([]);
  const [weeks, setWeeks] = useState(1);
  const [impact, setImpact] = useState<0 | 1 | 2 | 3>(1);
  const [result, setResult] = useState<ReturnType<typeof triage> | null>(null);
  const report = SAMPLE_REPORTS[profile.id] ?? SAMPLE_REPORTS.bea;
  const qs = questionsFor(report.results);
  const toggle = (arr: string[], set: (x: string[]) => void, v: string) => set(arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v]);

  function downloadSummary() {
    const body = [`FEMORA MedScan summary (DEMO, fictional data) for ${profile.name}`, `Report: ${report.lab}, ${report.date}`, "",
      ...report.results.map((r) => `- ${r.test}: ${r.value} ${r.unit} (${flagOf(r)}). ${explain(r)}`), "", "Questions for my clinician:", ...qs.map((q) => `- ${q}`),
      ...(result ? ["", `Symptom check: ${result.level}. ${result.text}`, `Symptoms: ${sym.join(", ") || "none"}; duration ${weeks} weeks; impact ${impact}/3`] : []),
      "", "Educational summary, not a diagnosis."].join("\n");
    const url = URL.createObjectURL(new Blob([body], { type: "text/plain" }));
    const a = document.createElement("a"); a.href = url; a.download = "femora-medscan-summary.txt"; a.click(); URL.revokeObjectURL(url);
  }

  return (
    <div>
      <PageHeader title="MedScan" status="simulated" sub="Understand your lab results and symptoms now, without waiting for an appointment, then walk into your next visit prepared." />
      <Notice tone="warn">MedScan explains and prepares; it does not diagnose or replace a clinician. Sample results are fictional. In an emergency, call your local emergency number.</Notice>

      <div className="mt-5"><HomeTest onResults={() => setScanned(true)} /></div>
      <div className="mt-5 grid gap-5 lg:grid-cols-[1.2fr_1fr]">
        <Card title={<span className="flex items-center gap-2"><ScanLine size={18} className="text-primary" /> Scan a lab report</span>} actions={scanned ? <StatusBadge status="simulated" /> : undefined}>
          {!scanned ? <ReportCapture onDone={() => setScanned(true)} /> : (
            <div>
              <p className="text-sm text-muted">{report.lab} · {new Date(report.date).toLocaleDateString()} · ranges are taken from the report and vary between labs</p>
              <ul className="mt-3 space-y-3">{report.results.map((r) => { const f = flagOf(r); return (
                <li key={r.test} className="rounded-f-sm bg-surface-2 p-3">
                  <div className="flex items-center gap-2"><b>{r.test}</b><Badge tone={f === "normal" ? "good" : "warn"}>{f}</Badge><span className="ml-auto font-display text-xl">{r.value} <span className="text-sm text-muted">{r.unit}</span></span></div>
                  <p className="text-sm text-muted">{r.what}</p><p className="mt-1 text-sm">{explain(r)}</p>
                </li>); })}</ul>
              {qs.length > 0 && <div className="mt-4"><h4 className="font-medium">Questions to ask your clinician</h4><ul className="mt-1 list-disc pl-5 text-sm">{qs.map((q) => <li key={q}>{q}</li>)}</ul></div>}
              <div className="mt-4 flex flex-wrap gap-2"><Button variant="primary" onClick={downloadSummary}><Download size={16} /> Download summary</Button><Button onClick={() => setScanned(false)}>Scan another</Button></div>
            </div>)}
        </Card>

        <Card title={<span className="flex items-center gap-2"><Stethoscope size={18} className="text-primary" /> Quick symptom check</span>}>
          <fieldset><legend className="text-sm font-medium text-danger">Any of these right now?</legend>
            <div className="mt-1 grid gap-1">{RED_FLAGS.map((f) => <label key={f} className="flex items-center gap-2 text-sm"><input type="checkbox" checked={red.includes(f)} onChange={() => toggle(red, setRed, f)} />{f}</label>)}</div></fieldset>
          <fieldset className="mt-4"><legend className="text-sm font-medium">What are you experiencing?</legend>
            <div className="mt-1 flex flex-wrap gap-2">{COMMON.map((s) => <button type="button" key={s} aria-pressed={sym.includes(s)} onClick={() => toggle(sym, setSym, s)} className={`rounded-full px-3 py-1 text-sm ${sym.includes(s) ? "bg-primary text-primary-ink" : "bg-surface-2"}`}>{s}</button>)}</div></fieldset>
          <label className="mt-4 block text-sm">For how many weeks? <b>{weeks}</b><input type="range" min={0} max={26} value={weeks} onChange={(e) => setWeeks(Number(e.target.value))} className="w-full" /></label>
          <fieldset className="mt-2"><legend className="text-sm">How much does it affect your daily life?</legend>
            <div className="mt-1 flex gap-2">{["Not at all", "A little", "A lot", "Severely"].map((l, i) => <button type="button" key={l} aria-pressed={impact === i} onClick={() => setImpact(i as 0 | 1 | 2 | 3)} className={`rounded-full px-3 py-1 text-sm ${impact === i ? "bg-primary text-primary-ink" : "bg-surface-2"}`}>{l}</button>)}</div></fieldset>
          <Button variant="primary" className="mt-4" onClick={() => setResult(triage(red, sym, weeks, impact))}>Check now</Button>
          {result && (
            <div className={`mt-4 rounded-f-sm p-3 ${result.level === "emergency" ? "bg-danger/12" : result.level === "appointment" ? "bg-warn/15" : "bg-good/12"}`} role="status">
              <Badge tone={result.level === "emergency" ? "danger" : result.level === "appointment" ? "warn" : "good"}>{result.level === "emergency" ? "Urgent" : result.level === "appointment" ? "See a clinician soon" : "Self-care & track"}</Badge>
              <p className="mt-1 text-sm">{result.text}</p>
              {result.level === "appointment" && <p className="mt-1 text-sm"><Link className="text-primary underline" to="/app/free-care">Find a free consultation near you</Link></p>}
            </div>)}
          <p className="mt-3 text-xs text-muted">Rule-based triage for demonstration; it needs clinical review before real-world use.</p>
        </Card>
      </div>
    </div>
  );
}
