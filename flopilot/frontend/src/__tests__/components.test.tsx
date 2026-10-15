import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AnswerCard } from "../components/AnswerCard";
import { Chart } from "../components/Chart";
import { ProposalCard } from "../components/ProposalCard";
import { RichText } from "../components/RichText";
import type { AssistantResult, ChartSpec, Operation } from "../lib/types";

function op(overrides: Partial<Operation> = {}): Operation {
  return {
    id: "op_1", workbook_id: "wb", base_version: 1, current_version: 1, out_of_date: false, run_id: "run", action_type: "normalize_categories",
    status: "PROPOSED", title: "Normalize Region spelling (5 cells)", description: "Replace spelling variants.", sheet: "Sales",
    target_range: "E2:E121", affected_cells: 5,
    flags: { overwrites_values: 5, replaces_formulas: 0, clears_values: 0, inserts_formulas: 0, deletes_rows: 0, adds_sheet: false },
    destructive: false, warnings: ["Review each mapping."], details: { mapping: { "north america": "North America" } },
    changes_sample: [{ sheet: "Sales", cell: "E7", before: { formula: null, type: "text", value: "north america" }, after: { formula: null, type: "text", value: "North America" }, number_format: null }],
    changes_total: 5, removed_rows_sample: [], new_sheet: null, change_set_hash: "a".repeat(64), requires_acknowledgement: false,
    fidelity_at_risk: [], dry_run: { passed: true, checks: [{ name: "reopens", passed: true, detail: "ok" }] }, verification: null,
    validation: null, error: null, result_version: null, created_at: "2026-01-01T00:00:00Z", ...overrides,
  };
}

const noop = async () => undefined;

describe("ProposalCard", () => {
  it("shows the diff, flags and approves with an idempotency key", async () => {
    const onApprove = vi.fn(async () => undefined);
    render(<ProposalCard op={op()} canApprove previewing={false} onPreview={vi.fn()} onApprove={onApprove} onReject={noop} onRefresh={noop} />);
    expect(screen.getByText("Overwrites 5 values")).toBeInTheDocument();
    expect(screen.getByText("north america")).toBeInTheDocument();
    expect(screen.getByText(/Dry run passed 1 validation checks/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Approve & apply" }));
    expect(onApprove).toHaveBeenCalledTimes(1);
    const [, ack, key] = onApprove.mock.calls[0] as unknown as [Operation, boolean, string];
    expect(ack).toBe(false);
    expect(key).toMatch(/\w+-\w+/);
  });

  it("requires explicit acknowledgement when features would be lost", () => {
    render(<ProposalCard op={op({ requires_acknowledgement: true, dry_run: { passed: true, checks: [], fidelity: { lost: { charts: 1 } } } })}
      canApprove previewing={false} onPreview={vi.fn()} onApprove={noop} onReject={noop} onRefresh={noop} />);
    const approve = screen.getByRole("button", { name: "Approve & apply" });
    expect(approve).toBeDisabled();
    fireEvent.click(screen.getByRole("checkbox"));
    expect(approve).toBeEnabled();
  });

  it("does not let viewers approve and offers re-preparation for out-of-date proposals", () => {
    const { rerender } = render(<ProposalCard op={op()} canApprove={false} previewing={false} onPreview={vi.fn()} onApprove={noop} onReject={noop} onRefresh={noop} />);
    expect(screen.getByRole("button", { name: "Approve & apply" })).toBeDisabled();
    expect(screen.getByText(/can view proposals but not approve/)).toBeInTheDocument();
    rerender(<ProposalCard op={op({ out_of_date: true, current_version: 2, details: { builder: { name: "x", args: {} } } })} canApprove previewing={false}
      onPreview={vi.fn()} onApprove={noop} onReject={noop} onRefresh={noop} />);
    expect(screen.queryByRole("button", { name: "Approve & apply" })).toBeNull();
    expect(screen.getByRole("button", { name: /Prepare again/ })).toBeInTheDocument();
    expect(screen.getByText(/Out of date/)).toBeInTheDocument();
  });

  it("flags destructive edits", () => {
    render(<ProposalCard op={op({ destructive: true, flags: { overwrites_values: 0, replaces_formulas: 1, clears_values: 0, inserts_formulas: 1, deletes_rows: 2, adds_sheet: false } })}
      canApprove previewing={false} onPreview={vi.fn()} onApprove={noop} onReject={noop} onRefresh={noop} />);
    expect(screen.getByText("Replaces 1 formula")).toBeInTheDocument();
    expect(screen.getByText("Deletes 2 rows")).toBeInTheDocument();
  });
});

describe("AnswerCard", () => {
  const result: AssistantResult = {
    schema_version: "1.0", type: "answer", text: "Sum of **Net Revenue**:\n- Europe: **$390,624.50**",
    sources: [{ id: "src_1", workbook_id: "wb", version: 1, sheet: "Sales", range: "K2:K121", header: "Net Revenue", label: "Sales!K2:K121 (Net Revenue)", status: "current" }],
    method: "SUM of 'Net Revenue'", assumptions: ["'revenue' means Net Revenue (confirmed by you)."], warnings: [],
    follow_ups: [{ label: "Add to workbook as a report", prompt: "Add this summary to the workbook as a report sheet" }], engine: "deterministic-demo",
  };

  it("renders sources, method and assumptions, and navigates to sources", () => {
    const onSource = vi.fn();
    const onPrompt = vi.fn();
    render(<AnswerCard result={result} operations={{}} canApprove previewOpId={null} onSource={onSource} onPrompt={onPrompt}
      onPreview={vi.fn()} onApprove={noop} onReject={noop} onRefresh={noop} />);
    expect(screen.getByText("$390,624.50").tagName).toBe("STRONG");
    fireEvent.click(screen.getByRole("button", { name: "Sales!K2:K121 (Net Revenue)" }));
    expect(onSource).toHaveBeenCalledWith(result.sources![0]);
    expect(screen.getByText(/confirmed by you/)).toBeInTheDocument();
    expect(screen.getByText(/Demo mode: deterministic rules/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Add to workbook as a report" }));
    expect(onPrompt).toHaveBeenCalledWith("Add this summary to the workbook as a report sheet");
  });

  it("offers clarification options instead of guessing", () => {
    const onPrompt = vi.fn();
    render(<AnswerCard result={{ schema_version: "1.0", type: "clarification", text: "Which revenue?", clarification: { question: "Which revenue?", options: [{ label: "Gross Revenue", prompt: "Use Gross Revenue for revenue" }, { label: "Net Revenue", prompt: "Use Net Revenue for revenue" }] } }}
      operations={{}} canApprove previewOpId={null} onSource={vi.fn()} onPrompt={onPrompt} onPreview={vi.fn()} onApprove={noop} onReject={noop} onRefresh={noop} />);
    fireEvent.click(screen.getByRole("button", { name: "Net Revenue" }));
    expect(onPrompt).toHaveBeenCalledWith("Use Net Revenue for revenue");
  });
});

describe("RichText", () => {
  it("never renders workbook text as HTML", () => {
    const { container } = render(<RichText text={"<script>alert(1)</script> **ok**"} />);
    expect(container.querySelector("script")).toBeNull();
    expect(container.textContent).toContain("<script>alert(1)</script>");
  });
});

describe("Chart", () => {
  it("draws gaps for missing months instead of zeros and labels web-only charts", () => {
    const spec: ChartSpec = {
      kind: "chart", type: "line", title: "Net Revenue trend", x_label: "Month", y_label: "Sum of Net Revenue (USD ($))", unit: "USD ($)",
      series: [{ name: "All", points: [{ x: "2025-01", y: 10 }, { x: "2025-02", y: null }, { x: "2025-03", y: 30 }] }],
      filters: [], sources: [], notes: ["Months without data are shown as gaps, not zero."], web_only: true,
    };
    const { container } = render(<Chart spec={spec} />);
    expect(container.querySelectorAll("path")).toHaveLength(2);    // two segments around the gap
    expect(container.querySelectorAll("circle")).toHaveLength(2);
    expect(screen.getByText(/shown in FloPilot only/)).toBeInTheDocument();
    expect(screen.getByText(/gaps, not zero/)).toBeInTheDocument();
  });
});
