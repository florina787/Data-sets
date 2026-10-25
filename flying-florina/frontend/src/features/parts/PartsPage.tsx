import { Boxes } from "lucide-react";
import { useState } from "react";
import { Chart } from "@/components/Chart";
import { DataTable } from "@/components/DataTable";
import { Card, ErrorBox, Loading, PageHeader } from "@/components/ui";
import { useApi } from "@/lib/hooks";

type Parts = {
  items: Record<string, unknown>[]; critical: Record<string, unknown>[];
  suppliers: { id: string; name: string; deliveries: number; on_time_pct: number; avg_slip_days: number; recent_avg_slip_days: number | null }[];
  substitutes: Record<string, unknown>[];
};

export function PartsPage() {
  const [pn, setPn] = useState("P-7731");
  const [input, setInput] = useState("P-7731");
  const q = useApi<Parts>(["parts", pn], `/api/parts/availability${pn ? `?part_number=${encodeURIComponent(pn)}` : ""}`);
  return (
    <div className="space-y-4">
      <PageHeader title="Parts & Supply Chain" subtitle="Inventory reconciled across ERP, nightly CSV and supplier portal. Interchangeability is never inferred without an authority document." icon={<Boxes className="h-5 w-5" />} />
      <form className="flex flex-wrap gap-2" onSubmit={(e) => { e.preventDefault(); setPn(input.trim().toUpperCase()); }}>
        <input className="input" value={input} onChange={(e) => setInput(e.target.value)} aria-label="Part number" placeholder="P-7731 (empty = all)" />
        <button className="btn btn-primary">Check availability</button>
      </form>
      {q.isLoading ? <Loading /> : q.error ? <ErrorBox error={q.error} /> : q.data && (
        <>
          <Card title={pn ? `${pn}: availability by location` : "All stock locations"} subtitle="verified_qty uses the most recent physical count; critical counts older than 30 days are unverified (fictional DOC-009).">
            <DataTable label="Availability" columns={[{ key: "part_number", label: "Part" }, { key: "location", label: "Location" }, { key: "verified_qty", label: "Verified" }, { key: "reported_qty_by_source", label: "Reported by source" }, { key: "last_verified", label: "Last count" }, { key: "verified", label: "Verified" }, { key: "conflict", label: "Conflict" }, { key: "lot", label: "Lot" }, { key: "note", label: "Note" }]} rows={q.data.items} />
          </Card>
          {pn && (
            <Card title="Approved substitution check">
              <DataTable columns={[{ key: "part_number", label: "Alternate" }, { key: "authority_doc", label: "Authority doc" }, { key: "approved", label: "Approved" }, { key: "reason", label: "Reason" }]} rows={q.data.substitutes} />
            </Card>
          )}
          <div className="grid gap-4 lg:grid-cols-2">
            <Card title="Supplier on-time % (computed from synthetic delivery history)">
              <Chart title="Supplier reliability" spec={{ kind: "bar", x: q.data.suppliers.map((s) => s.id), series: [{ name: "On-time %", data: q.data.suppliers.map((s) => s.on_time_pct) }, { name: "Recent slip (d)", data: q.data.suppliers.map((s) => s.recent_avg_slip_days) }] }} height={240} />
            </Card>
            <Card title="Critical stock (2 or fewer verified units)">
              <DataTable columns={[{ key: "part_number", label: "Part" }, { key: "name", label: "Name" }, { key: "criticality", label: "Criticality" }, { key: "verified_total", label: "Verified" }, { key: "lead_time_days", label: "Lead d" }]} rows={q.data.critical} maxHeight={240} />
            </Card>
          </div>
          <Card title="Supplier reliability table">
            <DataTable columns={[{ key: "id", label: "Supplier" }, { key: "name", label: "Name" }, { key: "deliveries", label: "Deliveries" }, { key: "on_time_pct", label: "On-time %" }, { key: "avg_slip_days", label: "Avg slip d" }, { key: "recent_avg_slip_days", label: "Recent slip d" }]} rows={q.data.suppliers} />
          </Card>
        </>
      )}
    </div>
  );
}
