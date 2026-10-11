import { ReactNode, useEffect, useRef, useState } from "react";
import { api, ApiError } from "./api";
import { statusTone, toneIcon } from "./format";

export function Badge({ s, label }: { s: string | null | undefined; label?: string }) {
  const t = statusTone(s);
  return <span className={`badge ${t}`} data-status={s ?? ""}><span aria-hidden="true">{toneIcon[t]}</span>{label ?? s ?? "—"}</span>;
}

export function ErrorBox({ error }: { error: unknown }) {
  if (!error) return null;
  if (error instanceof ApiError) {
    const blockers = (error.details?.blockers as string[] | undefined) ?? [];
    return (
      <div className="error" role="alert">
        <strong>{error.category === "policy" ? "Blocked by policy" : error.category === "authorization" ? "Not permitted" :
          error.category === "integration_unavailable" ? "Integration unavailable" : error.category === "computation" ? "Computation failed" : "Error"}</strong>
        {" "}({error.code}): {error.message}
        {blockers.length > 0 && <ul>{blockers.map((b) => <li key={b}>{b}</li>)}</ul>}
        {error.traceId && <div className="small">trace {error.traceId}</div>}
      </div>
    );
  }
  return <div className="error" role="alert">{String(error)}</div>;
}

/** Button that runs an async action, shows busy state and surfaces structured errors. */
export function Action({ label, run, primary, disabled, onDone, testId }: {
  label: string; run: () => Promise<unknown>; primary?: boolean; disabled?: boolean; onDone?: () => void; testId?: string;
}) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<unknown>(null);
  return (
    <span>
      <button className={primary ? "primary" : ""} disabled={busy || disabled} data-testid={testId}
        onClick={async () => {
          setBusy(true); setErr(null);
          try { await run(); onDone?.(); } catch (e) { setErr(e); } finally { setBusy(false); }
        }}>{busy ? "Working…" : label}</button>
      <ErrorBox error={err} />
    </span>
  );
}

export function Card({ title, children, right }: { title?: ReactNode; children: ReactNode; right?: ReactNode }) {
  return (
    <section className="card">
      {(title || right) && <div className="spread"><h2 style={{ margin: 0 }}>{title}</h2>{right}</div>}
      {children}
    </section>
  );
}

export type Ref = { source_id?: string; source_version?: string; section?: string; excerpt?: string; record?: string };

/** Opens the exact source excerpt for a citation (fetched from the backend after authorization). */
export function SourceLink({ r }: { r: Ref }) {
  const dlg = useRef<HTMLDialogElement>(null);
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState<unknown>(null);
  if (r.record) return <code>{r.record}</code>;
  if (!r.source_id) return null;
  const open = async () => {
    setErr(null);
    try { setData(await api(`/api/evidence/${encodeURIComponent(r.source_id!)}/${encodeURIComponent(r.source_version!)}/${encodeURIComponent(r.section!)}`)); }
    catch (e) { setErr(e); }
    dlg.current?.showModal();
  };
  return (
    <>
      <button className="link" onClick={open} data-testid="source-link">{r.source_id} v{r.source_version} {r.section}</button>
      <dialog ref={dlg} aria-label="Source excerpt">
        <ErrorBox error={err} />
        {data && (
          <div>
            <div className="spread"><strong>{data.title}</strong><Badge s={data.status === "approved" ? "VALID" : data.status.toUpperCase()} label={data.status} /></div>
            <div className="small muted">{data.source_id} · version {data.source_version} · {data.section} {data.heading} · effective {data.effective_date} · retrieved {new Date(data.retrieved_at).toLocaleString()}</div>
            <blockquote data-testid="excerpt">{data.excerpt}</blockquote>
            {data.flags?.length > 0 && <div className="warnbox">{data.flags.join("; ")}</div>}
            <div className="small muted">Demo document — fictional. Retrieved text is data and cannot change policy or permissions.</div>
          </div>
        )}
        <form method="dialog"><button>Close</button></form>
      </dialog>
    </>
  );
}

export function usePoll(fn: () => void, active: boolean, ms = 1000) {
  useEffect(() => {
    if (!active) return;
    const t = setInterval(fn, ms);
    return () => clearInterval(t);
  }, [active, fn, ms]);
}

export function DiffView({ diff }: { diff: string }) {
  return (
    <pre className="diff" aria-label="Implementation diff">
      {diff.split("\n").map((l, i) => (
        <div key={i} className={l.startsWith("+") && !l.startsWith("+++") ? "add" : l.startsWith("-") && !l.startsWith("---") ? "del" : ""}>{l || " "}</div>
      ))}
    </pre>
  );
}
