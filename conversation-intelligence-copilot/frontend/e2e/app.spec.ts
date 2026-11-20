import { expect, test, type Page } from "@playwright/test";

const errors: string[] = [];

async function fresh(page: Page) {
  page.on("pageerror", (e) => errors.push(String(e)));
  await page.goto("/");
  await page.evaluate(() => localStorage.removeItem("cic.session"));
  await page.goto("/");
}

async function askCard(page: Page, tag: string) {
  await page.getByRole("button", { name: new RegExp("^" + tag) }).click();
  await expect(page.getByText("Uncertainty & method").last()).toBeVisible({ timeout: 60_000 });
}

test.afterEach(() => {
  expect(errors, "no uncaught page errors").toEqual([]);
});

test("Q1: negative topics in the last month with charts, evidence and QA", async ({ page }) => {
  await fresh(page);
  await askCard(page, "Sentiment × topics");
  await expect(page.getByRole("heading", { level: 2 })).toContainText("Top negative topics in November 2025");
  await expect(page.getByText(/240 of 682 conversations/)).toBeVisible();
  await expect(page.getByText("Top negative topics · November 2025")).toBeVisible();
  await expect(page.locator(".recharts-bar-rectangle").first()).toBeVisible();
  await expect(page.getByText(/QA \d+\/\d+/)).toBeVisible();
  await expect(page.getByText("Supporting evidence")).toBeVisible();
  // Evidence opens the source transcript.
  await page.getByRole("button", { name: "Open full transcript →" }).first().click();
  await expect(page.getByRole("dialog")).toContainText("Source transcript");
  await expect(page.getByRole("dialog").getByText(/cs_conversations\.csv:line/).first()).toBeVisible();
  await page.keyboard.press("Escape");
  // Follow-up keeps context.
  await page.getByRole("button", { name: "Compare the top two topics." }).click();
  await expect(page.getByText(/Resolved '#1, #2' from the previous answer/)).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText(/Kept the previous date window \(November 2025\)/)).toBeVisible();
});

test("Q2: coaching shows safeguards and the review heatmap", async ({ page }) => {
  await fresh(page);
  await askCard(page, "Agent coaching");
  await expect(page.getByText("Human review required.")).toBeVisible();
  await expect(page.getByText("Review signals for flagged conversations")).toBeVisible();
  await expect(page.getByText(/No agent has 3 or more conversations/).first()).toBeVisible();
});

test("Q3: trajectory for a conversation selected in the explorer", async ({ page }) => {
  await fresh(page);
  await page.goto("/explorer/C0000479");
  await page.getByRole("button", { name: "Analyse sentiment trajectory" }).click();
  await page.getByRole("link", { name: "Ask Intelligence" }).first().click();
  await expect(page.getByText("Annotated transcript timeline")).toBeVisible({ timeout: 60_000 });
  await expect(page.getByRole("heading", { level: 2 })).toContainText("C0000479");
  await expect(page.getByText("turning point").first()).toBeVisible();
});

test("Q4: leadership priorities with recommendations and a priority matrix", async ({ page }) => {
  await fresh(page);
  await askCard(page, "Leadership priorities");
  await expect(page.getByText("Recommendations for leadership")).toBeVisible();
  await expect(page.getByText("Priority matrix: volume vs negative rate")).toBeVisible();
  await expect(page.getByText(/Decision owner/).first()).toBeVisible();
});

test("unsupported question is refused without charts", async ({ page }) => {
  await fresh(page);
  await page.getByRole("textbox").fill("What is the revenue impact of these complaints?");
  await page.keyboard.press("Enter");
  // Without a model this is a refusal; with one it is the model's own answer, clearly labelled as not from the dataset.
  await expect(page.getByText("I can't answer that reliably from this dataset.").or(page.getByTestId("general-answer-banner"))).toBeVisible({ timeout: 120_000 });
  await expect(page.locator(".recharts-surface")).toHaveCount(0);
});

test("chart drilldown opens the underlying conversations", async ({ page }) => {
  await fresh(page);
  await page.goto("/sentiment");
  await expect(page.getByText("How to read this")).toBeVisible({ timeout: 60_000 });
  await page.locator(".recharts-bar-rectangle").first().click();
  await expect(page.getByRole("dialog")).toContainText("Conversations behind this data point");
  await page.getByRole("dialog").getByRole("button").filter({ hasText: /^C\d{7}/ }).first().click();
  await expect(page.getByRole("dialog").last()).toContainText("Source transcript");
});

test("agent harness shows the executed graph with real statuses", async ({ page }) => {
  await fresh(page);
  await page.getByRole("button", { name: /^Leadership priorities/ }).click();
  await expect(page.getByText("Recommendations for leadership")).toBeVisible({ timeout: 60_000 });
  await page.getByRole("link", { name: /Trace/ }).click();
  await expect(page.locator(".react-flow__node")).toHaveCount(20); // 18 nodes incl. the Zero-LLM router, plus START and END
  await expect(page.locator(".react-flow__node").filter({ hasText: "Leadership agent" })).toContainText("completed");
  await expect(page.locator(".react-flow__node").filter({ hasText: "Coaching agent" })).toContainText("skipped");
  await page.locator(".react-flow__node").filter({ hasText: "Supervisor / planner" }).click();
  await expect(page.getByText("leadership_priorities").first()).toBeVisible();
});

test("all pages render", async ({ page }) => {
  await fresh(page);
  for (const [path, text] of [["/leadership", "Executive summary"], ["/coaching", "Conversation review queue"], ["/explorer", "Select a conversation"],
    ["/prompts", "System instruction"], ["/metrics", "Node latency"], ["/governance", "Controls"]] as const) {
    await page.goto(path);
    await expect(page.getByText(text).first()).toBeVisible({ timeout: 30_000 });
  }
});

test("backend failure shows an error with retry", async ({ page }) => {
  await fresh(page);
  await page.route("**/api/chat/stream", (r) => r.fulfill({ status: 503, body: JSON.stringify({ detail: "Analytics database not found" }) }));
  await page.getByRole("textbox").fill("Show the sentiment trend over time.");
  await page.keyboard.press("Enter");
  await expect(page.getByRole("alert")).toContainText("Analytics database not found");
  await page.unroute("**/api/chat/stream");
  await page.getByRole("button", { name: "Retry" }).click();
  await expect(page.getByText("Negative rate by month")).toBeVisible({ timeout: 60_000 });
});

test("mobile layout has no horizontal overflow", async ({ browser }) => {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true });
  const page = await ctx.newPage();
  await page.goto("/");
  await expect(page.getByRole("textbox")).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
  await ctx.close();
});
