import { expect, test } from "@playwright/test";
import { navTo } from "./nav";

// Flo & Jerry 3.0 command experience: visual answers, X-Ray, guarded containment,
// the team portfolio, honest connector states, the Export Studio and the guided demo.
const SHOTS = "../docs/screenshots";

test("Jerry answers with visuals, actions and an X-Ray of how it knows", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Signed in as").selectOption({ label: "Eli Novak (Engineer)" });
  await navTo(page, "Ask Copilot");
  const main = page.getByRole("main");
  await expect(main.getByTestId("jerry-welcome")).toBeVisible();

  await main.getByLabel("Ask the copilot").fill("Are we under attack?");
  await main.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(main.locator('[data-visual="radar"]').first()).toBeVisible();
  await expect(main.locator('[data-visual="heatmap"]').first()).toBeVisible();
  await expect(main.getByTestId("policy-chips").last()).toContainText("Policy applied");
  // Nothing says the company is compromised: the data is labelled synthetic.
  await expect(main.getByText(/synthetic/i).first()).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/40-jerry-threats.png`, fullPage: true });

  await main.getByRole("button", { name: "Show how Jerry knows" }).last().click();
  const xray = page.getByRole("dialog", { name: "Show how Jerry knows" });
  await expect(xray).toBeVisible();
  await expect(xray).not.toContainText(/password|secret|token/i);
  await xray.getByRole("button", { name: "Close" }).click();

  await main.getByLabel("Ask the copilot").fill("Which licenses are unused?");
  await main.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(main.locator('[data-visual="waterfall"]').first()).toBeVisible();
  await expect(main.getByText(/realized revenue/i)).toHaveCount(0);
});

test("containment: protected OT refused, endpoint preview is a dry run", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Signed in as").selectOption({ label: "Eli Novak (Engineer)" });
  await navTo(page, "Defense Command");
  await page.getByRole("tab", { name: /containment/i }).click();
  const main = page.getByRole("main");

  await main.getByLabel("Asset (explicit scope)").selectOption("OT-REFRIG-03");
  await main.getByRole("button", { name: "Preview (dry run)" }).click();
  const plan = main.getByTestId("containment-plan");
  await expect(plan).toContainText("✕ Protected environment");
  await expect(plan.getByRole("button", { name: "Propose for approval" })).toHaveCount(0);

  await main.getByLabel("Asset (explicit scope)").selectOption("WS-QA-014");
  await main.getByRole("button", { name: "Preview (dry run)" }).click();
  await expect(plan).toContainText("Rollback");
  await expect(plan.getByRole("button", { name: "Propose for approval" })).toBeVisible();
  await expect(main.getByText(/execution is always a dry run/)).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/41-containment.png`, fullPage: true });
});

test("team portfolio, connectors, export studio and guided demo", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Signed in as").selectOption({ label: "Eli Novak (Engineer)" });

  await navTo(page, "Team & delivery portfolio");
  const main = page.getByRole("main");
  await expect(main.getByRole("heading", { name: "What every team is building" })).toBeVisible();
  await expect(main.locator('[data-visual="gantt"]')).toBeVisible();
  await expect(main.getByText(/CANARY-RATING/)).toHaveCount(0);
  await page.screenshot({ path: `${SHOTS}/42-portfolio.png`, fullPage: true });

  await navTo(page, "Connect your enterprise");
  await expect(main.getByTestId("connector-databricks")).toBeVisible();
  await expect(main.getByTestId("connector-databricks")).not.toContainText(/^connected$/);

  await navTo(page, "Export Studio");
  await expect(main.getByRole("heading", { name: "Board-ready reports" })).toBeVisible();
  await expect(main.getByRole("button", { name: "Download PDF" }).first()).toBeVisible();

  await navTo(page, "Guided CTO demo");
  await main.getByRole("tab", { name: "Enterprise Defense Command" }).click();
  await main.getByTestId("demo-next").click();
  await expect(main.locator('[data-visual="radar"]').first()).toBeVisible();
  await main.getByTestId("demo-next").click();
  await expect(main.getByTestId("demo-next")).toHaveText("Next question");
  await page.screenshot({ path: `${SHOTS}/43-guided-defense.png`, fullPage: true });
});
