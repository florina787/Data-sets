import { useState } from "react";
import { Download, FlaskConical, Plus, Stethoscope, Trash2 } from "lucide-react";
import { Link } from "react-router-dom";
import { useApp } from "../../lib/app-state";
import { usePersistent } from "../../lib/usePersistent";
import { Badge, Button, Card, Field, Notice, PageHeader, inputCls } from "../../components/ui";
import { COMMON, COMMON_TESTS, RED_FLAGS, explain, flagOf, questionsFor, triage, type LabResult } from "./logic";

export function MedScanPage() {
  const { profile } = useApp();
  const [results, setResults] = usePersistent<(LabResult & { date: string })[]>(`labs:${profile.id}`, () => []);
  const [f, setF] = useState({ test: COMMON_TESTS[0].test, value: "", unit: COMMON_TESTS[0].unit, low: "", high: "", date: "" });
  const [red, setRed] = useState<string[]>([]);
  const [sym, setSym] = useState<string[]>([]);
  const [weeks, setWeeks] = useState(1);
  const [impact, setImpact] = useState<0 | 1 | 2 | 3>(1);
  const [result, setResult] = useState<ReturnType<typeof triage> | null>(null);
  const qs = questionsFor(results);
  const toggle = (arr: string[], set: (x: string[]) => void, v: string) => set(arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v]);

  function downloadSummary() {
    const body = [`Lab results summary for ${profile.name}, prepared ${new Date().toLocaleDateString()} (entered by the user)`, "",
      ...results.map((r) => `- ${r.test} (${r.date || "date not set"}): ${r.value} ${r.unit}, ${flagOf(r)}. ${explain(r)}`), "", "Questions for my clinician:", ...qs.map((q) => `- ${q}`),
      ...(result ? ["", `Symptom check: ${result.level}. ${result.text}`] : []), "", "Educational summary, not a diagnosis."].join("\n");
    const url = URL.createObjectURL(new Blob([body], { type: "text/plain" }));
    const a = document.createElement("a"); a.href = url; a.download = "lab-summary.txt"; a.click(); URL.revokeObjectURL(url);
  }

  return (
    <div>
      <PageHeader title="MedScan" sub="Understand your lab results and symptoms right away, and walk into your next appointment prepared." />
      <Notice tone="warn">MedScan explains; it doesn't diagnose or replace a clinician. Results are compared only with the reference range printed on your own report. In an emergency, call your local emergency number.</Notice>

      <div className="mt-5 grid gap-5 lg:grid-cols-[1.2fr_1fr]">
        <Card title={<span className="flex items-center gap-2"><FlaskConical size={18} className="text-primary" /> My lab results</span>} actions={results.length ? <Button size="sm" onClick={downloadSummary}><Download size={14} /> Summary</Button> : undefined}>
          {results.length === 0 ? <p className="text-sm text-muted">Enter a result from your report to see a plain-language explanation.</p> : (
            <ul className="space-y-3">{results.map((r, i) => { const fl = flagOf(r); return (
              <li key={i} className="rounded-f-sm bg-surface-2 p-3">
                <div className="flex items-center gap-2"><b>{r.test}</b><Badge tone={fl === "normal" ? "good" : "warn"}>{fl}</Badge><span className="ml-auto font-display text-xl">{r.value} <span className="text-sm text-muted">{r.unit}</span></span>
                  <button aria-label={`Delete ${r.test}`} className="text-muted hover:text-danger" onClick={() => setResults((rs) => rs.filter((_, j) => j !== i))}><Trash2 size={15} /></button></div>
                {r.what && <p className="text-sm text-muted">{r.what}</p>}<p className="mt-1 text-sm">{explain(r)}</p>
              </li>); })}</ul>)}
          {qs.length > 0 && <div className="mt-4"><h4 className="font-medium">Questions to ask your clinician</h4><ul className="mt-1 list-disc pl-5 text-sm">{qs.map((q) => <li key={q}>{q}</li>)}</ul></div>}
          <form className="mt-4 grid grid-cols-2 gap-2 border-t border-line pt-4 sm:grid-cols-3" onSubmit={(e) => { e.preventDefault(); const v = Number(f.value); if (!f.test || Number.isNaN(v) || f.value === "") return;
            const meta = COMMON_TESTS.find((t) => t.test === f.test);
            setResults((rs) => [...rs, { test: f.test, value: v, unit: f.unit, low: f.low === "" ? undefined : Number(f.low), high: f.high === "" ? undefined : Number(f.high), what: meta?.what ?? "", date: f.date }]);
            setF({ ...f, value: "", low: "", high: "" }); }}>
            <Field label="Test"><input list="tests" className={inputCls} value={f.test} onChange={(e) => { const m = COMMON_TESTS.find((t) => t.test === e.target.value); setF({ ...f, test: e.target.value, unit: m?.unit ?? f.unit }); }} />
              <datalist id="tests">{COMMON_TESTS.map((t) => <option key={t.test} value={t.test} />)}</datalist></Field>
            <Field label="Your value"><input type="number" step="any" className={inputCls} value={f.value} onChange={(e) => setF({ ...f, value: e.target.value })} required /></Field>
            <Field label="Unit"><input className={inputCls} value={f.unit} onChange={(e) => setF({ ...f, unit: e.target.value })} /></Field>
            <Field label="Range low (from report)"><input type="number" step="any" className={inputCls} value={f.low} onChange={(e) => setF({ ...f, low: e.target.value })} /></Field>
            <Field label="Range high (from report)"><input type="number" step="any" className={inputCls} value={f.high} onChange={(e) => setF({ ...f, high: e.target.value })} /></Field>
            <Field label="Test date"><input type="date" className={inputCls} value={f.date} onChange={(e) => setF({ ...f, date: e.target.value })} /></Field>
            <div className="col-span-full"><Button type="submit" variant="primary"><Plus size={16} /> Add result</Button></div>
          </form>
          <p className="mt-2 text-xs text-muted">Photo/PDF reading (OCR) needs a secure processing service and is planned; it isn't available yet.</p>
        </Card>

        <Card title={<span className="flex items-center gap-2"><Stethoscope size={18} className="text-primary" /> Quick symptom check</span>}>
          <fieldset><legend className="text-sm font-medium text-danger">Any of these right now?</legend>
            <div className="mt-1 grid gap-1">{RED_FLAGS.map((x) => <label key={x} className="flex items-center gap-2 text-sm"><input type="checkbox" checked={red.includes(x)} onChange={() => toggle(red, setRed, x)} />{x}</label>)}</div></fieldset>
          <fieldset className="mt-4"><legend className="text-sm font-medium">What are you experiencing?</legend>
            <div className="mt-1 flex flex-wrap gap-2">{COMMON.map((s) => <button type="button" key={s} aria-pressed={sym.includes(s)} onClick={() => toggle(sym, setSym, s)} className={`rounded-full px-3 py-1 text-sm ${sym.includes(s) ? "bg-primary text-primary-ink" : "bg-surface-2"}`}>{s}</button>)}</div></fieldset>
          <label className="mt-4 block text-sm">For how many weeks? <b>{weeks}</b><input type="range" min={0} max={26} value={weeks} onChange={(e) => setWeeks(Number(e.target.value))} className="w-full" /></label>
          <fieldset className="mt-2"><legend className="text-sm">How much does it affect your daily life?</legend>
            <div className="mt-1 flex flex-wrap gap-2">{["Not at all", "A little", "A lot", "Severely"].map((l, i) => <button type="button" key={l} aria-pressed={impact === i} onClick={() => setImpact(i as 0 | 1 | 2 | 3)} className={`rounded-full px-3 py-1 text-sm ${impact === i ? "bg-primary text-primary-ink" : "bg-surface-2"}`}>{l}</button>)}</div></fieldset>
          <Button variant="primary" className="mt-4" onClick={() => setResult(triage(red, sym, weeks, impact))}>Check now</Button>
          {result && (
            <div className={`mt-4 rounded-f-sm p-3 ${result.level === "emergency" ? "bg-danger/12" : result.level === "appointment" ? "bg-warn/15" : "bg-good/12"}`} role="status">
              <Badge tone={result.level === "emergency" ? "danger" : result.level === "appointment" ? "warn" : "good"}>{result.level === "emergency" ? "Urgent" : result.level === "appointment" ? "See a clinician soon" : "Self-care & track"}</Badge>
              <p className="mt-1 text-sm">{result.text}</p>
              {result.level === "appointment" && <p className="mt-1 text-sm"><Link className="text-primary underline" to="/app/reminders">Add an appointment and save your questions</Link></p>}
            </div>)}
          <p className="mt-3 text-xs text-muted">Rule-based guidance pending clinical review. It never uses an AI model for urgency decisions.</p>
        </Card>
      </div>
    </div>
  );
}
