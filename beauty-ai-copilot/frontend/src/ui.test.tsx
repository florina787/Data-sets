import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Badge, ErrorBox } from "./components";
import { ApiError } from "./api";
import { ci, pp, statusTone } from "./format";
import { GateTable } from "./pages/tabs";

describe("format", () => {
  it("formats percentage points distinctly from percent", () => {
    expect(pp(-4.31)).toBe("-4.31 pp");
    expect(pp(2.5)).toBe("+2.50 pp");
    expect(ci([-8.62, -0.86])).toBe("-8.62 to -0.86");
  });
  it("maps statuses to tones", () => {
    expect(statusTone("FAIL")).toBe("fail");
    expect(statusTone("INCONCLUSIVE")).toBe("warn");
    expect(statusTone("PASS")).toBe("pass");
  });
});

describe("status is never colour-only", () => {
  it("badge renders a text label and a symbol", () => {
    render(<Badge s="FAIL" />);
    const b = screen.getByText("FAIL").closest(".badge")!;
    expect(b.textContent).toContain("✕");
    expect(b).toHaveAttribute("data-status", "FAIL");
  });
  it("gate table shows rule, observed and status text", () => {
    render(<GateTable gates={[{ gate_id: "G-NO-REGRESSION", rule: "No cell loses > 2 pp", observed: "TS-3|cool -4.31 pp", status: "FAIL", owner_role: "domain_reviewer", evidence: [] }]} />);
    expect(screen.getByText("G-NO-REGRESSION")).toBeInTheDocument();
    expect(screen.getByText("TS-3|cool -4.31 pp")).toBeInTheDocument();
    expect(screen.getByText("FAIL")).toBeInTheDocument();
  });
});

describe("errors", () => {
  it("distinguishes policy blocks and lists blockers", () => {
    render(<ErrorBox error={new ApiError(409, "policy", "release_gates_blocking", "gates do not pass", { blockers: ["G-REVIEWS: domain PENDING"] }, "t1")} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Blocked by policy");
    expect(screen.getByText("G-REVIEWS: domain PENDING")).toBeInTheDocument();
  });
  it("distinguishes unavailable integrations", () => {
    render(<ErrorBox error={new ApiError(503, "integration_unavailable", "deployment_unconfigured", "not configured")} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Integration unavailable");
  });
});
