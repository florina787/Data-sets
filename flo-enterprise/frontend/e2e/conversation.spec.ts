// FLO 2.0 conversation-first experience, driven through the real UI against the real API (synthetic data).
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

async function login(page: Page, user: string) {
  await page.goto("/");
  await page.evaluate(() => sessionStorage.clear());
  await page.goto("/");
  await page.locator(`[data-user="${user}"]`).click();
  await expect(page.getByRole("heading", { name: /Your wealth\. Your strategy\./ })).toBeVisible({ timeout: 20000 });
}

async function ask(page: Page, text: string) {
  const box = page.getByLabel("Message FLO");
  await box.fill(text);
  await box.press("Enter");
  return lastTurn(page);
}

async function lastTurn(page: Page) {
  const turn = page.getByTestId("flo-turn").last();
  await expect(turn).not.toHaveAttribute("data-status", "streaming", { timeout: 30000 });
  return turn;
}

const chart = (page: Page, id: string) => page.locator(`[data-chart="${id}"]`);

async function seriousA11y(page: Page) {
  await page.waitForTimeout(1200); // let entrance animations finish so contrast is measured at rest
  const r = await new AxeBuilder({ page }).disableRules(["region"]).analyze();
  return r.violations.filter((v) => v.impact === "serious" || v.impact === "critical").map((v) => `${v.id}: ${v.nodes.length}`);
}

test("welcome: FLO is the centre of the landing page, with personas and working prompt cards", async ({ page }) => {
  await login(page, "u-ceo");
  const composer = page.getByLabel("Message FLO");
  await expect(composer).toBeVisible();
  const box = (await composer.boundingBox())!;
  const vw = page.viewportSize()!;
  expect(box.width).toBeGreaterThan(vw.width * 0.4);
  expect(Math.abs(box.x + box.width / 2 - (vw.width + 240) / 2)).toBeLessThan(80); // centred in the main area (sidebar 240px)
  expect(box.y).toBeLessThan(vw.height * 0.6);
  await expect(page.locator("[data-prompt]")).toHaveCount(10);
  await expect(page.getByRole("radiogroup", { name: "Persona" }).getByRole("radio")).toHaveCount(10);
  await expect(page.locator("[data-chart]")).toHaveCount(0); // no dashboard grid before a question
  expect(await seriousA11y(page)).toEqual([]);
});

test("all ten starter prompts reach a governed workflow", async ({ page }) => {
  test.setTimeout(180_000);
  await login(page, "u-ceo");
  for (let i = 0; i < 10; i++) {
    if (i > 0) await page.getByRole("main").getByRole("button", { name: "New conversation" }).click();
    await page.locator(`[data-prompt="${i}"]`).click();
    const t = await lastTurn(page);
    expect(["complete", "partial", "needs_input", "denied"]).toContain(await t.getAttribute("data-status"));
    await expect(t.getByTestId("flo-headline")).not.toBeEmpty();
  }
});

test("demo 2 + 9: CEO investigates AUM vs profitability and follow-ups change the dashboard", async ({ page }) => {
  await login(page, "u-ceo");
  const t = await ask(page, "Why is our AUM growing while profitability declines?");
  await expect(t).toHaveAttribute("data-status", "complete");
  await expect(page.getByTestId("workspace-headline")).toContainText("operating margin");
  for (const id of ["aum_trend", "net_flows", "revenue_expenses", "margin_trend", "revenue_yield"]) await expect(chart(page, id)).toBeVisible();
  await expect(page.locator('[data-kpi="margin"]')).toContainText("%");
  await expect(page.getByRole("region", { name: "Recommendations" })).toContainText("expense-growth review");
  expect(await seriousA11y(page)).toEqual([]);
  await ask(page, "Break this down by product.");
  await expect(chart(page, "product_revenue")).toBeVisible();
  await ask(page, "Now show the last 24 months.");
  await expect(page.locator('[data-kpi="aum"]')).toContainText("over 24 months");
  // chart filter control sends a structured follow-up
  await chart(page, "margin_trend").getByRole("radio", { name: "12m" }).click();
  await expect(await lastTurn(page)).toHaveAttribute("data-status", "complete");
  // explain-with-FLO from a chart
  await chart(page, "margin_trend").getByRole("button", { name: /Explain with FLO/ }).click();
  await expect(await lastTurn(page)).not.toHaveAttribute("data-status", "error");
  await expect(page.getByTestId("flo-turn")).toHaveCount(5);
});

test("demo 3: CIO simulates a 20% equity downturn, then re-runs with scenario controls", async ({ page }) => {
  await login(page, "u-cio");
  await ask(page, "Simulate a 20% equity market downturn.");
  await expect(chart(page, "scenario_paths")).toBeVisible();
  await expect(page.locator('[data-kpi="aum_change"]')).toContainText("-");
  const ctl = page.getByRole("region", { name: "Scenario controls" });
  await ctl.getByRole("radio", { name: "Severe stress" }).click();
  await ctl.getByRole("button", { name: "Run scenario" }).click();
  const t = await lastTurn(page);
  await expect(t).toHaveAttribute("data-status", "complete");
  await expect(t).toContainText("severe_stress");
});

test("demo 4: wealth advisor prepares a client review with approval gates", async ({ page }) => {
  await login(page, "u-advisor");
  await ask(page, "Prepare a portfolio review for client C-00226.");
  for (const id of ["client_allocation", "risk_return", "goal_progress", "retirement_projection"]) await expect(chart(page, id)).toBeVisible();
  await expect(page.getByRole("region", { name: "Meeting agenda" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Approval requirements" })).toContainText("recommendation:deliver");
});

test("demo 5 + 8: CFO drivers and a board-ready summary", async ({ page }) => {
  await login(page, "u-cfo");
  await ask(page, "Analyze our revenue and expense drivers.");
  await expect(chart(page, "revenue_bridge")).toBeVisible();
  await expect(chart(page, "budget_variance")).toBeVisible();
  await ask(page, "Prepare a board-level summary.");
  await expect(page.getByTestId("workspace-headline")).toContainText("Board summary");
  await expect(page.getByRole("region", { name: "Approval requirements" })).toContainText("board:distribute");
});

test("demo 6: relationship manager investigates retention in their own book", async ({ page }) => {
  await login(page, "u-advisor");
  await page.getByRole("radio", { name: /Relationship Manager/ }).click();
  await ask(page, "Investigate client retention in my book.");
  await expect(chart(page, "book_signals")).toBeVisible();
  await expect(page.getByRole("region", { name: /Clients with review signals/ })).toBeVisible();
  await expect(chart(page, "retention_trend")).toHaveCount(0);
});

test("demo 7: risk officer examines concentration exposure", async ({ page }) => {
  await login(page, "u-risk");
  await ask(page, "Examine our concentration exposure.");
  await expect(chart(page, "concentration_top_issuers")).toBeVisible();
  await expect(page.getByRole("region", { name: "Recommendations" })).toContainText("single-issuer");
});

test("demo 1: business owner onboarding with labelled preliminary figures", async ({ page }) => {
  await login(page, "u-prospect");
  await ask(page, "Hello FLO, I own an investment advisory firm managing CAD 500 million. Can you help us manage the business and improve profitability?");
  await expect(page.getByRole("region", { name: "Discovery" })).toBeVisible();
  await expect(page.locator('[data-kpi="revenue"]')).toContainText("Illustrative assumption");
  await expect(chart(page, "firm_data_readiness")).toBeVisible();
  await ask(page, "We have 8 advisors, 1,200 client households, an average fee of 0.85% and expenses of CAD 3.1 million.");
  await expect(page.locator('[data-kpi="operating_margin"]')).toContainText("27.1%");
  await expect(page.locator('[data-kpi="operating_margin"]')).toContainText("Calculated from your inputs");
  await expect(page.getByRole("region", { name: "Implementation roadmap" })).toBeVisible();
});

test("demo 10 + persona: unauthorized data stays protected and personas never grant access", async ({ page }) => {
  await login(page, "u-advisor2");
  const t = await ask(page, "Prepare a portfolio review for client C-00226.");
  await expect(t).toHaveAttribute("data-status", "denied");
  await expect(page.locator("[data-chart]")).toHaveCount(0);
  await login(page, "u-advisor");
  await page.getByRole("radio", { name: /CEO \/ Executive Leadership/ }).click();
  const t2 = await ask(page, "Why is our AUM growing while profitability declines?");
  await expect(t2).toHaveAttribute("data-status", "denied");
  await expect(page.locator("[data-kpi]")).toHaveCount(0);
});

test("evidence drawer, history and reload restore the conversation", async ({ page }) => {
  await login(page, "u-ceo");
  await ask(page, "Analyze our portfolio concentration risk.");
  await page.getByRole("button", { name: "Evidence & trace" }).click();
  const dlg = page.getByRole("dialog", { name: "Evidence and governance trace" });
  await expect(dlg).toContainText("Tool calls");
  await expect(dlg.locator('[data-chart="agent_workflow"]')).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(dlg).toHaveCount(0);
  await page.getByRole("main").getByRole("button", { name: "New conversation" }).click();
  await page.getByRole("button", { name: "Conversation history" }).click();
  await page.getByLabel("Search conversations").fill("concentration");
  await page.getByRole("complementary", { name: "Conversation history" }).getByRole("button", { name: /concentration/i }).first().click();
  await expect(page.getByTestId("flo-turn")).toHaveCount(1);
  await expect(chart(page, "concentration_top_issuers")).toBeVisible();
});

test("mobile: conversation and analytics stack vertically and the composer stays reachable", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await login(page, "u-ceo");
  await expect(page.getByLabel("Message FLO")).toBeInViewport();
  await ask(page, "Why is our AUM growing while profitability declines?");
  await expect(page.getByLabel("Message FLO")).toBeInViewport();
  await expect(page.getByTestId("workspace")).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
});

test("conversational memory: performance → last quarter → top sector → 'that sector' falls 15%", async ({ page }) => {
  await login(page, "u-cio");
  await ask(page, "Show our portfolio performance.");
  await expect(chart(page, "performance_trend")).toBeVisible();
  await expect(page.locator('[data-inline-chart="performance_trend"]')).toBeVisible(); // charts appear inside the answer too
  await ask(page, "Compare it with last quarter.");
  await expect(page.getByTestId("workspace-headline")).toContainText("3 month");
  await ask(page, "Which sector contributed the most?");
  const sector = (await page.getByTestId("workspace-headline").textContent())!.split(" contributed")[0];
  const t = await ask(page, "What happens if that sector falls 15%?");
  await expect(t).toHaveAttribute("data-status", "complete");
  await expect(page.getByTestId("workspace-headline")).toContainText(`If ${sector} fell 15`);
  await expect(page.getByRole("region", { name: "Simulated outcomes" })).toBeVisible();
  // expandable agent timeline: responsibility, duration, sources, approvals
  await t.getByRole("button", { name: /Agent timeline/ }).click();
  const row = t.locator('[data-agent-run="sector_scenario_agent"]');
  await expect(row).toContainText("Single-sector shock");
  await expect(row).toContainText("ms");
  await expect(row).toContainText("Deterministic scenario engine");
  expect(await seriousA11y(page)).toEqual([]);
});

test("sidebar collapses, keeps modules reachable and reopens recent conversations", async ({ page }) => {
  await login(page, "u-ceo");
  await ask(page, "Show our portfolio performance.");
  const nav = page.getByRole("navigation", { name: "Primary" });
  await expect(nav.getByRole("button", { name: /Show our portfolio performance/ }).first()).toBeVisible();
  await nav.getByRole("button", { name: "Collapse sidebar" }).click();
  await expect(nav.getByRole("link", { name: "Executive Command Center" })).toBeVisible();
  await nav.getByRole("button", { name: "Expand sidebar" }).click();
  await nav.getByRole("button", { name: "New conversation" }).click();
  await expect(page.getByRole("heading", { name: /Your wealth\. Your strategy\./ })).toBeVisible();
  await nav.getByRole("button", { name: /Show our portfolio performance/ }).first().click();
  await expect(page.getByTestId("flo-turn")).toHaveCount(1);
});
