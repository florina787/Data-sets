import { useState } from "react";
import { Page } from "../components/Layout";
import { DomeMark } from "../components/Logo";
import { Badge, Button, DemoLabel, Empty, ErrorBox, Loading, cx } from "../components/ui";
import { api } from "../lib/api";
import { fmtDateTime } from "../lib/format";
import { useAsync } from "../lib/useAsync";

interface Conn { id: string; platform: string; connector_type: string; display_name: string; status: string; capabilities: string[]; verified_at: string | null; is_demo: boolean }
interface EvPage { total: number; counts: { source_system: string; kind: string; count: number }[]; items: { id: string; kind: string; observed_at: string; summary: string; source_system: string; source_ref: string; content_hash: string; is_demo: boolean }[] }
const KINDS = ["", "log", "metric", "deployment", "config_change", "trace", "status"];
const PAGE = 12;

export default function Sources() {
  const conns = useAsync(() => api<Conn[]>("/connections"));
  const [kind, setKind] = useState("");
  const [offset, setOffset] = useState(0);
  const ev = useAsync(() => api<EvPage>(`/evidence?limit=${PAGE}&offset=${offset}${kind ? `&kind=${kind}` : ""}`), [kind, offset]);

  return (
    <div className="bg-gradient-to-b from-dome-50 to-canvas">
      <Page>
        <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
          <div className="flex min-h-[220px] flex-col justify-center rounded-[26px] bg-[#E6E7FB] p-8">
            <div className="flex items-center gap-3"><DomeMark size={44} /><span className="font-display text-3xl font-medium tracking-tight">sources</span></div>
            <p className="mt-4 max-w-lg text-sm text-ink-soft">Every conclusion traces back to a record collected from a named source, with its original identifier, collection time and a content hash that detects later edits.</p>
          </div>
          <div className="relative flex min-h-[220px] items-center justify-center overflow-hidden rounded-[26px] bg-gradient-to-br from-white to-[#DCDDEE]">
            <div className="h-40 w-40 rounded-full border border-white bg-white/40 shadow-[inset_0_2px_12px_rgba(255,255,255,0.9),0_30px_60px_-20px_rgba(59,61,170,0.45)] backdrop-blur-md" />
            <div className="absolute"><DomeMark size={72} /></div>
          </div>
        </div>

        <h2 className="mt-10 font-display text-xl font-semibold">Connected sources</h2>
        {conns.error && <ErrorBox error={conns.error} />}
        {conns.loading && <Loading />}
        <div className="mt-3 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {conns.data?.map((c) => {
            const counts = (ev.data?.counts ?? []).filter((x) => x.source_system === c.connector_type);
            return (
              <article key={c.id} className="rounded-[22px] border border-white bg-white/60 p-5 shadow-tile backdrop-blur">
                <div className="flex items-center justify-between"><span className="font-mono text-[11px] uppercase text-dome-600">{c.connector_type}</span><Badge value={c.status} /></div>
                <h3 className="mt-2 font-medium">{c.display_name}</h3>
                {c.is_demo && <DemoLabel className="mt-2 inline-block" />}
                <div className="mt-3 flex flex-wrap gap-1">{c.capabilities.map((cap) => <span key={cap} className="rounded-md bg-dome-50 px-1.5 py-0.5 font-mono text-[10px] text-dome-700">{cap}</span>)}</div>
                <div className="mt-4 grid grid-cols-3 gap-2 text-center">
                  {counts.map((x) => <div key={x.kind} className="rounded-xl bg-white p-2"><div className="font-display text-lg font-semibold">{x.count}</div><div className="text-[10px] text-ink-mute">{x.kind}</div></div>)}
                </div>
                {!counts.length && <p className="mt-3 text-xs text-ink-mute">No evidence collected yet. Run an RCA.</p>}
                <p className="mt-3 text-[11px] text-ink-mute">Verified {c.verified_at ? fmtDateTime(c.verified_at) : "never"}</p>
              </article>
            );
          })}
        </div>

        <div className="mt-10 flex flex-wrap items-center gap-2">
          <h2 className="mr-auto font-display text-xl font-semibold">Evidence explorer</h2>
          {KINDS.map((k) => (
            <button key={k || "all"} onClick={() => { setKind(k); setOffset(0); }} aria-pressed={kind === k}
              className={cx("rounded-full border px-3 py-1 text-xs", kind === k ? "border-dome-500 bg-dome-500 text-white" : "border-dome-100 bg-white text-ink-soft")}>{k || "all"}</button>
          ))}
        </div>
        {ev.error && <ErrorBox error={ev.error} />}
        {ev.loading && <Loading />}
        {ev.data && ev.data.total === 0 && <Empty>No evidence yet. Investigations collect it from the connected sources.</Empty>}
        {ev.data && ev.data.total > 0 && (
          <div className="mt-3 overflow-x-auto rounded-2xl border border-white bg-white/70">
            <table className="w-full text-left text-sm">
              <thead className="text-[11px] uppercase tracking-wider text-ink-mute"><tr><th className="p-3">Observed</th><th>Kind</th><th>Summary</th><th>Source ref</th><th>sha256</th></tr></thead>
              <tbody>
                {ev.data.items.map((e) => (
                  <tr key={e.id} className="border-t border-dome-100">
                    <td className="whitespace-nowrap p-3 text-xs">{fmtDateTime(e.observed_at)}</td>
                    <td><span className="font-mono text-xs text-dome-600">{e.kind}</span></td>
                    <td className="max-w-lg pr-3">{e.summary}</td>
                    <td className="font-mono text-xs">{e.source_system}:{e.source_ref}</td>
                    <td className="font-mono text-xs text-ink-mute">{e.content_hash.slice(0, 10)}…</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="flex items-center justify-between p-3 text-xs text-ink-soft">
              <span>{offset + 1}–{Math.min(offset + PAGE, ev.data.total)} of {ev.data.total}</span>
              <span className="flex gap-2">
                <Button kind="ghost" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>Previous</Button>
                <Button kind="ghost" disabled={offset + PAGE >= ev.data.total} onClick={() => setOffset(offset + PAGE)}>Next</Button>
              </span>
            </div>
          </div>
        )}
      </Page>
    </div>
  );
}
