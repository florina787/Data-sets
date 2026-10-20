import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { ChartCard } from "../charts/ChartCard";
import { TopicSentimentHeatmap } from "../charts/charts";
import { AppProvider } from "../lib/state";
import { describeFilters } from "../assistant/Flo";

vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ datasets: [] }), { headers: { "content-type": "application/json" } })));
vi.stubGlobal("ResizeObserver", class { observe() {} unobserve() {} disconnect() {} });

const wrap = (ui: React.ReactNode) => render(<MemoryRouter><AppProvider>{ui}</AppProvider></MemoryRouter>);

describe("ChartCard", () => {
  it("always provides scope, units, an accessible table, CSV export and Ask Flo", () => {
    wrap(<ChartCard title="Topics" scope="topic = Billing" units="conversations" askQuestion="q" table={{ head: ["Topic", "Count"], rows: [["Billing", 3], ["Unknown", 1]] }}><div /></ChartCard>);
    expect(screen.getByText(/topic = Billing/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /CSV/ })).toBeEnabled();
    expect(screen.getByRole("button", { name: /Ask Flo about this/ })).toBeInTheDocument();
    expect(screen.getByRole("table", { name: "Topics data" })).toBeInTheDocument();
    expect(screen.getAllByText("Unknown").length).toBeGreaterThan(0);
  });
  it("shows an empty state for unsupported metrics", () => {
    wrap(<ChartCard title="T" scope="s" units="u" askQuestion="q" empty="Not enough weeks." table={{ head: [], rows: [] }}><div>chart</div></ChartCard>);
    expect(screen.getByText("Not enough weeks.")).toBeInTheDocument();
    expect(screen.queryByText("chart")).toBeNull();
  });
});

describe("Heatmap and table consistency", () => {
  it("labels every cell with the same count as the data", () => {
    const data = { scope: "all", denominator: 5, columns: [{ key: "negative", label: "Negative" }, { key: "unknown", label: "Unknown" }],
      rows: [{ key: "billing_refunds", label: "Billing & refunds", total: 5, cells: [{ key: "negative", label: "Negative", count: 3, share_of_row: 0.6 }, { key: "unknown", label: "Unknown", count: 2, share_of_row: 0.4 }] }] };
    render(<TopicSentimentHeatmap data={data} />);
    expect(screen.getByTitle("Billing & refunds · Negative: 3 of 5 (60%)")).toBeInTheDocument();
    expect(screen.getByTitle("Billing & refunds · Unknown: 2 of 5 (40%)")).toBeInTheDocument();
  });
});

describe("Filter chips", () => {
  it("describe explicit scope for Flo context", () => {
    const chips = describeFilters({ topics: ["billing_refunds"], resolution: ["unresolved_explicit"] });
    expect(chips.map((c) => c.label)).toEqual(["Topic: Billing & refunds", "Outcome: Explicitly unresolved"]);
  });
});
