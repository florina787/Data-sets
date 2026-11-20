import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import App from "../App";
import { Visual, pageFor } from "../components/Assistant";
import { setRole } from "../lib/api";

vi.mock("../components/Chart", () => ({ Chart: ({ label }: { label: string }) => <div role="img" aria-label={label} /> }));

const cfg = { page: "rca", title: "RCA", starters: ["What caused the incident?", "Which explanations were ruled out?", "Where is the evidence weakest?", "Show the timeline of events"],
  engine: { mode: "rule-based", language_model: null } };
const answer = (statement: string, extra: object = {}) => ({
  conversation_id: "conv_1", intent: "root_cause", statement, bullets: ["Verdict: confirmed", "signature_match: pass"],
  visual: { type: "chain", items: [{ label: "ingest-orders", tone: "root" }, { label: "revenue-api", tone: "impacted" }] },
  evidence: [{ label: "Evidence ev_1", href: "/rca?incident=i1" }],
  follow_ups: ["Which explanations were ruled out?", "Where is the evidence weakest?", "Show the timeline of events", "What will the plan change?"],
  engine: { mode: "rule-based", language_model: null }, input_flags: [], data_mode: "demo", ...extra,
});
let asks: { body: Record<string, unknown> }[] = [];
let failNext = false;

beforeEach(() => {
  asks = [];
  failNext = false;
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith("/assistant/pages/rca")) return new Response(JSON.stringify(cfg));
    if (url.endsWith("/assistant/ask")) {
      const body = JSON.parse(String(init?.body));
      asks.push({ body });
      if (failNext) { failNext = false; return new Response(JSON.stringify({ detail: "Rate limit exceeded" }), { status: 429 }); }
      return new Response(JSON.stringify(answer(asks.length === 1 ? "Deployment on ingest-orders." : "4 of 9 explanations were disproven by evidence.")));
    }
    if (url.includes("/incidents")) return new Response(JSON.stringify({ total: 0, items: [] }));
    return new Response(JSON.stringify({ detail: "not mocked" }), { status: 404 });
  }));
  setRole("viewer");
});
afterEach(() => vi.unstubAllGlobals());

const openOn = async (path: string) => {
  render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>);
  await userEvent.click(screen.getByRole("button", { name: /Ask Florome/ }));
  return screen.getByRole("dialog", { name: /Florome assistant/ });
};

it("maps routes to page assistants", () => {
  expect(pageFor("/")).toBe("home");
  expect(pageFor("/overview")).toBe("overview");
  expect(pageFor("/shield")).toBe("shield");
  expect(pageFor("/nowhere")).toBeNull();
});

it("shows the page's four starters and labels itself honestly", async () => {
  const dlg = await openOn("/rca?incident=i1");
  for (const s of cfg.starters) expect(await within(dlg).findByRole("button", { name: s })).toBeInTheDocument();
  expect(within(dlg).getByText(/no AI model/)).toBeInTheDocument();
});

it("asks with page context, renders a visual answer, and continues the conversation", async () => {
  const dlg = await openOn("/rca?incident=i1");
  await userEvent.click(await within(dlg).findByRole("button", { name: "What caused the incident?" }));
  expect(await within(dlg).findByText("Deployment on ingest-orders.")).toBeInTheDocument();
  expect(asks[0].body).toMatchObject({ page: "rca", question: "What caused the incident?", conversation_id: null, context: { incident_id: "i1" } });
  expect(within(dlg).getByText("ingest-orders")).toBeInTheDocument(); // chain visual
  expect(within(dlg).getByRole("link", { name: /Evidence ev_1/ })).toHaveAttribute("href", "/rca?incident=i1");
  const card = within(dlg).getAllByTestId("assistant-answer")[0];
  expect(within(card).getAllByRole("button")).toHaveLength(4); // four follow-ups
  await userEvent.click(within(card).getByRole("button", { name: "Which explanations were ruled out?" }));
  expect(await within(dlg).findByText(/4 of 9 explanations/)).toBeInTheDocument();
  expect(asks[1].body).toMatchObject({ conversation_id: "conv_1" });
});

it("supports free text and recovers from errors with retry", async () => {
  const dlg = await openOn("/rca");
  failNext = true;
  await userEvent.type(within(dlg).getByLabelText("Your question"), "why did it break?{Enter}");
  expect(await within(dlg).findByRole("alert")).toHaveTextContent("Rate limit exceeded");
  await userEvent.click(within(dlg).getByRole("button", { name: "Retry" }));
  await waitFor(() => expect(within(dlg).queryByRole("alert")).not.toBeInTheDocument());
  expect(asks.map((a) => a.body.question)).toEqual(["why did it break?", "why did it break?"]);
});

it("closes with Escape and offers no assistant on unknown pages", async () => {
  await openOn("/rca");
  await userEvent.keyboard("{Escape}");
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

it("renders every visual type from answer data", () => {
  const { container } = render(
    <MemoryRouter>
      <Visual v={{ type: "kpis", items: [{ label: "Verified", value: 1 }] }} />
      <Visual v={{ type: "bars", unit: "USD", items: [{ label: "aws", value: 200 }, { label: "azure", value: 100 }] }} />
      <Visual v={{ type: "table", columns: ["A"], rows: [["x"]] }} />
      <Visual v={{ type: "timeline", items: [{ at: "2026-11-20T17:00:00Z", label: "api", text: "500", tone: "bad" }] }} />
      <Visual v={{ type: "report", markdown: "# Brief" }} />
    </MemoryRouter>,
  );
  expect(screen.getByText("Verified")).toBeInTheDocument();
  const bars = container.querySelectorAll(".bg-dome-500");
  expect((bars[0] as HTMLElement).style.width).toBe("100%");
  expect((bars[1] as HTMLElement).style.width).toBe("50%");
  expect(screen.getByRole("button", { name: /Download brief/ })).toBeInTheDocument();
});
