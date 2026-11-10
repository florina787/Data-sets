import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AppStateProvider } from "@/app/AppState";
import { ChartBody } from "@/components/charts/ChartRenderer";
import { ResponseView } from "@/components/chat/ResponseView";
import { EvidenceProvider } from "@/components/evidence/EvidenceContext";
import type { ChartSpec } from "@/types/api";
import { response } from "./fixtures";

function wrap(ui: React.ReactNode) {
  return render(<MemoryRouter><AppStateProvider><EvidenceProvider>{ui}</EvidenceProvider></AppStateProvider></MemoryRouter>);
}

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn().mockImplementation(() => Promise.resolve(new Response(JSON.stringify({ available: false }), { status: 200 }))));
  try { localStorage.clear(); } catch { /* ignore */ }
});

const base: Omit<ChartSpec, "chart_type" | "data"> = {
  chart_id: "c", title: "T", description: "", x_field: "name", y_field: null, series: [], value_format: "count", filters: {}, dataset_scope: "original",
  source_analysis_id: "", evidence_ids: [], uncertainty_note: null, drilldown: null, error_low_field: null, error_high_field: null, accessibility_summary: "",
};

describe("ChartBody", () => {
  it("renders KPI cards with numerator/denominator", () => {
    wrap(<ChartBody spec={{ ...base, chart_type: "kpi", data: response.charts[0].data }} />);
    expect(screen.getByText("29.3%")).toBeInTheDocument();
    expect(screen.getByText("3,215 / 10,966")).toBeInTheDocument();
  });

  it("renders tables and heatmaps from server data", () => {
    wrap(<ChartBody spec={{ ...base, chart_type: "heatmap", data: [{ row: "C1 (AgentA)", conversation_id: "C1", cells: { "Missed empathy": 1, "Resolution misfit": null } }] }} />);
    expect(screen.getByText("C1 (AgentA)")).toBeInTheDocument();
    expect(screen.getByText("n/a")).toBeInTheDocument();
  });
});

describe("ResponseView", () => {
  it("shows answer, human-review notice, evidence, uncertainty and QA", async () => {
    wrap(<ResponseView r={response} />);
    expect(screen.getByRole("heading", { name: response.headline })).toBeInTheDocument();
    expect(screen.getByText(/Human review required/)).toBeInTheDocument();
    expect(screen.getByText("C0006890")).toBeInTheDocument();
    expect(screen.getByText(/Decision support only/)).toBeInTheDocument();
    expect(screen.getByText("QA 2/2")).toBeInTheDocument();
    expect(screen.getByText(/Resolved '#1'/)).toBeInTheDocument();
    await userEvent.click(screen.getByText("QA 2/2"));
    expect(screen.getByText(/Denominators/)).toBeInTheDocument();
  });

  it("links to the execution trace", () => {
    wrap(<ResponseView r={response} />);
    expect(screen.getByRole("link", { name: /Trace/ })).toHaveAttribute("href", "/harness/R-1");
  });
});
