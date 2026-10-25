import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { DataTable } from "@/components/DataTable";
import { Workspace } from "@/components/Workspace";
import type { Block } from "@/lib/types";

function wrap(ui: React.ReactNode) {
  return render(<QueryClientProvider client={new QueryClient()}><MemoryRouter>{ui}</MemoryRouter></QueryClientProvider>);
}

describe("DataTable", () => {
  it("sorts by column", () => {
    render(<DataTable columns={[{ key: "n", label: "N" }]} rows={[{ n: 2 }, { n: 1 }, { n: 3 }]} />);
    fireEvent.click(screen.getByRole("button", { name: "Sort by N" }));
    const cells = screen.getAllByRole("cell").map((c) => c.textContent);
    expect(cells).toEqual(["1", "2", "3"]);
  });
  it("renders boolean badges", () => {
    render(<DataTable columns={[{ key: "verified", label: "Verified" }]} rows={[{ verified: false }]} />);
    expect(screen.getByText("No")).toBeInTheDocument();
  });
});

describe("Workspace", () => {
  it("renders answer, kpis, citations flags and decision trace", () => {
    const blocks: Block[] = [
      { type: "answer", markdown: "**DENIED before execution.**" },
      { type: "kpis", items: [{ label: "Tool executions", value: 0 }] },
      { type: "citations", items: [{ doc_id: "DOC-021", title: "Bulletin", revision: "1", effective_date: "2026-10-12", review_due: "2027-10-12", classification: "INTERNAL", source: "x", status: "current", provenance_sha256: null, snippet: "[QUARANTINED]", score: 1, flags: ["prompt_injection_quarantined"], authoritative: false }] },
      { type: "warnings", items: ["telemetry withheld"] },
    ];
    wrap(<Workspace blocks={blocks} />);
    expect(screen.getByText("DENIED before execution.")).toBeInTheDocument();
    expect(screen.getByText("Tool executions")).toBeInTheDocument();
    expect(screen.getByText("prompt injection quarantined")).toBeInTheDocument();
    expect(screen.getByText("not authoritative")).toBeInTheDocument();
    expect(screen.getByText("telemetry withheld")).toBeInTheDocument();
  });
  it("calls onQuery for clarify suggestions", () => {
    const onQuery = vi.fn();
    wrap(<Workspace blocks={[{ type: "clarify", suggestions: ["Show fleet health"] }]} onQuery={onQuery} />);
    fireEvent.click(screen.getByText("Show fleet health"));
    expect(onQuery).toHaveBeenCalledWith("Show fleet health");
  });
});
