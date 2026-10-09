import { Card, Empty, Notice } from "../components/ui";
import { StatusBadge } from "../components/charts";
import { usePoll } from "../hooks";
import { AskButton } from "./Copilot";

export default function Compliance() {
  const { data, error } = usePoll<any>("/api/enterprise/compliance", 15000);
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold">Product compliance</h1>
          <p className="text-sm text-navy-600">Channel listings checked field by field against the approved product records from Regulatory Affairs.</p>
        </div>
        <AskButton question="Which listings have allergen issues?" label="Ask about allergens" />
      </div>
      {error && <Notice kind="error">{error}</Notice>}
      {!data ? <Empty>Loading…</Empty> : (
        <>
          <Card title={`Issues: ${data.critical} critical, ${data.warnings} warnings, across ${data.listings_checked} listings`}>
            {data.issues.length === 0 ? <Empty>All listings match their approved records.</Empty> : (
              <table className="table">
                <thead><tr><th>Severity</th><th>Product</th><th>Channel</th><th>Rule</th><th>Finding</th></tr></thead>
                <tbody>{data.issues.map((i: any) => (
                  <tr key={i.sku + i.channel + i.rule}>
                    <td><StatusBadge status={i.severity === "critical" ? "critical" : "reorder"} /><span className="sr-only">{i.severity}</span></td>
                    <td>{i.name}</td><td>{i.channel}</td><td className="text-xs">{i.rule}</td>
                    <td className="text-xs">{i.detail}{i.note && <div className="text-navy-600">{i.note}</div>}</td>
                  </tr>
                ))}</tbody>
              </table>
            )}
            <p className="mt-2 text-xs text-navy-600">{data.method}. The copilot reports issues; correcting listings is a Regulatory Affairs and channel-operations task.</p>
          </Card>
          <Card title="Approved product records">
            <table className="table">
              <thead><tr><th>Product</th><th>Version</th><th>Ingredients</th><th>Allergens</th><th>Approved</th></tr></thead>
              <tbody>{data.records.map((r: any) => (
                <tr key={r.sku}><td>{r.name}<div className="font-mono text-[10px] text-navy-600">{r.sku}</div></td><td>v{r.version}</td><td className="text-xs">{r.ingredients.join(", ")}</td><td className="text-xs font-semibold">{r.allergens.join(", ") || "none declared"}</td><td className="text-xs">{r.approved_by}, {r.approved_at}</td></tr>
              ))}</tbody>
            </table>
          </Card>
        </>
      )}
    </div>
  );
}
