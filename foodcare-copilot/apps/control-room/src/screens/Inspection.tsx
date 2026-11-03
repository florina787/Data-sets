import { FormEvent, useEffect, useState } from "react";
import { api, apiBlobUrl, post, upload } from "../api";
import { Card, Empty, Notice } from "../components/ui";
import { useBlob } from "../hooks";
import { useApp } from "../context";
import { AskButton } from "./Copilot";

type Potato = {
  potato_no: number; item_id: string; grade: string | null; detection_score: number; length_mm: number | null;
  width_mm: number | null; area_px: number; elongation: number; solidity: number; dark_pct: number; green_pct: number;
  edge: boolean; possible_cluster: number | null; bbox: number[]; reasons: string[];
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
              <GradeBadge grade={p.grade} />
              <ul className="list-disc pl-5 text-xs">{p.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
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
        {batch ? <BatchView batch={batch} onChange={setBatch} /> : <Card><Empty>Upload a photo or try the synthetic sample to start an inspection.</Empty></Card>}
      </div>
    </div>
  );
}
