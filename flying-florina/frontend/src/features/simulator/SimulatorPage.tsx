import { FlaskConical } from "lucide-react";
import { Card, PageHeader } from "@/components/ui";
import { Workspace } from "@/components/Workspace";

const DEFAULTS = { aircraft_id: "AC-204", part_number: "P-7731", base: "MAIN-HUB", delays_hours: [24, 48, 72], install_hours: 9, downtime_cost_per_hour_low: 4000, downtime_cost_per_hour_high: 9000, monte_carlo_runs: 2000 };

export function SimulatorPage() {
  return (
    <div className="space-y-4">
      <PageHeader title="Scenario Simulator" subtitle="What-if digital twin of the AC-204 recovery: deterministic formulas, seeded Monte Carlo over synthetic supplier history, sensitivity analysis. Versioned runs." icon={<FlaskConical className="h-5 w-5" />} />
      <Card title="How outcomes are computed">
        <ul className="list-disc space-y-0.5 pl-4 font-mono text-[11px]">
          <li>arrival = start + delay_hours</li>
          <li>slot_start = first available hangar slot at base with start &gt;= arrival</li>
          <li>downtime_hours = (slot_start + install_hours) - start</li>
          <li>cost_range = downtime_hours x [cost_per_hour_low, cost_per_hour_high] (fictional assumptions)</li>
        </ul>
      </Card>
      <Workspace blocks={[{ type: "scenario_controls", inputs: DEFAULTS }]} />
    </div>
  );
}
