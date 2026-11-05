import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { api, apiBlobUrl, post, upload } from "../api";
import { Card, Empty, Notice } from "../components/ui";
import { useBlob } from "../hooks";
import { Potato } from "../components/Illustrations";
import { useApp } from "../context";
import { AskButton } from "./Copilot";

type Potato = {
  potato_no: number; item_id: string; grade: string | null; detection_score: number; length_mm: number | null;
  width_mm: number | null; area_px: number; elongation: number; solidity: number; dark_pct: number; green_pct: number;
  edge: boolean; possible_cluster: number | null; bbox: number[]; reasons: string[];
  model_grade: string | null; corrected: boolean; corrected_by: string | null;
};
type Batch = {
  id: string; title: string; supplier: string | null; lot_code: string | null; mm_per_px: number | null;
  created_at: string; thresholds: Record<string, number>; summary: any; potatoes: Potato[];
  images: { id: string; original_name: string; width: number; height: number; duration_ms: number }[];
  detector_info: { name: string; kind: string; validated: boolean; disclosure: string; trained_model: { available: boolean; reason: string } };
};

const GRADE_STYLE: Record<string, string> = {
  Good: "bg-leaf-100 text-leaf-700", Moderate: "bg-amber-100 text-amber-700", "Not Good": "bg-brick-100 text-brick-700",
};
const GRADE_ICON: Record<string, string> = { Good: "✓", Moderate: "▲", "Not Good": "●" };

function GradeBadge({ grade }: { grade: string | null }) {
  const g = grade ?? "Not graded";
  return <span className={`whitespace-nowrap rounded px-1.5 py-0.5 text-xs font-semibold ${GRADE_STYLE[g] ?? "bg-cream-200 text-navy-700"}`}><span aria-hidden>{GRADE_ICON[g] ?? "–"}</span> {g}</span>;
}

async function download(path: string, name: string) {
  const url = await apiBlobUrl(path);
  const a = document.createElement("a");
  a.href = url; a.download = name; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** Viewfinder with corner brackets: shows the chosen photo, or the live webcam until captured. */
function Scanner({ file, onCapture }: { file: File | null; onCapture: (f: File) => void }) {
  const [stream, setStream] = useState<MediaStream | null>(null);
  const [camError, setCamError] = useState<string | null>(null);
  const video = useRef<HTMLVideoElement>(null);
  const preview = useMemo(() => (file ? URL.createObjectURL(file) : null), [file]);
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);
  useEffect(() => { if (video.current && stream) video.current.srcObject = stream; }, [stream]);
  useEffect(() => () => stream?.getTracks().forEach((t) => t.stop()), [stream]);
  const start = async () => {
    setCamError(null);
    try { setStream(await navigator.mediaDevices.getUserMedia({ video: { width: { ideal: 1280 } }, audio: false })); }
    catch (e) { setCamError(`Webcam unavailable: ${(e as Error).message}`); }
  };
  const stop = () => { stream?.getTracks().forEach((t) => t.stop()); setStream(null); };
  const capture = () => {
    const v = video.current;
    if (!v || !v.videoWidth) return;
    const canvas = document.createElement("canvas");
    canvas.width = v.videoWidth; canvas.height = v.videoHeight;
    canvas.getContext("2d")?.drawImage(v, 0, 0);
    canvas.toBlob((b) => { if (b) { onCapture(new File([b], `webcam-${Date.now()}.jpg`, { type: "image/jpeg" })); stop(); } }, "image/jpeg", 0.92);
  };
  const corner = "absolute h-7 w-7 border-ice-400";
  return (
    <div className="space-y-2">
      <div className="relative aspect-[4/3] overflow-hidden rounded-2xl border border-surface-line bg-[#06101f]">
        {stream ? <video ref={video} autoPlay playsInline muted className="h-full w-full object-cover" aria-label="Live webcam preview" />
          : preview ? <img src={preview} alt="Selected photo, ready to inspect" className="h-full w-full object-contain" />
            : <div className="flex h-full flex-col items-center justify-center gap-2 text-xs text-navy-600"><Potato size={56} /><span>Choose a photo or start the webcam</span></div>}
        <span className={`${corner} left-4 top-4 rounded-tl-xl border-l-2 border-t-2`} aria-hidden />
        <span className={`${corner} right-4 top-4 rounded-tr-xl border-r-2 border-t-2`} aria-hidden />
        <span className={`${corner} bottom-4 left-4 rounded-bl-xl border-b-2 border-l-2`} aria-hidden />
        <span className={`${corner} bottom-4 right-4 rounded-br-xl border-b-2 border-r-2`} aria-hidden />
        <span className="absolute right-3 top-3 rounded-lg border border-surface-line bg-surface-base/80 px-2 py-0.5 text-[10px] font-semibold text-ice-300" title="Classical computer vision, not a trained AI model">Classical CV</span>
      </div>
      <div className="flex flex-wrap gap-2">
        {!stream ? <button type="button" className="btn-ghost text-xs" onClick={start}>Start webcam</button>
          : <><button type="button" className="btn-primary text-xs" onClick={capture}>Capture photo</button><button type="button" className="btn-ghost text-xs" onClick={stop}>Stop webcam</button></>}
      </div>
      {camError && <p role="alert" className="text-xs text-brick-700">{camError}</p>}
    </div>
  );
}

function NewInspection({ onDone }: { onDone: (b: Batch) => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [form, setForm] = useState({ title: "", supplier: "", lot_code: "", mm_per_px: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const run = async (e: FormEvent) => {
    e.preventDefault();
    if (!file) return;
    setBusy(true); setError(null);
    try {
      const batch = await post("/api/inspections", {
        title: form.title || file.name, supplier: form.supplier || null, lot_code: form.lot_code || null,
        mm_per_px: form.mm_per_px ? Number(form.mm_per_px) : null,
      });
      const result = await upload(`/api/inspections/${batch.id}/images?filename=${encodeURIComponent(file.name)}`, file);
      onDone(result.batch);
    } catch (err) { setError((err as Error).message); } finally { setBusy(false); }
  };
  const sample = async () => {
    setBusy(true); setError(null);
    try { onDone((await post("/api/inspections/sample")).batch); } catch (err) { setError((err as Error).message); } finally { setBusy(false); }
  };
  const field = (key: keyof typeof form, label: string, extra: Record<string, string> = {}) => (
    <label className="block text-xs text-navy-700">{label}
      <input className="mt-0.5 w-full rounded border border-cream-300 px-2 py-1 text-sm" value={form[key]}
        onChange={(e) => setForm({ ...form, [key]: e.target.value })} {...extra} />
    </label>
  );
  return (
    <Card title="New inspection">
      <form onSubmit={run} className="space-y-2">
        <Scanner file={file} onCapture={setFile} />
        <label className="block text-xs text-navy-700">Photo of potatoes (JPEG, PNG or WebP; plain background, potatoes not touching)
          <input type="file" accept="image/jpeg,image/png,image/webp" className="mt-1 block w-full text-sm" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        </label>
        {field("title", "Batch title")}
        <div className="grid grid-cols-2 gap-2">{field("supplier", "Supplier")}{field("lot_code", "Lot code")}</div>
        {field("mm_per_px", "Scale: millimetres per pixel (optional; enables size in mm)", { inputMode: "decimal", placeholder: "e.g. 0.25" })}
        {error && <Notice kind="error">{error}</Notice>}
        <div className="flex flex-wrap gap-2">
          <button className="btn-primary" disabled={!file || busy}>{busy ? "Inspecting…" : "Inspect"}</button>
          <button type="button" className="btn-ghost" disabled={busy} onClick={sample} title="Rendered shapes with known answers, not a photo">Try a synthetic sample</button>
        </div>
      </form>
    </Card>
  );
}

function Thresholds({ batch, onChange }: { batch: Batch; onChange: (b: Batch) => void }) {
  const [values, setValues] = useState(batch.thresholds);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => setValues(batch.thresholds), [batch.id]);
  const save = async () => {
    try { onChange(await api(`/api/inspections/${batch.id}/thresholds`, { method: "PUT", body: JSON.stringify({ thresholds: values }) })); setError(null); }
    catch (e) { setError((e as Error).message); }
  };
  return (
    <details className="text-xs">
      <summary className="cursor-pointer font-semibold text-navy-800">Quality thresholds (re-grades from stored measurements; no re-processing)</summary>
      <div className="mt-2 grid grid-cols-2 gap-2 md:grid-cols-3">
        {Object.entries(values).map(([k, v]) => (
          <label key={k} className="text-navy-700">{k.replace(/_/g, " ")}
            <input type="number" step="any" min={0} className="mt-0.5 w-full rounded border border-cream-300 px-2 py-1" value={v}
              onChange={(e) => setValues({ ...values, [k]: Number(e.target.value) })} />
          </label>
        ))}
      </div>
      {error && <p role="alert" className="mt-1 text-brick-700">{error}</p>}
      <button className="btn-ghost mt-2" onClick={save}>Apply thresholds</button>
    </details>
  );
}

/** Concentric quality rings: share of graded potatoes per grade, count in the centre. */
function QualityRings({ s }: { s: any }) {
  const rings = [
    { label: "Good", pct: s.pct?.Good ?? 0, n: s.counts?.Good ?? 0, colour: "#10b981", r: 62 },
    { label: "Moderate", pct: s.pct?.Moderate ?? 0, n: s.counts?.Moderate ?? 0, colour: "#f59e0b", r: 50 },
    { label: "Not Good", pct: s.pct?.["Not Good"] ?? 0, n: s.counts?.["Not Good"] ?? 0, colour: "#ef4444", r: 38 },
  ];
  const sweep = 270;
  const arc = (r: number, frac: number) => {
    const start = (135 * Math.PI) / 180, end = start + (sweep * Math.PI / 180) * frac;
    const p = (a: number) => `${70 + r * Math.cos(a)} ${70 + r * Math.sin(a)}`;
    return `M ${p(start)} A ${r} ${r} 0 ${(sweep * frac) > 180 ? 1 : 0} 1 ${p(end)}`;
  };
  return (
    <div className="card flex items-center gap-4" role="img" aria-label={`Quality: ${rings.map((r) => `${r.label} ${r.pct}%`).join(", ")} of ${s.graded} graded potatoes`}>
      <svg width="150" height="140" viewBox="0 0 140 130" aria-hidden>
        {rings.map((r) => (
          <g key={r.label}>
            <path d={arc(r.r, 1)} fill="none" stroke="#1e3654" strokeWidth="9" strokeLinecap="round" />
            {r.pct > 0 && <path d={arc(r.r, Math.min(r.pct / 100, 0.999))} fill="none" stroke={r.colour} strokeWidth="9" strokeLinecap="round" />}
          </g>
        ))}
        <text x="70" y="70" textAnchor="middle" fontSize="24" fontWeight="600" fill="#f8fafc">{s.detected ?? 0}</text>
        <text x="70" y="86" textAnchor="middle" fontSize="9" fill="#94a3b8">potatoes</text>
      </svg>
      <ul className="space-y-1.5 text-sm">
        {rings.map((r) => (
          <li key={r.label} className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full" style={{ background: r.colour }} aria-hidden />
            <span className="w-20 text-navy-700">{r.label}</span><span className="font-mono text-navy-900">{r.pct}%</span><span className="text-xs text-navy-600">({r.n})</span></li>
        ))}
        <li className="pt-1 text-xs text-navy-600">of {s.graded} graded{s.not_graded ? ` · ${s.not_graded} not graded` : ""}{s.corrected ? ` · ${s.corrected} corrected by an inspector` : ""}</li>
      </ul>
    </div>
  );
}

function Correction({ batchId, potato, onChange }: { batchId: string; potato: Potato; onChange: (b: Batch) => void }) {
  const [grade, setGrade] = useState("Good");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { setReason(""); setError(null); }, [potato.potato_no]);
  const save = async (e: FormEvent) => {
    e.preventDefault();
    try {
      const out = await api(`/api/inspections/${batchId}/potatoes/${potato.potato_no}/correction`, { method: "PUT", body: JSON.stringify({ grade, reason }) });
      onChange(out.batch);
    } catch (err) { setError((err as Error).message); }
  };
  return (
    <details className="rounded-lg border border-surface-line p-2 text-xs">
      <summary className="cursor-pointer font-semibold text-navy-800">Correct this grade (inspector review)</summary>
      <form onSubmit={save} className="mt-2 space-y-2">
        <label className="block">New grade
          <select className="mt-0.5 w-full rounded border border-surface-line px-2 py-1" value={grade} onChange={(e) => setGrade(e.target.value)}>
            {["Good", "Moderate", "Not Good"].map((g) => <option key={g}>{g}</option>)}
          </select>
        </label>
        <label className="block">Reason (required, kept in the audit log)
          <input className="mt-0.5 w-full rounded border border-surface-line px-2 py-1" value={reason} onChange={(e) => setReason(e.target.value)} maxLength={300} placeholder="e.g. dark patch is soil, not rot" />
        </label>
        {error && <p role="alert" className="text-brick-700">{error}</p>}
        <button className="btn-ghost" disabled={reason.trim().length < 3}>Save correction</button>
        <p className="text-navy-600">The rules' grade is kept next to yours. Corrections become labelled examples for future model training.</p>
      </form>
    </details>
  );
}

function BatchView({ batch, onChange }: { batch: Batch; onChange: (b: Batch) => void }) {
  const [imageId, setImageId] = useState(batch.images[0]?.id ?? null);
  const [selected, setSelected] = useState<number | null>(null);
  const [filter, setFilter] = useState<string>("all");
  useEffect(() => { setImageId(batch.images[0]?.id ?? null); setSelected(null); }, [batch.id]);
  const annotated = useBlob(imageId ? `/api/inspections/${batch.id}/images/${imageId}` : null);
  const crop = useBlob(selected ? `/api/inspections/${batch.id}/potatoes/${selected}/image` : null);
  const s = batch.summary;
  const p = batch.potatoes.find((x) => x.potato_no === selected) ?? null;
  const image = batch.images.find((i) => i.id === imageId);
  const rows = batch.potatoes.filter((x) => filter === "all" || (x.grade ?? "Not graded") === filter);
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 className="text-lg font-semibold">{batch.title}</h2>
          <p className="text-xs text-navy-600">{batch.id} · supplier {batch.supplier ?? "–"} · lot {batch.lot_code ?? "–"} · {new Date(batch.created_at).toLocaleString()}{batch.mm_per_px ? ` · ${batch.mm_per_px} mm/px` : " · no scale (sizes relative to the batch)"}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <AskButton question={`How many potatoes are detected in ${batch.id} and which are defective?`} label="Ask about this batch" />
          <button className="btn-ghost" onClick={() => download(`/api/inspections/${batch.id}/report.csv`, `${batch.id}.csv`)}>Download CSV</button>
          <button className="btn-ghost" onClick={() => download(`/api/inspections/${batch.id}/report.json`, `${batch.id}.json`)}>Download JSON</button>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-2 md:grid-cols-5" aria-label="Batch summary">
        {[["Detected", s.detected, null], ["Good", s.counts?.Good, s.pct?.Good], ["Moderate", s.counts?.Moderate, s.pct?.Moderate],
          ["Not Good", s.counts?.["Not Good"], s.pct?.["Not Good"]], ["Not graded", s.not_graded, null]].map(([label, n, pct]) => (
          <div key={label as string} className="card py-2">
            <div className="text-xs text-navy-600">{label as string}</div>
            <div className="text-2xl font-semibold">{n as number}</div>
            {pct !== null && <div className="text-xs text-navy-600">{pct as number}% of graded</div>}
          </div>
        ))}
      </div>
      <QualityRings s={s} />
      <div className="grid gap-3 lg:grid-cols-[1fr_320px]">
        <Card title={`Annotated image${image ? ` · ${image.original_name || image.id} · ${image.width}×${image.height}px · ${image.duration_ms} ms` : ""}`}>
          {batch.images.length > 1 && (
            <div className="mb-2 flex gap-1">{batch.images.map((i) => <button key={i.id} className={`btn-ghost text-xs ${i.id === imageId ? "bg-cream-200" : ""}`} onClick={() => setImageId(i.id)}>{i.original_name || i.id}</button>)}</div>
          )}
          {annotated ? <img src={annotated} alt={`Annotated inspection image with ${s.detected} numbered potato outlines coloured by grade`} className="w-full rounded" /> : <Empty>Loading image…</Empty>}
          <p className="mt-1 text-xs text-navy-600">Outline colour: green Good, amber Moderate, red Not Good, grey not graded. Click a number below to inspect a potato.</p>
          <div className="mt-2 flex flex-wrap gap-1" role="list" aria-label="Potatoes">
            {batch.potatoes.filter((x) => x.item_id === imageId).map((x) => (
              <button key={x.potato_no} role="listitem" onClick={() => setSelected(x.potato_no)} aria-pressed={selected === x.potato_no}
                className={`rounded px-2 py-0.5 font-mono text-xs ${selected === x.potato_no ? "ring-2 ring-navy-600" : ""} ${GRADE_STYLE[x.grade ?? ""] ?? "bg-cream-200 text-navy-700"}`}>#{x.potato_no}</button>
            ))}
          </div>
        </Card>
        <Card title={p ? `Potato #${p.potato_no}` : "Potato detail"}>
          {!p ? <Empty>Select a potato number.</Empty> : (
            <div className="space-y-2 text-sm">
              {crop && <img src={crop} alt={`Close-up of potato #${p.potato_no}`} className="max-h-56 rounded" />}
              <div className="flex flex-wrap items-center gap-2">
                <GradeBadge grade={p.grade} />
                {p.corrected && <span className="text-xs text-gold-300">Inspector correction by {p.corrected_by} (rules said {p.model_grade ?? "not graded"})</span>}
              </div>
              <ul className="list-disc pl-5 text-xs">{p.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
              <Correction batchId={batch.id} potato={p} onChange={onChange} />
              <table className="table text-xs"><tbody>
                {p.length_mm !== null && <tr><th>Length × width</th><td>{p.length_mm} × {p.width_mm} mm</td></tr>}
                <tr><th>Area</th><td>{p.area_px.toLocaleString()} px</td></tr>
                <tr><th>Elongation</th><td>{p.elongation}</td></tr>
                <tr><th>Solidity</th><td>{p.solidity}</td></tr>
                <tr><th>Dark area</th><td>{p.dark_pct}%</td></tr>
                <tr><th>Green area</th><td>{p.green_pct}%</td></tr>
                <tr><th>Detection score</th><td>{p.detection_score} <span className="text-navy-600">(heuristic)</span></td></tr>
              </tbody></table>
            </div>
          )}
        </Card>
      </div>
      <Card title="All potatoes" actions={
        <label className="text-xs">Show <select className="rounded border border-cream-300 px-1" value={filter} onChange={(e) => setFilter(e.target.value)}>
          {["all", "Good", "Moderate", "Not Good", "Not graded"].map((g) => <option key={g}>{g}</option>)}
        </select></label>}>
        <div className="max-h-80 overflow-auto">
          <table className="table text-xs">
            <thead><tr><th>#</th><th>Grade</th><th>{batch.mm_per_px ? "Length mm" : "Area px"}</th><th>Elong.</th><th>Solidity</th><th>Dark %</th><th>Green %</th><th>Reason</th></tr></thead>
            <tbody>{rows.map((x) => (
              <tr key={x.potato_no} className="cursor-pointer hover:bg-cream-100" onClick={() => { setImageId(x.item_id); setSelected(x.potato_no); }}>
                <td className="font-mono">#{x.potato_no}</td><td><GradeBadge grade={x.grade} /></td>
                <td>{batch.mm_per_px ? x.length_mm : x.area_px.toLocaleString()}</td><td>{x.elongation}</td><td>{x.solidity}</td>
                <td>{x.dark_pct}</td><td>{x.green_pct}</td><td>{x.reasons[0]}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
        <div className="mt-3"><Thresholds batch={batch} onChange={onChange} /></div>
      </Card>
    </div>
  );
}

export default function Inspection() {
  const { user } = useApp();
  const [data, setData] = useState<any>(null);
  const [batch, setBatch] = useState<Batch | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = () => api("/api/inspections").then(setData).catch((e) => setError((e as Error).message));
  useEffect(() => { if (user) load(); }, [user]);
  const open = (id: string) => api(`/api/inspections/${id}`).then(setBatch).catch((e) => setError((e as Error).message));
  const remove = async (id: string) => {
    if (!window.confirm("Delete this inspection batch and its images?")) return;
    await api(`/api/inspections/${id}`, { method: "DELETE" });
    if (batch?.id === id) setBatch(null);
    load();
  };
  const d = data?.detector;
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold">Potato inspection studio</h1>
        <p className="text-sm text-navy-600">Detect every potato in a photo, measure size and shape, flag visible colour defects and grade each one against your thresholds.</p>
      </div>
      {d && (
        <Notice kind="warn">
          <strong>Method: {d.kind}.</strong> {d.disclosure} {d.trained_model.available ? "" : d.trained_model.reason}
        </Notice>
      )}
      {!user && <Notice>Sign in with any demo account to inspect images.</Notice>}
      {error && <Notice kind="error">{error}</Notice>}
      <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
        <div className="space-y-4">
          {user && <NewInspection onDone={(b) => { setBatch(b); load(); }} />}
          <Card title="Inspection history">
            {!data?.batches?.length ? <Empty>No inspections yet.</Empty> : (
              <ul className="space-y-1 text-xs">{data.batches.map((b: any) => (
                <li key={b.id} className={`flex items-start gap-1 rounded ${batch?.id === b.id ? "bg-navy-100" : "hover:bg-cream-200"}`}>
                  <button className="min-w-0 flex-1 px-2 py-1 text-left" onClick={() => open(b.id)}>
                    <div className="truncate font-medium text-navy-900">{b.title}</div>
                    <div className="text-navy-600">{new Date(b.created_at).toLocaleString()} · {b.summary.detected ?? 0} detected · {b.summary.counts?.Good ?? 0} Good</div>
                  </button>
                  <button className="px-1 py-1 text-navy-600 hover:text-brick-700" onClick={() => remove(b.id)} aria-label={`Delete inspection ${b.title}`}>✕</button>
                </li>
              ))}</ul>
            )}
          </Card>
        </div>
        {batch ? <BatchView batch={batch} onChange={setBatch} /> : <Card>
          <div className="flex flex-col items-center gap-3 py-10 text-center">
            <div className="flex items-end gap-4"><Potato size={84} /><Potato size={60} /><Potato size={72} /></div>
            <p className="text-base font-semibold text-navy-900">No batch selected</p>
            <p className="max-w-md text-sm text-navy-600">Upload a photo of potatoes on a plain background, or try the synthetic sample. Every potato will be numbered, measured and graded with its reasons.</p>
          </div>
        </Card>}
      </div>
    </div>
  );
}
