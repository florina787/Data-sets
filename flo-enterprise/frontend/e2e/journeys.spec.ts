import { expect, test, type Page } from "@playwright/test";

const shot = (page: Page, name: string) => page.screenshot({ path: `../docs/screenshots/${name}.png`, fullPage: false });

async function login(page: Page, user: string) {
  await page.goto("/");
  await page.locator(`[data-user="${user}"]`).click();
  await expect(page.getByRole("navigation", { name: "Primary" })).toBeVisible();
}

test("CEO: executive command center renders seeded charts and Ask Flo answers", async ({ page }) => {
  await login(page, "u-ceo");
  await expect(page.getByRole("heading", { name: "Executive Command Center" })).toBeVisible();
  await expect(page.getByText("Total AUM")).toBeVisible();
  await expect(page.locator("[data-chart] canvas").first()).toBeVisible({ timeout: 20000 });
  expect(await page.locator("[data-chart]").count()).toBeGreaterThanOrEqual(10);
  await page.waitForTimeout(1500);
  await shot(page, "01-executive");
  await page.getByRole("button", { name: "Ask Flo" }).first().click();
  await page.getByLabel("Question for Flo").fill("Why did AUM increase while profitability declined?");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(page.getByTestId("ask-answer")).toContainText("operating margin", { timeout: 20000 });
  await shot(page, "02-ask-flo");
  // lineage panel on a chart
  await page.getByRole("button", { name: "Close Ask Flo" }).click();
  await page.locator('[data-chart="aum_waterfall"]').getByRole("button", { name: "Source lineage and methodology" }).click();
  await expect(page.locator('[data-chart="aum_waterfall"]')).toContainText("Methodology");
});

test("CIO: investment workspace, portfolio detail and scenario simulator", async ({ page }) => {
  await login(page, "u-cio");
  await page.getByRole("link", { name: "Investment Intelligence" }).click();
  await page.getByRole("table", { name: "Portfolios" }).locator("tbody tr").first().click();
  await expect(page.getByText("Performance vs benchmark (cumulative)")).toBeVisible({ timeout: 20000 });
  await page.waitForTimeout(1200);
  await shot(page, "03-portfolio-detail");
  await page.getByRole("link", { name: "Scenario Simulator" }).click();
  await page.getByRole("button", { name: "severe stress" }).click();
  await expect(page.getByText("Estimated AUM")).toBeVisible({ timeout: 20000 });
  await page.waitForTimeout(1200);
  await shot(page, "04-scenarios");
});

test("Advisor: sees only assigned clients and drafts an approval-gated communication", async ({ page }) => {
  await login(page, "u-advisor");
  await expect(page.getByRole("heading", { name: /Advisor Home/ })).toBeVisible();
  await page.getByRole("table", { name: "Clients" }).locator("tbody tr").first().click();
  await expect(page.getByText("Contact (masked)")).toBeVisible({ timeout: 20000 });
  await shot(page, "05-client-360");
  await page.getByRole("tab", { name: "Goals & retirement" }).click();
  await expect(page.getByText(/Retirement projection/)).toBeVisible({ timeout: 20000 });
  await page.getByRole("tab", { name: "Communication drafting" }).click();
  await page.getByRole("button", { name: /Draft & submit for approval/ }).click();
  await expect(page.getByText("awaiting_approval")).toBeVisible({ timeout: 20000 });
  await shot(page, "06-comms-draft");
  // navigation is role-aware: no executive dashboard for advisors
  await expect(page.getByRole("link", { name: "Executive Command Center" })).toHaveCount(0);
});

test("Compliance officer: reviews the exact payload in the approvals queue", async ({ page }) => {
  await login(page, "u-compliance");
  await page.getByRole("link", { name: /Approvals/ }).click();
  await page.getByRole("button", { name: /client_communication|comms:send/ }).first().click().catch(async () => {
    await page.locator("ul li button").first().click();
  });
  await expect(page.getByText("Exact proposed payload")).toBeVisible();
  await shot(page, "07-approvals");
});

test("AI admin: observability dashboard and agent workflow", async ({ page }) => {
  await login(page, "u-aiadmin");
  await page.getByRole("link", { name: "AI Operations" }).click();
  await expect(page.getByText("Cost / workflow")).toBeVisible({ timeout: 20000 });
  await page.waitForTimeout(1000);
  await shot(page, "08-aiops");
});

test("External advisor: restricted navigation, product research only", async ({ page }) => {
  await login(page, "u-external");
  const links = await page.getByRole("navigation", { name: "Primary" }).getByRole("link").allTextContents();
  expect(links.map((l) => l.trim())).toEqual(["Product Research", "Knowledge Search", "Data Products"]);
  const r = await page.request.get("/api/wealth/clients/C-00001", { headers: { Authorization: `Bearer ${await page.evaluate(() => sessionStorage.getItem("flo.token"))}` } });
  expect(r.status()).toBe(403);
});
