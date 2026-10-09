import { expect, test } from "@playwright/test";

// The guided-demo controls: Reset Demo, Run Guided Demo, Pause (between steps), Continue.
test("guided demo controls reset, run, pause and continue", async ({ page }) => {
  page.on("dialog", (dialog) => dialog.accept());
  await page.goto("/");
  await page.getByLabel("Signed in as").selectOption({ label: "Eli Novak (Engineer)" });
  const header = page.getByRole("banner");

  await header.getByRole("button", { name: "Reset Demo" }).click();
  // Reset recreates the account store, so the session ends and the user signs in again.
  await expect(page.getByLabel("Signed in as")).toHaveValue("", { timeout: 120_000 });
  await page.getByLabel("Signed in as").selectOption({ label: "Eli Novak (Engineer)" });
  await expect(header.getByText("idle")).toBeVisible();

  await header.getByRole("button", { name: "Run Guided Demo" }).click();
  await expect(header.getByText("running")).toBeVisible();
  await header.getByRole("button", { name: "Pause" }).click();
  await expect(header.getByText("paused")).toBeVisible({ timeout: 120_000 });
  const done = page.locator("li", { hasText: "done" });
  const doneBefore = await done.count();
  expect(doneBefore).toBeGreaterThan(0);
  expect(doneBefore).toBeLessThan(13);

  await header.getByRole("button", { name: "Continue" }).click();
  await expect(header.getByText("done", { exact: true })).toBeVisible({ timeout: 300_000 });
  await expect(page.locator("ol li", { hasText: "done" })).toHaveCount(13);
  await expect(page.getByText("Injected fault active")).toHaveCount(0);
  await page.screenshot({ path: "../docs/screenshots/15-guided-demo-complete.png", fullPage: true });
});
