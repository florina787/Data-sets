import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { ShieldCheck } from "lucide-react";
import { Plot } from "../components/Plot";
import { Badge, Button, Card, ChartCard, DecisionBadge, ErrorBox, Note, PageHeader, Spinner, Table } from "../components/ui";
import { ApprovalCard } from "../components/ApprovalCard";
import { api, useApi } from "../lib/api";
import { money, SERIES } from "../lib/format";

export default function Guardian() {
  const [sp, setSp] = useSearchParams();
  const list = useApi<any[]>("/guardian/proposals");
  const sel = sp.get("proposal") ?? "TP-1001";
  const [res, setRes] = useState<any>(null);
  const [approval, setApproval] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { setApproval(null); setErr(null); api(`/guardian/proposals/${sel}/evaluate`, { method: "POST", body: { advisory: [] } }).then(setRes).catch((e) => setErr(e.message)); }, [sel]);
  const request = async () => { try { setApproval(await api(`/guardian/proposals/${sel}/request-approval`, { method: "POST" })); } catch (e: any) { setErr(e.message); } };
  return (
    <div>
      <PageHeader title="Investment Judgment Center" subtitle="Sherin Guardian independently evaluates proposals with deterministic controls. A PASS is not authorization to trade." />
      <div className="grid gap-4 xl:grid-cols-[340px_1fr]">
        <Card className="p-3">
          <h2 className="mb-2 px-1 font-display text-lg font-semibold text-flo-900">Proposals</h2>
          <ul className="space-y-1.5">{(list.data ?? []).map((p) => (
            <li key={p.id}><button type="button" onClick={() => setSp({ proposal: p.id })} className={`w-full rounded-xl border p-2.5 text-left text-sm transition ${sel === p.id ? "border-flo-600 bg-flo-50" : "border-line hover:bg-flo-50"}`}>
              <div className="flex items-center justify-between"><strong>{p.id}</strong><DecisionBadge d={p.decision} /></div>
              <div>{p.side} {p.issuer}</div><div className="text-xs text-muted">{p.portfolio_id} · {money(p.notional_usd)} {p.material && "· material"}</div></button></li>))}</ul>
        </Card>
        <div className="space-y-4">
          <ErrorBox error={err} />
          {!res ? <Spinner /> : (
            <>
              <Card className="p-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div><div className="flex items-center gap-2"><ShieldCheck className="h-6 w-6 text-flo-700" /><h2 className="font-display text-2xl font-semibold text-flo-900">{res.proposal_id} · {res.portfolio}</h2></div>
                    <p className="mt-1 text-sm text-muted">{res.meaning}</p></div>
                  <div className="text-right"><div className="text-[11px] uppercase text-muted">Guardian decision</div><div className="mt-1 scale-125"><DecisionBadge d={res.decision} /></div></div>
                </div>
                <div className="mt-3 grid gap-2 sm:grid-cols-3">
                  <div className="rounded-xl bg-flo-50 p-3"><div className="text-[10px] uppercase text-muted">Portfolio NAV</div><div className="font-display text-xl font-semibold">{money(res.risk.nav_usd)}</div></div>
                  <div className="rounded-xl bg-flo-50 p-3"><div className="text-[10px] uppercase text-muted">Post-trade volatility</div><div className="font-display text-xl font-semibold">{res.risk.post_trade_volatility !== null ? `${(res.risk.post_trade_volatility * 100).toFixed(2)}%` : "—"}</div></div>
                  <div className="rounded-xl bg-flo-50 p-3"><div className="text-[10px] uppercase text-muted">1-day 99% VaR (parametric)</div><div className="font-display text-xl font-semibold">{money(res.risk.var_99_1d_usd)}</div></div>
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  <Button onClick={request}>Request manager approval</Button>
                  <Badge tone="slate">Mandatory blocks cannot be overridden by any model or approver</Badge>
                </div>
                {approval && <div className="mt-3"><ApprovalCard a={approval} onChange={setApproval} /></div>}
                <Note>{res.note}</Note>
              </Card>
              <ChartCard title="Policy controls" subtitle="Pre-trade checks, concentration, liquidity, credit, ESG, market risk, evidence, materiality">
                <Table dense columns={[{ key: "name", label: "Control" }, { key: "status", label: "Result", render: (r) => <DecisionBadge d={r.status} /> }, { key: "mandatory", label: "Mandatory", render: (r) => (r.mandatory ? "yes" : "advisory") },
                  { key: "detail", label: "Evidence" }]} rows={res.checks} />
              </ChartCard>
              <div className="grid gap-4 xl:grid-cols-2">
                <ChartCard title="Sector exposure — pre vs post trade"><Plot ariaLabel="Sector exposure" height={360} data={[
                  { type: "bar", name: "Pre-trade %", x: res.exposures.by_sector.map((e: any) => e.sector), y: res.exposures.by_sector.map((e: any) => e.pre_pct), marker: { color: SERIES.opex } },
                  { type: "bar", name: "Post-trade %", x: res.exposures.by_sector.map((e: any) => e.sector), y: res.exposures.by_sector.map((e: any) => e.post_pct), marker: { color: SERIES.revenue } }]}
                  layout={{ barmode: "group", yaxis: { title: { text: "% of NAV" } } }} /></ChartCard>
                <ChartCard title="Largest issuer exposures"><Plot ariaLabel="Issuer exposure" height={360} data={[
                  { type: "bar", orientation: "h", name: "Post-trade %", y: res.exposures.by_issuer.map((e: any) => e.issuer), x: res.exposures.by_issuer.map((e: any) => e.post_pct), marker: { color: SERIES.revenue } }]}
                  layout={{ margin: { l: 190, r: 16, t: 8, b: 32 }, yaxis: { autorange: "reversed" }, hovermode: "closest" }} /></ChartCard>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
