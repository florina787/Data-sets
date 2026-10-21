import { useEffect, useState } from "react";
import { api, sessionHeaders } from "../lib/api";
import { useApp } from "../lib/state";
import { Badge, Card, Empty, PageHeader } from "../components/ui";
import { FloChat } from "../assistant/Flo";
import { AgentExecutionMap } from "../maps/Maps";
import { fmtDate } from "../lib/format";
import { Markdown } from "../lib/markdown";

export function AskFlo() {
  const { turns, liveNodes, busy } = useApp();
  const [graph, setGraph] = useState<any>(null);
  const [saved, setSaved] = useState<any[]>([]);
  const [open, setOpen] = useState<any>(null);
  useEffect(() => { api("/api/observability/graph").then(setGraph).catch(() => undefined); }, []);
  useEffect(() => {
    sessionHeaders().then((h) => api<any>("/api/flo/investigations", { headers: h })).then((r) => setSaved(r.investigations)).catch(() => undefined);
  }, [turns.length, busy]);
  const last = turns[turns.length - 1];
  const states: Record<string, string> = { ...liveNodes };
  if (Object.keys(states).length) states.__start__ = "completed";
  if (last && !["streaming", "awaiting_approval"].includes(last.status)) states.__end__ = "completed";
  const evidence = last?.response?.evidence ?? [];
  return (
    <div className="space-y-4">
      <PageHeader title="Ask Flo" description="Full investigation workspace: chat, evidence and the actual execution trace." />
      <div className="grid gap-4 2xl:grid-cols-[minmax(0,1fr)_420px]">
        <Card className="flex h-[78vh] flex-col overflow-hidden [&>div]:flex [&>div]:min-h-0 [&>div]:flex-1 [&>div]:flex-col [&>div]:p-0"><FloChat variant="page" /></Card>
        <div className="space-y-4">
          <Card title="Evidence for the latest answer" subtitle={evidence.length ? `${evidence.length} validated messages` : undefined}>
            {!evidence.length ? <Empty title="No evidence yet">Evidence appears after Flo answers an analytical question.</Empty> : (
              <ul className="space-y-2 text-xs">{evidence.map((e: any) => (
                <li key={e.id}><Badge tone="teal">{e.ref}</Badge> <Badge>{e.role}</Badge> “{e.quote}” <a className="text-teal underline" href={`/explorer?dataset=${last?.datasetId}&conversation=${e.conversation_key}&message=${e.message_id}`}>open</a></li>
              ))}</ul>
            )}
          </Card>
          <Card title="Execution trace" subtitle="Actual graph nodes and tools for the latest run">
            {graph && <AgentExecutionMap graph={graph} states={states} live={busy} />}
            {last && (
              <ol className="mt-3 space-y-1 text-xs">
                {last.nodeOrder.map((n) => <li key={n}><Badge tone={last.nodes[n] === "failed" ? "red" : last.nodes[n] === "awaiting_approval" ? "amber" : last.nodes[n] === "completed" ? "green" : "teal"}>{last.nodes[n]}</Badge> {n}</li>)}
              </ol>
            )}
          </Card>
          <Card title="Saved investigations" subtitle="This browser session only">
            {!saved.length ? <p className="text-xs text-muted">None saved yet. Use “Save investigation” under an answer.</p> : (
              <ul className="divide-y divide-line text-sm">{saved.map((s) => (
                <li key={s.id} className="py-1.5"><button type="button" className="text-left hover:text-teal" onClick={() => setOpen(s)}>{s.title}</button><div className="text-[11px] text-muted">{fmtDate(s.created_at)}</div></li>
              ))}</ul>
            )}
          </Card>
        </div>
      </div>
      {open && (
        <Card title={`Saved: ${open.title}`} actions={<button type="button" className="text-xs text-teal" onClick={() => setOpen(null)}>Close</button>}>
          <Markdown text={open.response.text ?? ""} />
        </Card>
      )}
    </div>
  );
}
