import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ContextPanel } from "@/features/copilot/ContextPanel";
import { blockedResponse } from "./fixtures";

const base = { setTab: vi.fn(), selected: null, onSelect: vi.fn(), extraEvidence: {}, userId: "U-002", onDecided: vi.fn(), auditKey: 0 };

describe("ContextPanel", () => {
  it("shows an empty state before any answer", () => {
    render(<ContextPanel resp={null} tab="evidence" {...base} />);
    expect(screen.getByText("Context appears here")).toBeInTheDocument();
    expect(screen.getAllByRole("tab")).toHaveLength(8);
  });
  it("shows MatterGuard decision and blocked tools on the policy tab", () => {
    render(<ContextPanel resp={blockedResponse} tab="policy" {...base} />);
    expect(screen.getByText("Prohibited")).toBeInTheDocument();
    expect(screen.getByText("✕ external_provider_call")).toBeInTheDocument();
  });
  it("explains that blocked requests create no work product", () => {
    render(<ContextPanel resp={blockedResponse} tab="approval" {...base} />);
    expect(screen.getByText("No approval required")).toBeInTheDocument();
  });
});
