import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import { cubeNodes } from "../pages/Integrations";
import { constellation, timelineOption } from "../pages/RCA";
import { layout } from "../pages/Topology";
import { setRole, type Platform } from "../lib/api";
import { plan, report, summary, topology } from "./fixtures";

vi.mock("../components/Chart", () => ({ Chart: ({ label }: { label: string }) => <div role="img" aria-label={label} /> }));

type Route = [RegExp, (init?: RequestInit) => { status?: number; body: unknown }];
let routes: Route[] = [];
const calls: { url: string; init?: RequestInit }[] = [];

beforeEach(() => {
  calls.length = 0;
  routes = [
    [/\/analytics\/summary$/, () => ({ body: summary })],
    [/\/topology$/, () => ({ body: topology })],
    [/\/architecture\/scenarios$/, () => ({ status: 503, body: { detail: "Project B dependencies not installed" } })],
    [/\/incidents$/, () => ({ body: { total: 1, items: [{ id: "i1", title: "Revenue API 500", severity: "sev2", status: "open", primary_resource_id: "c", detected_at: "2026-11-10T12:00:00Z", resolved_at: null, symptoms: [], is_demo: true }] } })],
    [/\/remediations\?incident_id=i1$/, () => ({ body: [plan] })],
    [/\/executions\?limit=500$/, () => ({ body: [] })],
    [/\/governance\/audit\?limit=200$/, () => ({ body: { total: 0, items: [] } })],
    [/\/rca\/i1$/, () => ({ body: report })],
  ];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    calls.push({ url, init });
    const r = routes.find(([re]) => re.test(url));
    const { status = 200, body } = r ? r[1](init) : { status: 404, body: { detail: "not mocked" } };
    return new Response(JSON.stringify(body), { status });
  }));
  setRole("operator");
});
afterEach(() => vi.unstubAllGlobals());

const renderAt = (path: string) => render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>);

describe("navigation and overview", () => {
  it("renders the shell, demo banner and live KPIs", async () => {
    renderAt("/");
    expect(screen.getByText(/fictional tenant/)).toBeInTheDocument();
    const nav = screen.getByRole("navigation", { name: "Primary" });
    for (const l of ["Overview", "Nervous System", "RCA", "Actions", "Integrations", "Sources", "Governance", "FinOps"]) expect(within(nav).getByText(l)).toBeInTheDocument();
    expect(await screen.findByText("1/1")).toBeInTheDocument();
    expect(screen.getAllByText(/Synthetic demo data/).length).toBeGreaterThan(0);
  });

  it("reports the copilot layer honestly when Project B is unavailable", async () => {
    renderAt("/");
    expect(await screen.findByText("unavailable")).toBeInTheDocument();
    expect(screen.getByText("imported")).toBeInTheDocument();
  });

  it("shows an error state with retry when the API fails", async () => {
    routes.unshift([/\/analytics\/summary$/, () => ({ status: 500, body: { detail: "backend down" } })]);
    renderAt("/");
    expect(await screen.findByRole("alert")).toHaveTextContent("backend down");
    expect(screen.getByText("Retry")).toBeInTheDocument();
  });
});

describe("topology", () => {
  it("lays out nodes by dependency depth", () => {
    const pos = layout(topology);
    expect(pos.a.x).toBe(0);
    expect(pos.b.x).toBeGreaterThan(pos.a.x);
    expect(pos.c.x).toBeGreaterThan(pos.b.x);
  });

  it("renders resource nodes with incident roles", async () => {
    renderAt("/topology");
    expect(await screen.findByTestId("topology-canvas")).toBeInTheDocument();
    expect(await screen.findByText("root cause")).toBeInTheDocument();
  });
});

describe("rca", () => {
  it("builds a constellation that can hide disproven hypotheses", () => {
    const all = constellation(report, null, false);
    expect(all.nodes.map((n) => n.id)).toContain("H2");
    const filtered = constellation(report, null, true);
    expect(filtered.nodes.map((n) => n.id)).not.toContain("H2");
    expect(filtered.edges.find((e) => e.target === "H2")).toBeUndefined();
    expect(all.edges.find((e) => e.target === "H2")?.style).toMatchObject({ strokeDasharray: "5 4" });
  });

  it("marks anomalous timeline events and the root change", () => {
    const opt = timelineOption(report) as { series: { data: { itemStyle: { color: string } }[]; markLine: { data: { name: string }[] } }[] };
    expect(opt.series[0].data[1].itemStyle.color).toBe("#E0534A");
    expect(opt.series[0].markLine.data.map((m) => m.name)).toEqual(["Detected", "Root change"]);
  });

  it("shows the conclusion and hypothesis table", async () => {
    renderAt("/rca?incident=i1");
    expect(await screen.findByText("Deployment on ingest-orders.")).toBeInTheDocument();
    expect(screen.getByText("Hypothesis comparison")).toBeInTheDocument();
  });
});

describe("actions", () => {
  it("approves exactly the presented plan hash with a fresh nonce", async () => {
    setRole("approver");
    routes.unshift([/\/approvals$/, () => ({ status: 201, body: { ...plan, status: "approved" } })]);
    renderAt("/actions?incident=i1");
    await userEvent.click(await screen.findByRole("button", { name: /Approve/ }));
    await waitFor(() => expect(calls.some((c) => c.url.endsWith("/approvals"))).toBe(true));
    const call = calls.find((c) => c.url.endsWith("/approvals"))!;
    const body = JSON.parse(String(call.init!.body));
    expect(body).toMatchObject({ plan_id: "plan_1", decision: "approve", plan_hash: plan.plan_hash });
    expect(body.nonce).toMatch(/^[0-9a-f]{32}$/);
    expect((call.init!.headers as Record<string, string>).Authorization).toBe("Bearer demo-meridian-approver");
  });

  it("surfaces a server denial (separation of duties)", async () => {
    routes.unshift([/\/approvals$/, () => ({ status: 403, body: { detail: "Separation of duties: the plan's creator cannot approve it" } })]);
    renderAt("/actions?incident=i1");
    await userEvent.click(await screen.findByRole("button", { name: /Approve/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Separation of duties");
  });

  it("renders every field required before approval", async () => {
    renderAt("/actions?incident=i1");
    for (const t of [/rollback_deployment/, /Errors drop/, /Re-point alias/, /lambda:UpdateAlias/]) expect(await screen.findByText(t)).toBeInTheDocument();
  });
});

describe("integrations", () => {
  it("never shows a planned platform as verified", () => {
    const platforms: Platform[] = [
      { platform: "sandbox", group: "Test", status: "simulated", connector_type: "sandbox", note: "", connected_and_verified: true },
      { platform: "github", group: "Enterprise software", status: "implemented", connector_type: "github_rest", note: "", connected_and_verified: false },
      { platform: "cloudwatch", group: "AWS", status: "not_implemented", connector_type: "", note: "", connected_and_verified: false },
    ];
    const byId = Object.fromEntries(cubeNodes(platforms).map((n) => [n.id, n.state]));
    expect(byId).toMatchObject({ core: "core", Test: "verified", "Enterprise software": "implemented", AWS: "planned", Microsoft: "planned" });
  });
});
