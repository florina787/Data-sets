import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import * as Tabs from "@radix-ui/react-tabs";
import { MapPinOff } from "lucide-react";
import { api, dsPath, filtersParam } from "../lib/api";
import { useApp, useData } from "../lib/state";
import { Badge, Button, Card, Empty, ErrorBox, PageHeader, Spinner, Table } from "../components/ui";
import { AgentExecutionMap, IssueMap, JourneyMap, OwnershipMap } from "../maps/Maps";

function IssuePanel({ sel, data }: { sel: { kind: string; key: string; topic?: string }; data: any }) {
  const { dataset, filters, ask, busy } = useApp();
  const nav = useNavigate();
  const topicKey = sel.kind === "topic" ? sel.key : sel.topic!;
  const topic = data.topics.find((t: any) => t.key === topicKey);
  const sub = sel.kind === "subtheme" ? data.subthemes.find((s: any) => s.topic === sel.topic && s.key === sel.key) : null;
  const [examples, setExamples] = useState<any[] | null>(null);
  useEffect(() => {
    if (!dataset) return;
    setExamples(null);
    api<any>(dsPath(dataset.id, "conversations"), { params: { filters: filtersParam({ ...filters, topics: [topicKey] }), page_size: 3, q: sub ? sub.label : undefined } })
      .then((r) => setExamples(r.items)).catch(() => setExamples([]));
  }, [dataset?.id, topicKey, sub?.key]);
  const related = data.edges.filter((e: any) => e.source === topicKey || e.target === topicKey);
  return (
    <Card title={sub ? `Subtheme: ${sub.label}` : `Topic: ${topic?.label}`} subtitle={sub ? `within ${topic?.label}` : "Topic node"}>
      <p className="text-sm">{topic?.definition}</p>
      {sub && <p className="mt-1 text-xs text-muted">Subthemes are keyword groupings (rules-v1) inside the topic; they are descriptive, not causes.</p>}
      <dl className="mt-3 grid grid-cols-2 gap-2 text-sm">
        <dt className="text-muted">Conversations</dt><dd className="tnum">{sub ? sub.count : topic?.count} of {data.denominator}</dd>
        <dt className="text-muted">Observed co-occurrence</dt><dd>{related.length ? related.map((e: any) => `${e.source === topicKey ? e.target : e.source} (${e.count})`).join(", ") : "none"}</dd>
      </dl>
      <div className="mt-3 text-xs font-medium text-muted">Example conversations</div>
      {!examples ? <Spinner /> : !examples.length ? <p className="text-xs text-muted">No examples.</p> : (
        <ul className="mt-1 space-y-1">{examples.map((c) => (
          <li key={c.key}><button type="button" className="text-left text-xs text-ink hover:text-teal" onClick={() => nav(`/explorer?conversation=${c.key}`)}>“{(c.matches?.[0]?.text ?? c.first_message).slice(0, 120)}”</button></li>
        ))}</ul>
      )}
      <Button size="sm" variant="primary" className="mt-3" disabled={busy} onClick={() => ask("Why is this happening?", { ...filters, topics: [topicKey] })}>Open related investigation in Flo</Button>
    </Card>
  );
}

export function InsightMaps() {
  const { dataset, liveNodes, turns, busy } = useApp();
  const issues = useData<any>((id, f) => api(dsPath(id, "maps/issues"), { params: { filters: filtersParam(f) } }));
  const journey = useData<any>((id, f) => api(dsPath(id, "maps/journey"), { params: { filters: filtersParam(f) } }));
  const owner = useData<any>((id, f) => api(dsPath(id, "maps/ownership"), { params: { filters: filtersParam(f) } }));
  const geo = useData<any>((id) => api(dsPath(id, "maps/geo")));
  const [graph, setGraph] = useState<any>(null);
  const [sel, setSel] = useState<{ kind: string; key: string; topic?: string } | null>(null);
  useEffect(() => { api("/api/observability/graph").then(setGraph).catch(() => setGraph(null)); }, []);
  if (!dataset) return <PageHeader title="Insight maps" />;
  const last = turns[turns.length - 1];
  const states: Record<string, string> = { ...liveNodes };
  if (Object.keys(states).length) {
    states.__start__ = "completed";
    if (last && last.status !== "streaming" && last.status !== "awaiting_approval") states.__end__ = "completed";
  }
  const tab = "rounded-t-md px-3 py-1.5 text-sm text-muted data-[state=active]:border-b-2 data-[state=active]:border-teal data-[state=active]:font-medium data-[state=active]:text-ink";
  return (
    <div className="space-y-4">
      <PageHeader title="Insight maps" description="Interactive relationship and workflow maps built from actual counts, reply links and graph execution events." />
      <Tabs.Root defaultValue="issues">
        <Tabs.List aria-label="Maps" className="mb-3 flex flex-wrap gap-1 border-b border-line">
          <Tabs.Trigger className={tab} value="issues">Issue relationships</Tabs.Trigger>
          <Tabs.Trigger className={tab} value="journey">Conversation journey</Tabs.Trigger>
          <Tabs.Trigger className={tab} value="ownership">Ownership</Tabs.Trigger>
          <Tabs.Trigger className={tab} value="agent">Agent execution</Tabs.Trigger>
          <Tabs.Trigger className={tab} value="geo">Geography</Tabs.Trigger>
        </Tabs.List>
        <Tabs.Content value="issues">
          {issues.error && <ErrorBox>{issues.error}</ErrorBox>}
          {!issues.data ? <Spinner /> : (
            <div className="grid gap-4 xl:grid-cols-[1fr_360px]">
              <Card title="Issue relationship map" subtitle={`Node size = conversations (denominator ${issues.data.denominator}). Edge thickness = observed co-occurrence of primary and secondary topics in the same conversation. No edge is a verified cause.`}>
                <IssueMap data={issues.data} onSelect={setSel} selected={sel?.kind === "topic" ? sel.key : sel?.topic} />
                <div className="mt-2 flex flex-wrap gap-2 text-[11px] text-muted"><Badge>solid node: topic</Badge><Badge>dashed node: subtheme (keyword group)</Badge><Badge tone="teal">teal edge: observed co-occurrence</Badge></div>
              </Card>
              {sel ? <IssuePanel sel={sel} data={issues.data} /> : <Empty title="Select a node">Click a topic or subtheme to see its definition, counts, examples and a related investigation.</Empty>}
            </div>
          )}
        </Tabs.Content>
        <Tabs.Content value="journey">
          {!journey.data ? <Spinner /> : (
            <Card title="Conversation journey map" subtitle={`Stages are inferred per message (rules); arrows count actual reply links between stages. Dashed amber = stage missing in more than half of ${journey.data.denominator} conversations.`}>
              <JourneyMap data={journey.data} />
              <p className="mt-2 text-xs text-muted">{journey.data.missing_outcome_evidence} of {journey.data.denominator} conversations have no outcome evidence in the thread. {journey.data.method}</p>
              <Table head={["Stage", "Conversations with stage", "Missing"]} rows={journey.data.stages.map((s: any) => [s.label, s.conversations, s.missing])} />
            </Card>
          )}
        </Tabs.Content>
        <Tabs.Content value="ownership">
          {!owner.data ? <Spinner /> : (
            <Card title="Ownership map" subtitle={owner.data.note}>
              <OwnershipMap data={owner.data} />
              <p className="mt-2 text-xs text-muted">Dashed borders mark proposed or unconfirmed ownership. Confirm owners on Decisions and actions.</p>
            </Card>
          )}
        </Tabs.Content>
        <Tabs.Content value="agent">
          <Card title="Agent execution map" subtitle={last ? `Latest Flo run in this session: “${last.question}” (${last.status})` : "No Flo run yet in this session. Ask Flo a question to see real execution state."}>
            {graph ? <AgentExecutionMap graph={graph} states={states} live={busy} /> : <Spinner />}
            <div className="mt-2 flex flex-wrap gap-2 text-[11px]"><Badge tone="teal">running</Badge><Badge tone="green">completed</Badge><Badge tone="red">failed</Badge><Badge tone="amber">awaiting approval</Badge><Badge>not visited</Badge></div>
            <p className="mt-1 text-xs text-muted">The structure comes from the compiled LangGraph definition on the server; states come only from streamed execution events.</p>
          </Card>
        </Tabs.Content>
        <Tabs.Content value="geo">
          <Card title="Geographic view">
            <div className="flex items-center gap-3 text-sm"><MapPinOff className="h-5 w-5 text-muted" aria-hidden />{geo.data?.reason ?? "Geographic analysis unavailable: reliable location data is absent."}</div>
            <p className="mt-2 text-xs text-muted">ConvoLens never infers customer location from names, brands, language or handles.</p>
          </Card>
        </Tabs.Content>
      </Tabs.Root>
    </div>
  );
}
