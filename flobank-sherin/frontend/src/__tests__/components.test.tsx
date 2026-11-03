import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AppProvider } from "../lib/store";
import { ApprovalCard, type ApprovalT } from "../components/ApprovalCard";
import { KpiRow } from "../components/charts";

const base: ApprovalT = { id: "AP-1", kind: "investment", title: "BUY X", summary: "s", status: "pending", requested_by: "pm.a", required_roles: ["SHERIN_MANAGER", "RISK_OFFICER"],
  outstanding_roles: ["SHERIN_MANAGER", "RISK_OFFICER"], financial_impact_usd: 3500000, risk_evidence: ["Materiality: REVIEW"], policy_blocked: false, can_be_approved: true, decisions: [], data_class: "synthetic" };

function wrap(ui: React.ReactNode, role = "SHERIN_MANAGER") {
  localStorage.setItem("sherin.role", JSON.stringify(role));
  localStorage.setItem("sherin.user", JSON.stringify("tester"));
  localStorage.setItem("sherin.currency", JSON.stringify("INR"));
  return render(<MemoryRouter><AppProvider>{ui}</AppProvider></MemoryRouter>);
}
afterEach(() => localStorage.clear());

describe("ApprovalCard", () => {
  it("has no approve path for a mandatory policy block", () => {
    wrap(<ApprovalCard a={{ ...base, status: "blocked", policy_blocked: true, can_be_approved: false }} />);
    expect(screen.getByText(/No role can approve this request/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Approve" })).toBeNull();
  });
  it("disables approve for roles that are not outstanding approvers", () => {
    wrap(<ApprovalCard a={base} />, "ENGINEER");
    expect(screen.getByRole("button", { name: "Approve" })).toBeDisabled();
  });
  it("sends the decision with the acting role and user", async () => {
    const f = vi.fn(async () => ({ ok: true, headers: new Headers({ "content-type": "application/json" }), json: async () => ({ ...base, status: "partially_approved", outstanding_roles: ["RISK_OFFICER"] }) }));
    (globalThis as any).fetch = f;
    const onChange = vi.fn();
    wrap(<ApprovalCard a={base} onChange={onChange} />);
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    await waitFor(() => expect(onChange).toHaveBeenCalled());
    const [url, init] = (f.mock.calls[0] as any[]);
    expect(url).toBe("/api/approvals/AP-1/decision");
    expect(init.headers["X-Role"]).toBe("SHERIN_MANAGER");
    expect(JSON.parse(init.body).decision).toBe("approve");
  });
});

const KPIS = {
  period: { label: "Oct 2026" }, prior_period: { label: "Sep 2026" }, fx: { currency: "INR", rate: 84.37, source: "Synthetic FX assumption (offline demo)", as_of: "2026-10-01T09:00:00" },
  net_benefit: 15900000, data_class: "synthetic",
  cards: ["bank_revenue", "bank_opex", "operating_profit", "ai_cost", "ai_revenue", "cost_avoidance", "roi", "verified_work"].map((k, i) => ({
    key: k, label: k, unit: k === "roi" ? "pct" : k === "verified_work" ? "count" : "currency", value: k === "roi" ? 201.8 : k === "verified_work" ? 891 : 1000000 * (i + 1),
    prior: 1, mom_pct: 2.3, mom_pts: k === "roi" ? 29.1 : null, good_direction: "up", basis: ["ai_revenue", "cost_avoidance", "roi"].includes(k) ? "estimated" : "actual",
    data_class: "synthetic", definition: "d", budget: null, budget_variance_pct: null, budget_utilization_pct: null })),
};

describe("KpiRow", () => {
  it("renders eight cards in the selected currency with basis and synthetic labels", async () => {
    (globalThis as any).fetch = vi.fn(async () => ({ ok: true, headers: new Headers({ "content-type": "application/json" }), json: async () => KPIS }));
    wrap(<KpiRow />);
    await screen.findByTestId("kpi-bank_revenue");
    for (const c of KPIS.cards) expect(screen.getByTestId(`kpi-${c.key}`)).toBeInTheDocument();
    expect(screen.getByTestId("kpi-bank_revenue").textContent).toContain("₹1.00M");
    expect(screen.getByTestId("kpi-roi").textContent).toContain("201.8%");
    expect(screen.getAllByText("estimated")).toHaveLength(3);
    expect(screen.getAllByText("synthetic").length).toBeGreaterThanOrEqual(8);
  });
});
