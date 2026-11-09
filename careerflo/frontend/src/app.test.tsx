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
    "Governance Center", "Billing and Subscription", "Account Settings"]) expect(labels).toContain(l);
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
