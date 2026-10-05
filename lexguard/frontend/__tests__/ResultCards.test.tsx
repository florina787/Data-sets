import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { CopilotResult } from "@/features/copilot/ResultCards";
import { blockedResponse, reviewResponse } from "./fixtures";

describe("CopilotResult", () => {
  it("renders a blocked state with policy evidence and agent trace", () => {
    render(<CopilotResult resp={blockedResponse} onAction={vi.fn()} onFinding={vi.fn()} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Blocked by deterministic policy");
    expect(screen.getByText("External legal-AI request blocked")).toBeInTheDocument();
    expect(screen.getAllByText("POL-CLIENT-003").length).toBeGreaterThan(0);
    expect(screen.getByText("How LexGuard analyzed this")).toBeInTheDocument();
    expect(screen.getByText("Requested provider blocked by policy")).toBeInTheDocument();
    expect(screen.getByText(/0 paid LLM calls/)).toBeInTheDocument();
  });

  it("renders structured review cards and wires findings and actions", () => {
    const onAction = vi.fn();
    const onFinding = vi.fn();
    render(<CopilotResult resp={reviewResponse} onAction={onAction} onFinding={onFinding} />);
    expect(screen.getByText("Lawyer review required before use")).toBeInTheDocument();
    expect(screen.getByText("63")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Supply Agreement"));
    expect(onFinding).toHaveBeenCalledWith("F-1");
    fireEvent.click(screen.getByRole("button", { name: "Draft Memo" }));
    expect(onAction).toHaveBeenCalledWith(expect.objectContaining({ id: "draft-memo" }));
  });
});
