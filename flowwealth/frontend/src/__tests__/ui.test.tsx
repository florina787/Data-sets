import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { StatusBadge, SyntheticNotice } from "../components/ui";
import { SegmentedMeter } from "../components/charts";
import Layout from "../components/Layout";
import Memory from "../pages/Memory";
import Rankings from "../pages/Rankings";
import { pct, monogram } from "../lib/format";

function mockFetch(routes: Record<string, unknown>) {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    const key = Object.keys(routes).find((k) => url.startsWith(`/api${k}`));
    if (!key) return new Response(JSON.stringify({ detail: "nope" }), { status: 404 });
    return new Response(JSON.stringify(routes[key]), { status: 200 });
  }));
}
afterEach(() => vi.unstubAllGlobals());

const memoryResp = (verified: boolean) => ({
  chain_verified: verified, first_bad_seq: verified ? null : 7,
  recent: [{ prediction_id: "p1", created_at: "2025-01-02T21:00:00", ticker: "SYN0001", horizon: "swing", target_time: "2025-01-12",
    actual_return: 0.02, benchmark_return: 0.01, direction_correct: 1, forecast_return: 0.004, regime: "bull_trend",
    strategy_id: "replay:xs_5d", data_status: "SYNTHETIC" }],
  summary: { model_version: "lightgbm@1", dataset_version: "syn-v1", data_status: "SYNTHETIC", predictions: 1, replay_steps: 1,
    evaluation: { n_resolved: 1, n_pending: 0, directional_accuracy_vs_excess: 1 }, feature_drift_psi_dev_vs_holdout: {} },
});

describe("formatting", () => {
  it("formats signed percentages and missing values", () => {
    expect(pct(0.0123)).toBe("+1.23%");
    expect(pct(-0.5, 0)).toBe("-50%");
    expect(pct(null)).toBe("—");
    expect(pct(Number.NaN)).toBe("—");
    expect(monogram("SYN0042")).toBe("S42");
    expect(monogram("abc")).toBe("AB");
  });
});

describe("components", () => {
  it("labels every data status and explains it", () => {
    render(<StatusBadge status="SYNTHETIC" />);
    expect(screen.getByText("SYNTHETIC")).toHaveAttribute("title", expect.stringMatching(/no market meaning/));
  });
  it("only shows the synthetic notice for synthetic data", () => {
    const { rerender, container } = render(<SyntheticNotice status="HISTORICAL" />);
    expect(container).toBeEmptyDOMElement();
    rerender(<SyntheticNotice status="SYNTHETIC" />);
    expect(screen.getByRole("note")).toHaveTextContent(/not real markets/);
  });
  it("segmented meter exposes its value accessibly", () => {
    render(<SegmentedMeter on={12} segments={40} label="risk" />);
    expect(screen.getByRole("meter", { name: "risk" })).toHaveAttribute("aria-valuenow", "12");
  });
  it("planned sections are not navigable", () => {
    render(<MemoryRouter><Layout /></MemoryRouter>);
    const planned = screen.getByText("Paper Trading").closest("span");
    expect(planned).toHaveAttribute("aria-disabled", "true");
    expect(screen.queryByRole("link", { name: /Paper Trading/ })).toBeNull();
    expect(screen.getByRole("link", { name: /Prediction Memory/ })).toBeInTheDocument();
    expect(screen.getByText(/not investment advice/)).toBeInTheDocument();
  });
});

describe("pages", () => {
  it("prediction memory shows the ledger, the synthetic caveat and a verified chain", async () => {
    mockFetch({ "/memory": memoryResp(true) });
    render(<MemoryRouter><Memory /></MemoryRouter>);
    await waitFor(() => expect(screen.getByText("Verified")).toBeInTheDocument());
    expect(screen.getByText("SYN0001")).toBeInTheDocument();
    expect(screen.getAllByText(/replay/).length).toBeGreaterThan(0);
  });
  it("prediction memory surfaces a broken chain", async () => {
    mockFetch({ "/memory": memoryResp(false) });
    render(<MemoryRouter><Memory /></MemoryRouter>);
    await waitFor(() => expect(screen.getByText("Broken @7")).toBeInTheDocument());
  });
  it("rankings explain their methodology and show the disclaimer", async () => {
    mockFetch({ "/rankings": { horizon: "5 trading days (swing)", as_of: "2025-12-31 21:00", data_status: "SYNTHETIC",
      model_version: "lightgbm@1", target: "excess", methodology: "LightGBM on ranked features", disclaimer: "not investment advice",
      feature_correlation_with_score: { ret_5_rk: -0.4 },
      items: [{ ticker: "SYN0009", exchange: "XNYS", sector: "Energy", country: "US", adj_close: 12, ts: "2025", pred: 0.01, vol_20: 0.02, ret_20: 0.05, dd_60: -0.1 }] } });
    render(<MemoryRouter><Routes><Route path="*" element={<Rankings />} /></Routes></MemoryRouter>);
    await waitFor(() => expect(screen.getByText("SYN0009")).toBeInTheDocument());
    expect(screen.getByText(/LightGBM on ranked features/)).toBeInTheDocument();
    expect(screen.getByText("not investment advice")).toBeInTheDocument();
  });
  it("shows an error instead of fake data when the API fails", async () => {
    mockFetch({});
    render(<MemoryRouter><Rankings /></MemoryRouter>);
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/Could not load/));
  });
});
