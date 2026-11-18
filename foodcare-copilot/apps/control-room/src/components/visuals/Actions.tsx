import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, apiBlobUrl } from "../../api";
import { useApp } from "../../context";
import { VisualList } from "./VisualRenderer";

export type UiAction = { type: string; label: string; url?: string; geo?: Record<string, string>; sites?: string[]; agent_run_id?: string };

const XRAY = "xray:open";
export function openXray(agentRunId: string) {
  window.dispatchEvent(new CustomEvent(XRAY, { detail: agentRunId }));
}

/** Download a server-generated file with the session token (a plain link can't send it). */
export async function download(url: string, setMsg: (m: string) => void) {
  setMsg("Preparing…");
  try {
    const href = await apiBlobUrl(url);
    const a = document.createElement("a");
    a.href = href;
    a.download = url.split("/").pop()!.split("?")[0];
    document.body.appendChild(a);
    a.click();
    a.remove();
    setMsg("Downloaded");
  } catch (e) {
    setMsg(`Could not download: ${(e as Error).message}`);
  }
}

/** Only the fixed, validated action types from the server are rendered; nothing else can run. */
export function ActionBar({ actions }: { actions: UiAction[] }) {
  const navigate = useNavigate();
  const { setGeo } = useApp();
  const [msg, setMsg] = useState<Record<number, string>>({});
  if (!actions?.length) return null;
  const run = (a: UiAction, i: number) => {
    const set = (m: string) => setMsg((s) => ({ ...s, [i]: m }));
    if (a.type === "download" || a.type === "open_motion") return a.url && download(a.url, set);
    if (a.type === "open_globe") {
      const node = a.geo?.node ?? a.sites?.[0];
      setGeo({ country: a.geo?.country, node });
      return navigate("/network");
    }
    if (a.type === "open_xray" && a.agent_run_id) return openXray(a.agent_run_id);
    if ((a.type === "open_page" || a.type === "open_containment") && a.url) return navigate(a.url);
  };
  return (
    <div className="mt-3 flex flex-wrap gap-2" data-testid="answer-actions">
      {actions.map((a, i) => (
        <span key={i} className="inline-flex items-center gap-1">
          <button className={a.type === "download" ? "btn-primary text-xs" : "btn-ghost text-xs"} onClick={() => run(a, i)}>
            {a.type === "download" ? "⤓ " : a.type === "open_globe" ? "◍ " : a.type === "open_xray" ? "⌁ " : ""}{a.label}
          </button>
          {msg[i] && <span className="text-[11px] text-ink-muted" role="status">{msg[i]}</span>}
        </span>
      ))}
    </div>
  );
}

/** Enterprise X-Ray: the recorded, sanitised path of one answer. */
export function XrayPanel() {
  const [id, setId] = useState<string | null>(null);
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    const on = (e: Event) => setId((e as CustomEvent).detail);
    window.addEventListener(XRAY, on);
    return () => window.removeEventListener(XRAY, on);
  }, []);
  useEffect(() => {
    setData(null);
    setErr(null);
    if (id) api(`/api/xray/${id}`).then(setData).catch((e) => setErr((e as Error).message));
  }, [id]);
  useEffect(() => {
    if (!id) return;
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setId(null);
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [id]);
  if (!id) return null;
  const flow = data && {
    kind: "flow", title: "How Jerry produced this answer", provenance: "operational_record",
    nodes: data.steps.map((s: any) => ({ id: s.id, label: s.label, group: s.kind === "tool" ? "tools" : s.kind === "input" ? "input" : s.kind === "output" ? "output" : s.kind, state: s.status ?? (s.duration_ms != null ? `${s.duration_ms} ms` : undefined), detail: s.detail })),
    edges: data.steps.slice(1).map((s: any, i: number) => {
      const prev = data.steps[i];
      return { source: s.kind === "tool" && prev.kind === "tool" ? "policy" : prev.id, target: s.id };
    }).concat(data.steps.filter((s: any) => s.kind === "tool").map((s: any) => ({ source: s.id, target: "evidence" }))),
    caption: data.note,
  };
  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/50" onClick={() => setId(null)}>
      <aside role="dialog" aria-modal="true" aria-labelledby="xray-title" onClick={(e) => e.stopPropagation()} className="h-full w-full max-w-3xl overflow-y-auto border-l border-surface-line bg-midnight p-6 shadow-2xl">
        <div className="flex items-start justify-between gap-3">
          <div><div className="eyebrow">Enterprise X-Ray</div><h2 id="xray-title" className="mt-1 text-xl font-semibold text-ink">Show how Jerry knows</h2></div>
          <button className="btn-ghost" onClick={() => setId(null)} autoFocus>Close</button>
        </div>
        {err && <p className="mt-4 text-sm text-brick-700">{err}</p>}
        {!data && !err && <p className="mt-4 text-sm text-ink-muted">Loading the trace…</p>}
        {data && (
          <>
            <p className="mt-2 text-sm text-ink-muted">Real recorded execution · {data.duration_ms} ms · status {data.status}. Arguments, prompts and payloads are withheld.</p>
            <VisualList visuals={[flow]} />
            <ol className="mt-4 space-y-2 text-sm">{data.steps.map((s: any) => (
              <li key={s.id} className="rounded-lg border border-surface-line bg-elevated/50 px-3 py-2">
                <div className="flex flex-wrap items-center justify-between gap-2"><span className="font-medium text-ink">{s.label}</span><span className="text-xs text-ink-faint">{s.kind}{s.duration_ms != null ? ` · ${s.duration_ms} ms` : ""}{s.source_state ? ` · source ${s.source_state.replace(/_/g, " ")}` : ""}</span></div>
                {s.detail && <p className="mt-1 text-xs text-ink-muted">{s.detail}</p>}
              </li>
            ))}</ol>
            <h3 className="mt-5 text-sm font-semibold text-ink">External systems (verified states)</h3>
            <ul className="mt-2 flex flex-wrap gap-2 text-xs">{data.external_systems.map((x: any) => <li key={x.id} className="chip border-surface-line text-ink-muted">{x.name}: {x.state.replace(/_/g, " ")}</li>)}</ul>
          </>
        )}
      </aside>
    </div>
  );
}

/** Subtle Privacy Shield and data-status indicators for an answer. */
export function PolicyChips({ a }: { a: any }) {
  if (!a.policy) return null;
  const p = a.policy;
  const chips = [
    ["Policy applied", "border-teal/60 text-teal-soft", "The server applied tenant isolation and field classification before this answer."],
    ...(p.restricted_excluded ? [["Restricted fields excluded", "border-champagne/60 text-champagne", "Personal, banking or credential fields were removed on the server."]] : []),
    ...(p.aggregated ? [["Aggregated data", "border-champagne/60 text-champagne", "Confidential values are shown as bands or summaries."]] : []),
    ...(p.approved_sources?.length ? [[`Approved sources: ${p.approved_sources.length}`, "border-surface-line text-ink-muted", p.approved_sources.join(", ")]] : []),
    ...(a.data_status && a.data_status !== "none" ? [[`Data: ${a.data_status.replace(/_/g, " ")}`, "border-surface-line text-ink-muted", "Provenance of the figures in this answer"]] : []),
  ];
  return (
    <div className="mt-2 flex flex-wrap gap-1.5" data-testid="policy-chips">
      {chips.map(([t, cls, title]) => <span key={t} className={`chip ${cls}`} title={title}>{t}</span>)}
    </div>
  );
}
