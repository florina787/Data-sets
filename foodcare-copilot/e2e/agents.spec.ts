import { expect, test } from "@playwright/test";

// Agent Intelligence: knowledge, context and procedural graphs plus agent activity, from real records.
const SHOTS = "../docs/screenshots";

test("agent intelligence shows the graphs of a real answer", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Signed in as").selectOption({ label: "Val Park (Viewer)" });
  const nav = page.getByRole("navigation", { name: "Primary" });
  await nav.getByRole("link", { name: "Ask Copilot", exact: true }).click();
  const main = page.getByRole("main");
  await main.getByLabel("Ask the copilot").fill("Is there enough apple stock for the Ontario weekend campaign?");
  await main.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(main.getByText(/high risk/).first()).toBeVisible();

  await nav.getByRole("link", { name: "Agent Intelligence" }).click();
  await expect(main.getByRole("list", { name: "Semantic spine" })).toBeVisible();
  await expect(main.getByRole("img", { name: /Knowledge graph with \d+ entities/ })).toBeVisible();
  const context = main.getByRole("region", { name: "The slice Jerry used" });
  await expect(context.getByText("campaign_stock_risk", { exact: true })).toBeVisible();
  await expect(main.getByText(/used 1 knowledge-graph node/)).toBeVisible();
  await expect(main.getByRole("img", { name: /Procedural graph/ })).toBeVisible();
  await expect(main.getByRole("img", { name: /Agent runs over time/ })).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/36-agent-intelligence.png`, fullPage: true });
});
