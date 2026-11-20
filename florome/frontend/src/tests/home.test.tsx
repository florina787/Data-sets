import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import App from "../App";
import { setRole } from "../lib/api";

vi.mock("../components/Chart", () => ({ Chart: ({ label }: { label: string }) => <div role="img" aria-label={label} /> }));

const home = { page: "home", title: "Copilot", starters: ["What's broken right now?"], engine: { mode: "rule-based", language_model: null },
  groups: [{ title: "Operations", questions: ["What caused the incident?"] }, { title: "Customers · Conversation Copilot", questions: ["What are customers most negative about?"] }] };
const customerAnswer = {
  conversation_id: "conv_9", intent: "customer_negative_topics", statement: "Top negative topics in November 2025: General help request, Duplicate charge.",
  bullets: ["#1 General help request: 49 negative of 156"], visual: { type: "bars", unit: "Negative conversations", items: [{ label: "General help request", value: 49 }] },
  evidence: [{ label: "C0011749 · Membership: “Hi, I need help with my Membership.”", href: null }],
  follow_ups: ["Compare the top two topics.", "What about the previous month?", "Show three supporting examples.", "Which agents handled those concerns?"],
  engine: { mode: "rule-based", language_model: null }, input_flags: [], data_mode: "demo",
  source: { name: "Conversation Intelligence Copilot", status: "completed", model_calls: 0 },
};
let reachable = true;
const asked: string[] = [];

beforeEach(() => {
  asked.length = 0;
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith("/assistant/pages/home")) return new Response(JSON.stringify(home));
    if (url.endsWith("/assistant/sources"))
      return new Response(JSON.stringify({ florome: { reachable: true, status: "ok" }, conversation_copilot: { configured: true, reachable, status: reachable ? "degraded" : "unreachable" } }));
    if (url.endsWith("/assistant/ask")) { asked.push(JSON.parse(String(init?.body)).question); return new Response(JSON.stringify(customerAnswer)); }
    return new Response(JSON.stringify({ detail: "not mocked" }), { status: 404 });
  }));
  setRole("viewer");
});
afterEach(() => vi.unstubAllGlobals());

const renderHome = () => render(<MemoryRouter initialEntries={["/"]}><App /></MemoryRouter>);

it("opens on the copilot with grouped questions and live source status", async () => {
  renderHome();
  expect(screen.getByRole("heading", { name: /What do you want to know/ })).toBeInTheDocument();
  expect(await screen.findByRole("region", { name: "Customers · Conversation Copilot" })).toBeInTheDocument();
  expect(await screen.findByText(/connected \(degraded\)/)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Ask Florome$/ })).not.toBeInTheDocument(); // no floating dock on the copilot page
});

it("reports the conversation copilot as not running when it is down", async () => {
  reachable = false;
  renderHome();
  expect(await screen.findByText("not running")).toBeInTheDocument();
  reachable = true;
});

it("answers a customer question with its source and quoted evidence", async () => {
  renderHome();
  const region = await screen.findByRole("region", { name: "Customers · Conversation Copilot" });
  await userEvent.click(within(region).getByRole("button", { name: "What are customers most negative about?" }));
  expect(await screen.findByText(/Top negative topics in November 2025/)).toBeInTheDocument();
  expect(screen.getByTestId("answer-source")).toHaveTextContent("Answered by the Conversation Intelligence Copilot · 0 AI model calls");
  expect(screen.getByTitle("Quoted from the source conversation")).toHaveTextContent("C0011749");
  await userEvent.click(screen.getByRole("button", { name: "What about the previous month?" }));
  expect(asked).toEqual(["What are customers most negative about?", "What about the previous month?"]);
});
