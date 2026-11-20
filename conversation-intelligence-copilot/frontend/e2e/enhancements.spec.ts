import { expect, test, type Page } from "@playwright/test";

/** The six enhancements, driven through the real UI in Analytics-only mode (deterministic, no model needed). */
const errors: string[] = [];

async function fresh(page: Page) {
  page.on("pageerror", (e) => errors.push(String(e)));
  await page.goto("/");
  await page.evaluate(() => { localStorage.removeItem("cic.session"); localStorage.setItem("cic.analysisMode", "analytics_only"); });
  await page.goto("/");
}

async function ask(page: Page, q: string) {
  await page.locator("#composer").fill(q);
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("routing-strip").last()).toBeVisible({ timeout: 90_000 });
}

test.afterEach(() => {
  expect(errors, "no uncaught page errors").toEqual([]);
});

test("Zero-LLM router: mode switch, route reason and honest token count", async ({ page }) => {
  await fresh(page);
  await expect(page.getByTestId("mode-analytics_only")).toHaveAttribute("aria-checked", "true");
  await ask(page, "What were the top 5 topics most associated with negative customer sentiment in the last month represented in the dataset?");
  const strip = page.getByTestId("routing-strip").last();
  await expect(strip).toContainText("Zero-LLM route");
  await expect(strip).toContainText("ANALYTICS ONLY selected");
  await expect(page.getByTestId("token-usage").last()).toContainText("0 (no model call)");
});

test("Dynamic dashboard: built from the answer, with rationale and refinements", async ({ page }) => {
  await fresh(page);
  await ask(page, "What were the top 5 topics most associated with negative customer sentiment in the last month represented in the dataset?");
  await page.getByTestId("view-dashboard").last().click();
  const d = page.getByTestId("dashboard-view").last();
  await expect(d).toContainText("Negative sentiment by topic");
  await expect(d).toContainText("Why this chart:");
  await expect(d.getByRole("button", { name: "Compare top two" })).toBeVisible();
  await page.getByTestId("view-answer").last().click();
  await expect(page.getByTestId("dashboard-view")).toHaveCount(0);
});

test("Conversation X-Ray: finding, timeline and transcript stay in sync", async ({ page }) => {
  await fresh(page);
  await ask(page, "X-ray conversation C0000479");
  const x = page.getByTestId("xray-panel").last();
  await expect(x).toBeVisible();
  await x.getByTestId("xray-signal-reopened_after_fix").click();
  await expect(x.locator('[data-highlighted="true"]')).toHaveCount(4); // turns 2, 4, 6, 12
  await x.getByTestId("xray-turn-11").click(); // the closing action that does not fit the issue
  await expect(x.getByTestId("xray-signal-resolution_mismatch")).toHaveAttribute("aria-pressed", "true");
  await expect(x.locator('[data-highlighted="true"]')).toHaveCount(1);
});

test("Root cause investigator: drivers vs symptoms, alternatives, no causal claims", async ({ page }) => {
  await fresh(page);
  await ask(page, "What is driving negative sentiment in duplicate charges?");
  const rc = page.getByTestId("root-cause-panel").last();
  await expect(rc).toContainText("associations, not proof of cause");
  await expect(rc.getByTestId("rc-factor-low_empathy")).toBeVisible();
  await expect(rc).toContainText("Symptoms (customer reactions)");
  await expect(rc).toContainText("Alternative explanations checked");
});

test("Evidence challenger and decision replay are attached to the answer", async ({ page }) => {
  await fresh(page);
  await ask(page, "Which recurring customer concerns should contact-centre leadership review first?");
  const ev = page.getByTestId("evidence-review").last();
  await expect(ev).toContainText("Quotes match source");
  await expect(ev).toContainText("What does not fit the claim");
  const rp = page.getByTestId("decision-replay").last();
  await rp.getByRole("button", { name: /AI decision replay/ }).click();
  await expect(rp).toContainText("DuckDB operations");
  await expect(rp).toContainText("leadership_priorities");
  await expect(rp).toContainText("None — this answer was produced without a model.");
  await rp.getByTestId("replay-step-router").click();
  await expect(rp).toContainText("Zero-LLM routing");
});

test("Hybrid retrieval: method switch and per-method ranks in the explorer", async ({ page }) => {
  await fresh(page);
  await page.goto("/explorer");
  await page.getByRole("tab", { name: "Semantic search" }).click();
  await page.locator("#sem").fill("customer charged twice wants a refund");
  await page.getByRole("button", { name: "Search" }).click();
  await expect(page.getByText(/mode hybrid/)).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText(/MiniLM #\d+/).first()).toBeVisible();
  await page.getByTestId("retrieval-lsa").click();
  await expect(page.getByText(/mode lsa/)).toBeVisible({ timeout: 30_000 });
});

test("System metrics shows token accounting and both retrieval backends", async ({ page }) => {
  await fresh(page);
  await page.goto("/metrics");
  await expect(page.getByTestId("token-accounting")).toContainText("Dataset preprocessing");
  await expect(page.getByTestId("retrieval-backends")).toContainText("Dense (MiniLM)");
  await expect(page.getByTestId("retrieval-backends")).toContainText("Sparse (LSA)");
});

test("Fast path: a greeting gets a light reply with no agents or model", async ({ page }) => {
  await fresh(page);
  await page.locator("#composer").fill("Hi");
  await page.keyboard.press("Enter");
  const reply = page.getByTestId("small-talk").last();
  await expect(reply).toBeVisible({ timeout: 10_000 });
  await expect(reply).toContainText("Hello!");
  await expect(reply).toContainText("Fast path · no model");
});

test("Top statements: a ranked table of real customer statements, shortfall stated", async ({ page }) => {
  await fresh(page);
  await ask(page, "What are the top 5 positive statements from users?");
  await expect(page.locator("h2").last()).toContainText("Only 2 distinct positive statements");
  const table = page.getByTestId("statements-table").last();
  await expect(table.locator("tbody tr")).toHaveCount(2);
  await expect(table).toContainText("Thanks, that helps.");
  await table.locator("tbody tr").first().getByRole("button").first().click();
  await expect(page.getByRole("dialog")).toBeVisible();
});
