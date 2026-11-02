import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, ScanEye, Upload } from "lucide-react";
import { DataTable } from "@/components/DataTable";
import { Badge, Card, ErrorBox, PageHeader, Skeleton } from "@/components/ui";
import { download, get, post, upload } from "@/lib/api";
import { Banner, Metric, num, pct } from "./common";

type Caps = { qwen: { available: boolean; model: string | null; quantization: string | null; runtime: string | null; context_window: number; modality: string; reason: string };
  vision_model: { found: boolean; model: string | null; searched: string }; ffmpeg: boolean; methods_available: string[]; default_method: string; statement: string; boundaries: string[] };
type Demo = { id: string; kind: string; label: string; object?: string; file?: string; note?: string; thumbs: string[]; frames?: { label: string; object: string }[] };
type Frame = { frame: number; drone_like: boolean; score: number; uncertain?: boolean; reason: string; thumbnail_png_b64: string; ground_truth?: string; ground_truth_object?: string };
type Analysis = { method: string; is_ai: boolean; frames: Frame[]; frames_flagged: number; frames_total: number; summary: string; limitations: string[]; analysis_id: string };
type Ev = { method: string; is_ai: boolean; dataset: string; precision: number; recall: number; f1: number; tp: number; fp: number; fn: number; tn: number; n: number; false_positive_rate: number;
  false_negative_rate: number; by_object: Record<string, { n: number; flagged_drone_like: number }>; uncertain: { file: string; object: string; score: number }[]; errors: { file: string; object: string; label: string; predicted: string; score: number }[] };

export function AirspaceLab() {
  const qc = useQueryClient();
  const caps = useQuery({ queryKey: ["vis-caps"], queryFn: () => get<Caps>("/api/visual/capabilities") });
  const demo = useQuery({ queryKey: ["vis-demo"], queryFn: () => get<Demo[]>("/api/visual/demo") });
  const ev = useQuery({ queryKey: ["vis-eval"], queryFn: () => get<Ev>("/api/visual/evaluation") });
  const hist = useQuery({ queryKey: ["vis-hist"], queryFn: () => get<{ id: string; ts: string; source: string; filename: string; frames: number; method: string; summary: string }[]>("/api/visual/history") });
  const [result, setResult] = useState<Analysis | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const analyze = useMutation({ mutationFn: (id: string) => post<Analysis>("/api/visual/analyze-demo", { item_id: id }), onSuccess: (r) => { setResult(r.data); qc.invalidateQueries({ queryKey: ["vis-hist"] }); } });
  const up = useMutation({ mutationFn: (f: File) => upload<Analysis>("/api/visual/upload", f), onSuccess: (r) => { setResult(r.data); qc.invalidateQueries({ queryKey: ["vis-hist"] }); } });
  const c = caps.data?.data;
  const e = ev.data?.data;
  return (
    <div className="space-y-4">
      <PageHeader title="Airspace Safety & Drone Visual Analysis Lab" icon={<ScanEye className="h-5 w-5" />}
        subtitle="Civilian safety research on prerecorded, authorized images and footage. Frames are analysed independently and the method that actually ran is always shown." />
      <Banner tone="amber"><b>Not a military, tracking, targeting or counter-drone system.</b> No trajectories, routes, intent assessment, pursuit or interception. Uploaded pixels are not stored; only a hash and the result summary.</Banner>
      {caps.error ? <ErrorBox error={caps.error} /> : null}
      <Card title="What this machine can actually do" subtitle="Detected at request time; nothing is downloaded">
        {!c ? <Skeleton className="h-24" /> : (
          <div className="space-y-3">
            <p className="text-sm" data-testid="vis-statement">{c.statement}</p>
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
              <Metric k="Local Qwen" v={c.qwen.model ? `${c.qwen.model}${c.qwen.quantization ? ` · ${c.qwen.quantization}` : ""}` : "not found"} />
              <Metric k="Qwen modality" v={c.qwen.modality} /><Metric k="Vision model" v={c.vision_model.found ? c.vision_model.model : "none installed"} />
              <Metric k="Method used" v={<Badge tone={c.default_method === "vision_model" ? "teal" : "amber"}>{c.default_method === "vision_model" ? "local vision model (AI)" : "classical baseline (not AI)"}</Badge>} />
              <Metric k="Context window" v={c.qwen.context_window} /><Metric k="Video sampling (ffmpeg)" v={c.ffmpeg ? "available" : "not installed"} />
              <Metric k="Runtime" v={c.qwen.runtime ?? "—"} /><Metric k="Vision search" v={c.vision_model.searched} />
            </div>
          </div>
        )}
      </Card>
      <div className="grid gap-4 xl:grid-cols-[1.2fr_1fr]">
        <Card title="Prerecorded examples (synthetic, labelled)" subtitle="Click to analyse. Ground truth is stored with each frame."
          actions={<><input ref={fileRef} type="file" className="hidden" accept=".png,.jpg,.jpeg,.webp,.gif,.mp4,.mov,.webm" onChange={(ev) => { const f = ev.target.files?.[0]; if (f) up.mutate(f); if (fileRef.current) fileRef.current.value = ""; }} data-testid="vis-upload" />
            <button className="btn btn-ghost text-xs" onClick={() => fileRef.current?.click()}><Upload className="h-4 w-4" />Upload footage</button></>}>
          {!demo.data ? <Skeleton className="h-64" /> : (
            <div className="grid grid-cols-3 gap-2 sm:grid-cols-4 lg:grid-cols-6" data-testid="vis-gallery">
              {demo.data.data.map((d) => (
                <button key={d.id} onClick={() => analyze.mutate(d.id)} className="group rounded-lg border border-token p-1 text-left hover:border-cyan/50" title={d.note ?? d.object}>
                  <img src={`data:image/png;base64,${d.thumbs[0]}`} alt={`${d.id} (${d.object ?? d.kind})`} className="aspect-[16/10] w-full rounded object-cover" />
                  <p className="mt-1 truncate text-[10px] text-faint">{d.id} · {d.kind === "clip" ? `clip, ${d.thumbs.length} frames` : d.object}</p>
                </button>
              ))}
            </div>
          )}
          {(analyze.error || up.error) ? <ErrorBox error={analyze.error ?? up.error} /> : null}
        </Card>
        <Card title="Evaluation against labelled data" subtitle={e ? `${e.dataset} · ${e.is_ai ? "AI model" : "classical baseline, not AI"}` : ""}>
          {!e ? <Skeleton className="h-48" /> : (
            <div className="space-y-3" data-testid="vis-eval">
              <div className="grid grid-cols-3 gap-2"><Metric k="Precision" v={num(e.precision)} /><Metric k="Recall" v={num(e.recall)} /><Metric k="F1" v={num(e.f1)} />
                <Metric k="False-positive rate" v={pct(e.false_positive_rate)} /><Metric k="False-negative rate" v={pct(e.false_negative_rate)} /><Metric k="Frames" v={e.n} /></div>
              <table className="ff"><thead><tr><th></th><th>Predicted drone</th><th>Predicted none</th></tr></thead>
                <tbody><tr><td>Drone</td><td className="num">{e.tp}</td><td className="num">{e.fn}</td></tr><tr><td>No drone</td><td className="num">{e.fp}</td><td className="num">{e.tn}</td></tr></tbody></table>
              <DataTable rows={Object.entries(e.by_object).map(([k, v]) => ({ object: k, ...v }))} columns={[{ key: "object", label: "Object in frame" }, { key: "n", label: "Frames" }, { key: "flagged_drone_like", label: "Flagged drone-like" }]} />
              <p className="text-xs muted">Uncertain classifications: {e.uncertain.length}. Errors: {e.errors.length} — the baseline confuses aircraft silhouettes with drones and misses distant drones.</p>
            </div>
          )}
        </Card>
      </div>
      {result && (
        <Card title="Analysis result" subtitle={result.summary} actions={<button className="btn btn-ghost text-xs" onClick={() => download(`/api/visual/report/${result.analysis_id}`, `${result.analysis_id}.md`)}><Download className="h-4 w-4" />Evidence report</button>}>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6" data-testid="vis-result">
            {result.frames.map((f) => (
              <div key={f.frame} className={`rounded-lg border p-1 ${f.drone_like ? "border-warn/60" : "border-token"}`}>
                <img src={`data:image/png;base64,${f.thumbnail_png_b64}`} alt={`frame ${f.frame}`} className="w-full rounded" />
                <p className="mt-1 text-[11px]">Frame {f.frame}: <b>{f.drone_like ? "drone-like" : "none"}</b> · score {f.score}{f.uncertain ? " · uncertain" : ""}</p>
                {f.ground_truth && <p className={`text-[10px] ${(f.ground_truth === "drone") === f.drone_like ? "text-pos" : "text-neg"}`}>ground truth: {f.ground_truth_object}</p>}
                <p className="text-[10px] text-faint">{f.reason}</p>
              </div>
            ))}
          </div>
          <ul className="mt-2 list-disc pl-4 text-xs muted">{result.limitations.map((l) => <li key={l}>{l}</li>)}</ul>
        </Card>
      )}
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Safety boundaries"><ul className="list-disc space-y-1 pl-4 text-sm">{c?.boundaries.map((b) => <li key={b}>{b}</li>)}</ul></Card>
        <Card title="Analysis history (stored: hash + summary only)">
          <DataTable rows={(hist.data?.data ?? []) as unknown as Record<string, unknown>[]} columns={[{ key: "ts", label: "When" }, { key: "source", label: "Source" }, { key: "filename", label: "Item" }, { key: "method", label: "Method" }, { key: "summary", label: "Result" }]} />
        </Card>
      </div>
    </div>
  );
}
