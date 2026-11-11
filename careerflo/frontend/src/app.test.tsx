import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { ActivityHeatmap, CareerProgression, JobCard, levelIndex } from "./components/career";
import { AgentCursor } from "./components/art/AgentCursor";
import { NAV } from "./components/Layout";
import { salaryRange } from "./lib/utils";

const wrap = (ui: JSX.Element) => render(<QueryClientProvider client={new QueryClient()}><MemoryRouter>{ui}</MemoryRouter></QueryClientProvider>);

test("sidebar exposes all 22 required sections", () => {
  const labels = NAV.flatMap((g) => g.items.map(([l]) => l));
  for (const l of ["AI Career Assistant", "Job Discovery", "Indeed Job Intelligence", "LinkedIn Job Intelligence", "Hidden Job Radar", "Job Matching",
    "Resume Studio", "ATS Intelligence", "Cover Letter Studio", "Interview Intelligence", "Live Coding Coach", "Company Research", "Recruiter CRM",
    "Application Tracker", "GitHub Portfolio Intelligence", "Salary Intelligence", "Career Analytics", "Agent Mission Control", "MCP Tool Registry",
    "Governance Center", "Billing and Subscription", "Account Settings", "Career Graph"]) expect(labels).toContain(l);
  expect(labels.at(-1)).toBe("Career Graph");
});

test("job card shows source, salary and synthetic label; never invents a salary", () => {
  wrap(<JobCard job={{ id: "1", title: "Senior AI Engineer", company: "Demo Co", source: "synthetic", is_synthetic: true, salary_min: 150000, salary_max: 180000, salary_currency: "CAD", posted_at: new Date().toISOString() }} />);
  expect(screen.getByText("Senior AI Engineer")).toBeInTheDocument();
  expect(screen.getByText("CAD 150k–180k")).toBeInTheDocument();
  expect(screen.getByText("Synthetic demo")).toBeInTheDocument();
  expect(salaryRange({})).toBe("Salary not published");
});

test("career progression highlights the current role", () => {
  wrap(<CareerProgression name="Alex" current={2} title="AI Engineer" />);
  expect(screen.getByText("You are here")).toBeInTheDocument();
  expect(screen.getByText("Senior AI Engineer")).toBeInTheDocument();
  expect(levelIndex(6, "Software Engineer")).toBe(2);
});

test("heatmap and agent cursor render", () => {
  const { container } = wrap(<><ActivityHeatmap dates={[new Date().toISOString()]} weeks={4} /><AgentCursor label="Job Discovery" /></>);
  expect(container.querySelectorAll("span[title]").length).toBe(28);
  expect(screen.getByText("Job Discovery")).toBeInTheDocument();
});

test("model markdown renders bold and lists without raw asterisks or HTML injection", async () => {
  const { Markdown } = await import("./components/Markdown");
  const { container } = render(<Markdown text={"**Summary:**\n- one **two**\n1. first\n<img src=x onerror=alert(1)>"} />);
  expect(container.querySelector("strong")?.textContent).toBe("Summary:");
  expect(container.querySelectorAll("li").length).toBe(2);
  expect(container.textContent).not.toContain("**");
  expect(container.querySelector("img")).toBeNull();
});

test("transactions card summarises real invoices, handles refunds/failures and shows an honest empty state", async () => {
  const { summarise, alertsFor, TransactionsCard } = await import("./components/Transactions");
  const now = new Date("2026-11-10T12:00:00Z").getTime();
  const d = (days: number) => new Date(now - days * 864e5).toISOString();
  const txns = [
    { id: "a", status: "paid", amount_cents: 999, currency: "cad", paid_at: d(70) },
    { id: "b", status: "paid", amount_cents: 999, currency: "cad", paid_at: d(40) },
    { id: "c", status: "refunded", amount_cents: 1999, refunded_cents: 1999, currency: "cad", paid_at: d(10) },
    { id: "e", status: "paid", amount_cents: 1999, currency: "cad", paid_at: d(5) },
    { id: "f", status: "failed", amount_cents: 1999, currency: "cad", paid_at: d(2) },
  ];
  const all = summarise(txns, "ALL", now);
  expect(all.total).toBe(999 + 999 + 0 + 1999);          // refunds and failures contribute nothing
  expect(all.series.at(-1)!.value).toBeCloseTo(39.97);
  const m = summarise(txns, "1M", now);
  expect(m.total).toBe(1999);
  expect(m.delta).toBe(1999 - 999);                        // vs. the previous 30 days
  expect(m.pct).toBeCloseTo(1.001, 2);
  expect(alertsFor(txns, { status: "past_due" }).map((a) => a.tone)).toContain("coral");
  render(<TransactionsCard txns={[]} sub={null} />);
  expect(screen.getByText("No transactions yet")).toBeInTheDocument();
  expect(screen.getByText(/appear here once Stripe confirms/)).toBeInTheDocument();
});
