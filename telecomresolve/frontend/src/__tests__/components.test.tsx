import { fireEvent, render, screen } from "@testing-library/react";
import { RecommendationCard } from "../components/RecommendationCard";
import { EvidencePanel } from "../components/EvidencePanel";
import { StatusChip } from "../components/ui";
import { parseHash } from "../router";
import { statusTone } from "../format";
import { EvidenceResponse, Recommendation } from "../types";

const rec: Recommendation = {
  id: "REC-1", status: "active", action_type: "create_technician_dispatch", payload: { case_id: "C-1003" },
  payload_hash: "abcdef0123456789", purpose: "Send a technician.", prerequisites: ["Fresh diagnostics within 24 hours"],
  evidence_refs: ["DIAG-SNR", "DIAG-CRC"], uncertainty: "Evidence sufficiency: strong.", risk: "high",
  approval_requirement: { requires_approval: true, approver_roles: ["supervisor"], executor_roles: ["field_coordinator"],
    separation_of_duties: true, mvp_behavior: "executable" },
  policy_version: "p1", policy_decision: { allowed: true, reasons: [] },
  prior_interventions: [{ source_ref: "HIST-INT-1003-1", action: "modem_restart", outcome: "unresolved",
    repeated_in_recommendation: false, justification: "Recorded as already tried in 2 source(s) (HIST-INT-1003-1, STATEMENT) without resolving the symptom; not repeated." }],
  refused_requests: [{ request: "Guaranteed restoration time", reason: "Never guaranteed.", citations: ["KB-x"] }],
  alternatives: [{ action_type: "apply_bill_credit", allowed: false, executable: false, mvp_behavior: "disabled", reasons: ["disabled"] }],
  proposed_by: "u-spec-ava", generation_mode: "DEMO", snapshot_id: "SNAP-1", created_at: "2026-10-09T00:00:00Z",
};

test("recommendation card shows purpose, evidence, uncertainty, risk, approval and prior steps", () => {
  const opened: string[] = [];
  render(<RecommendationCard rec={rec} approval={null} onOpenRef={(r) => opened.push(r)} />);
  expect(screen.getByText(/Create technician dispatch/)).toBeInTheDocument();
  expect(screen.getByText("Send a technician.")).toBeInTheDocument();
  expect(screen.getByText(/Evidence sufficiency: strong/)).toBeInTheDocument();
  expect(screen.getByText(/Risk: high/)).toBeInTheDocument();
  expect(screen.getByText(/proposer cannot approve/)).toBeInTheDocument();
  expect(screen.getByText(/not repeated/)).toBeInTheDocument();
  expect(screen.getByText(/Generation: DEMO/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Open source DIAG-SNR" }));
  expect(opened).toEqual(["DIAG-SNR"]);
});

test("evidence panel separates measured observations from statements", () => {
  const ev: EvidenceResponse = {
    snapshot: { id: "SNAP-1", created_at: "", content_hash: "x", window_start: "", window_end: "", facts: [],
      missing_evidence: ["fresh_line_diagnostics"], prior_actions: [] },
    items: [
      { ref_id: "DIAG-STALE", source_type: "diagnostic_sample", source_id: "s", source_version: "v", authority: "measurement",
        kind: "observation", excerpt: "old sample", freshness: "stale", supports: [], opposes: [], flags: ["stale"], retrieved_at: "", data: {} },
      { ref_id: "STATEMENT", source_type: "customer_statement", source_id: "C", source_version: "v", authority: "customer_statement",
        kind: "statement", excerpt: "it drops", freshness: "n/a", supports: [], opposes: [], flags: [], retrieved_at: "", data: {} },
    ],
    hypotheses: [], diagnosis: { conclusion: "INSUFFICIENT_EVIDENCE", summary: "No cause is asserted." }, snapshots: ["SNAP-1"],
  };
  render(<EvidencePanel ev={ev} onOpenRef={() => {}} />);
  expect(screen.getByText("Insufficient evidence")).toBeInTheDocument();
  expect(screen.getByText(/Missing evidence: fresh_line_diagnostics/)).toBeInTheDocument();
  expect(screen.getByLabelText("Measured observations")).toHaveTextContent("old sample");
  expect(screen.getByLabelText("Reported statements and notes")).toHaveTextContent("it drops");
  expect(screen.getByText("Stale")).toBeInTheDocument();
});

test("status chips carry text, not color alone", () => {
  render(<StatusChip status="AWAITING_APPROVAL" />);
  expect(screen.getByText("Pending approval")).toBeInTheDocument();
  render(<StatusChip status="VERIFYING" />);
  expect(screen.getByText("Recovery not yet verified")).toBeInTheDocument();
  expect(statusTone("RESOLVED")).toBe("ok");
});

test("hash router parses case ids", () => {
  expect(parseHash("#/workspace/C-1003")).toEqual({ page: "workspace", caseId: "C-1003" });
  expect(parseHash("")).toEqual({ page: "overview", caseId: undefined });
});
