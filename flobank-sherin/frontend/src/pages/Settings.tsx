import { useState } from "react";
import { SherinAvatar, SHERIN_IMAGE } from "../components/SherinAvatar";
import { Badge, Button, Card, ErrorBox, Note, PageHeader, Table } from "../components/ui";
import { RoleSwitcher } from "../components/Layout";
import { api, useApi } from "../lib/api";
import { useApp } from "../lib/store";

export default function Settings() {
  const { role } = useApp();
  const fx = useApi<any>("/fx/rates");
  const bl = useApi<any[]>("/baselines");
  const meta = useApi<any>("/meta");
  const [quote, setQuote] = useState("INR");
  const [rate, setRate] = useState("");
  const [source, setSource] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [edit, setEdit] = useState<Record<string, { h: string; r: string }>>({});
  const addRate = async () => { setErr(null); try { await api("/fx/rates", { method: "POST", body: { quote, rate: Number(rate), source } }); setRate(""); setSource(""); fx.reload(); } catch (e: any) { setErr(e.message); } };
  const saveBl = async (wf: string) => { setErr(null); const e = edit[wf]; try { await api(`/baselines/${wf}`, { method: "PUT", body: { hours_per_task: Number(e.h), hourly_rate_usd: Number(e.r), source: `Edited in Settings by ${role}` } }); bl.reload(); setEdit((x) => { const c = { ...x }; delete c[wf]; return c; }); } catch (ex: any) { setErr(ex.message); } };
  return (
    <div>
      <PageHeader title="Settings" subtitle="Currency and exchange rates, human baselines, role, model and data configuration." />
      <ErrorBox error={err} />
      <div className="grid gap-4 xl:grid-cols-2">
        <Card className="p-5">
          <h2 className="font-display text-xl font-semibold text-flo-900">Identity (demo)</h2>
          <div className="mt-2"><RoleSwitcher /></div>
          <Note>Roles are selected here for demonstration. Production should use Entra ID (OIDC) group claims; see docs/STATUS.md.</Note>
          <h2 className="mt-5 font-display text-xl font-semibold text-flo-900">Sherin's portrait</h2>
          <div className="mt-2 flex items-center gap-4"><SherinAvatar size="xl" /><div className="text-sm text-muted">Every screen loads one asset: <code>{SHERIN_IMAGE}</code>. Place the approved Ghibli-style image at <code>frontend/public{SHERIN_IMAGE}</code>. No substitute face is generated.</div></div>
          <h2 className="mt-5 font-display text-xl font-semibold text-flo-900">Runtime</h2>
          {meta.data && <ul className="mt-1 space-y-1 text-sm"><li>Mode: <Badge tone="gold">{meta.data.mode}</Badge></li><li>Database: <Badge>{meta.data.database}</Badge></li>
            <li>Local Qwen (Ollama): {meta.data.llm.available ? <Badge tone="green">available · {meta.data.llm.model}</Badge> : <Badge tone="amber">{meta.data.llm.reason}</Badge>}</li></ul>}
        </Card>
        <Card className="p-5">
          <h2 className="font-display text-xl font-semibold text-flo-900">Exchange rates (base USD)</h2>
          <Table dense columns={[{ key: "quote", label: "Pair", render: (r) => `USD/${r.quote}` }, { key: "rate", label: "Rate", align: "right" }, { key: "source", label: "Source" }, { key: "as_of", label: "As of" }, { key: "data_class", label: "Class" }]} rows={fx.data?.current ?? []} />
          <div className="mt-3 flex flex-wrap items-end gap-2">
            <select aria-label="Quote currency" value={quote} onChange={(e) => setQuote(e.target.value)} className="rounded-full border border-line px-3 py-1.5 text-sm"><option>INR</option><option>CAD</option></select>
            <input aria-label="Rate" value={rate} onChange={(e) => setRate(e.target.value)} placeholder="Rate" className="w-24 rounded-full border border-line px-3 py-1.5 text-sm" />
            <input aria-label="Source" value={source} onChange={(e) => setSource(e.target.value)} placeholder="Source (e.g. Treasury desk 16:00)" className="min-w-48 flex-1 rounded-full border border-line px-3 py-1.5 text-sm" />
            <Button onClick={addRate} disabled={!rate || source.length < 3}>Set rate</Button>
          </div>
          <details className="mt-3 text-sm"><summary className="cursor-pointer font-semibold text-flo-800">Conversion history ({fx.data?.history.length ?? 0})</summary>
            <Table dense columns={[{ key: "quote", label: "Pair" }, { key: "rate", label: "Rate", align: "right" }, { key: "as_of", label: "As of" }, { key: "source", label: "Source" }, { key: "created_by", label: "By" }]} rows={fx.data?.history ?? []} /></details>
        </Card>
        <Card className="p-5 xl:col-span-2">
          <h2 className="font-display text-xl font-semibold text-flo-900">Human-only baselines</h2>
          <Note>Independently configured by Finance. Changes apply to tasks completed afterwards; historical tasks keep the baseline that applied when they ran.</Note>
          <Table dense columns={[{ key: "label", label: "Workflow" }, { key: "department", label: "Department" },
            { key: "h", label: "Hours / task", align: "right", render: (r) => edit[r.workflow_type] ? <input aria-label={`${r.label} hours`} className="w-16 rounded border border-line px-1 text-right" value={edit[r.workflow_type].h} onChange={(e) => setEdit({ ...edit, [r.workflow_type]: { ...edit[r.workflow_type], h: e.target.value } })} /> : r.hours_per_task },
            { key: "r", label: "Rate USD/h", align: "right", render: (r) => edit[r.workflow_type] ? <input aria-label={`${r.label} rate`} className="w-16 rounded border border-line px-1 text-right" value={edit[r.workflow_type].r} onChange={(e) => setEdit({ ...edit, [r.workflow_type]: { ...edit[r.workflow_type], r: e.target.value } })} /> : r.hourly_rate_usd },
            { key: "source", label: "Source" }, { key: "data_class", label: "Class" },
            { key: "a", label: "", render: (r) => edit[r.workflow_type] ? <Button variant="primary" onClick={() => saveBl(r.workflow_type)}>Save</Button> : <Button variant="ghost" onClick={() => setEdit({ ...edit, [r.workflow_type]: { h: String(r.hours_per_task), r: String(r.hourly_rate_usd) } })}>Edit</Button> }]} rows={bl.data ?? []} />
        </Card>
      </div>
    </div>
  );
}
