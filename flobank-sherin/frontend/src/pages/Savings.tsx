import { GraphB, GraphC, GraphD, GraphG, KpiRow } from "../components/charts";
import { PageHeader } from "../components/ui";
export default function Savings() {
  return (
    <div>
      <PageHeader title="AI Savings" subtitle="Verified economic value: cost avoidance, realized savings, attributed profit and what Sherin cost to produce them." />
      <KpiRow />
      <div className="mt-4 space-y-4"><GraphB /><GraphC /><GraphG /><GraphD /></div>
    </div>
  );
}
