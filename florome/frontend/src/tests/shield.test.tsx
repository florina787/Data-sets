import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import App from "../App";
import { setRole } from "../lib/api";

vi.mock("../components/Chart", () => ({ Chart: ({ label }: { label: string }) => <div role="img" aria-label={label} /> }));

const summary = {
  repositories: 1, hypotheses: { total: 2, by_status: { confirmed: 1, disproven: 1 } },
  findings: { confirmed: 1, by_severity: { critical: 1 }, by_class: { command_injection: 1 }, incidents_opened: 1 }, patches: { verified: 1 },
  containment: { sessions: 2, contained: 1, by_violation: { network_egress: 1 } }, policy: { decisions: 5, denied: 1 },
  controls: { opengrep: true, trivy: true, opa: true, opa_mode: "optional", network_namespace: true, emergency_stop: false, rate_limit_per_minute: 240 },
  data_class: "benchmark",
};
const hyps = [
  { id: "h1", vuln_class: "command_injection", function: "ping", file: "app.py", line: 91, status: "confirmed", status_basis: "Reproduced in 2 of 2", assumption: "a", weakness: "w",
    verification_method: "probe_cmd_canary", supporting: [], contradicting: [], severity: "critical", severity_basis: "x", incident_id: null },
  { id: "h2", vuln_class: "command_injection", function: "echo", file: "app.py", line: 97, status: "disproven", status_basis: "guard", assumption: "a", weakness: "w",
    verification_method: "probe_cmd_canary", supporting: [], contradicting: [], severity: "none", severity_basis: "x", incident_id: null },
];
const bench = [
  { id: "b0", pipeline: "llm_only", status: "not_run", sample_size: 9, metrics: {}, note: "Not run: no authorised model endpoint is configured.", at: "" },
  { id: "b1", pipeline: "hybrid_verified", status: "completed", sample_size: 9, metrics: { tp: 5, fp: 0, fn: 0, precision: 1, recall: 1 }, note: "", at: "" },
  { id: "b2", pipeline: "scanner_only", status: "completed", sample_size: 9, metrics: { tp: 4, fp: 2, fn: 1, precision: 0.667, recall: 0.8 }, note: "", at: "" },
];
const routes: [RegExp, unknown][] = [
  [/\/shield\/summary$/, summary], [/\/shield\/repositories$/, { authorized_targets: [], repositories: [] }], [/\/shield\/hypotheses$/, hyps],
  [/\/shield\/evaluation$/, bench], [/\/shield\/containment\/scenarios$/, [{ id: "network_egress", description: "tries to call out", expected: "network_egress" }]],
  [/\/shield\/containment\/events$/, []],
];

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    const r = routes.find(([re]) => re.test(url));
    return new Response(JSON.stringify(r ? r[1] : { detail: "not mocked" }), { status: r ? 200 : 404 });
  }));
  setRole("viewer");
});
afterEach(() => vi.unstubAllGlobals());

it("shows real verdicts, metrics and an honest LLM-only status", async () => {
  render(<MemoryRouter initialEntries={["/shield"]}><App /></MemoryRouter>);
  expect(await screen.findByText("Cyber Dome")).toBeInTheDocument();
  expect(await screen.findByText("ping")).toBeInTheDocument();
  expect(screen.getByText("echo")).toBeInTheDocument();
  expect(screen.getByText("False alarms rejected")).toBeInTheDocument();
  expect(screen.getByText(/Not run: no authorised model/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Run full research/ })).toBeDisabled(); // viewer cannot start research
});
