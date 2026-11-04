import { expect, test } from "@playwright/test";

// Model Evaluation Lab: registry honesty and a recorded evaluation on the SYNTHETIC set.
const SHOTS = "../docs/screenshots";

test("model evaluation lab records an evaluation with provenance", async ({ page }) => {
  test.setTimeout(4 * 60 * 1000);
  await page.goto("/");
  await page.getByLabel("Signed in as").selectOption({ label: "Eli Novak (Engineer)" });
  await page.getByRole("navigation", { name: "Primary" }).getByRole("link", { name: "Model Evaluation Lab" }).click();
  const main = page.getByRole("main");
  await expect(main.getByText("No trained model is registered yet.")).toBeVisible();
  await expect(main.getByRole("cell", { name: "potato-detector-classical@1.0" })).toBeVisible();
  await main.getByRole("button", { name: "Run evaluation on the synthetic set" }).click();
  await expect(main.getByText(/Evaluated 20 synthetic images/)).toBeVisible({ timeout: 180_000 });
  await expect(main.getByText(/mAP@50 1.000/).first()).toBeVisible();
  await expect(main.getByText("SYNTHETIC").first()).toBeVisible();
  await expect(main.getByLabel(/Confusion matrix/)).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/33-model-evaluation-lab.png`, fullPage: true });
});
