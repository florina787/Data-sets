import { expect, Page, test } from "@playwright/test";

async function persona(page: Page, label: RegExp) {
  const select = page.getByLabel(/Demo persona/);
  const option = select.locator("option", { hasText: label });
  await select.selectOption(await option.getAttribute("value") as string);
  await expect(page.getByRole("heading", { name: /Sign in with a demo persona/ })).toHaveCount(0);
}

test("primary journey: investigate, approve, execute, verify, audit", async ({ page }) => {
  await page.goto("/#/workspace/C-1003");
  await expect(page.getByText("Independent telecom prototype — synthetic data.")).toBeVisible();
  await expect(page.getByText(/Generation:/)).toContainText("DEMO");
  await persona(page, /Ava Moreau/);
  await page.goto("/#/workspace/C-1003");
  await expect(page.getByRole("heading", { name: /C-1003/ })).toBeVisible();
  await page.getByRole("button", { name: "Run investigation" }).click();
  await expect(page.getByText("Create technician dispatch (simulated)")).toBeVisible({ timeout: 20_000 });
  await expect(page.locator(".card").filter({ hasText: "Evidence and hypotheses" })).toContainText("Suspected cause");
  await expect(page.getByText(/Your persona \(specialist\) cannot decide it/)).toBeVisible();
  await page.screenshot({ path: "e2e-results/01-recommendation.png", fullPage: true });

  // open a citation
  await page.getByRole("button", { name: "Open source DIAG-SNR" }).first().click();
  await expect(page.getByRole("dialog")).toContainText("Verified against source");
  await page.screenshot({ path: "e2e-results/02-citation.png" });
  await page.getByRole("button", { name: "Close" }).click();

  // supervisor approves
  await persona(page, /Emma Laurent/);
  await page.goto("/#/workspace/C-1003");
  await page.getByRole("button", { name: "Approve" }).click();
  await expect(page.locator(".card").filter({ hasText: "Recommendation" }).first()).toContainText("Approval approved");
  // field coordinator executes
  await persona(page, /Dev Singh/);
  await page.goto("/#/workspace/C-1003");
  await page.getByRole("button", { name: "Execute (simulated)" }).click();
  await expect(page.getByText(/Execution EXE-/)).toBeVisible();
  await page.getByRole("button", { name: "Verify recovery" }).click();
  await expect(page.locator(".recovery")).toContainText("Resolved (recovery verified)");
  await page.screenshot({ path: "e2e-results/03-resolved.png", fullPage: true });

  await page.goto("/#/audit/C-1003");
  await persona(page, /Emma Laurent/);
  await page.goto("/#/audit/C-1003");
  await expect(page.getByText("Hash chain intact")).toBeVisible();
});

test("insufficient evidence case abstains", async ({ page }) => {
  await page.goto("/");
  await persona(page, /Ava Moreau/);
  await page.goto("/#/workspace/C-1004");
  await page.getByRole("button", { name: "Run investigation" }).click();
  await expect(page.getByRole("heading", { name: "Insufficient evidence" }).first()).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText(/Request for further evidence/)).toBeVisible();
  await expect(page.getByText("Create technician dispatch (simulated)")).toHaveCount(0);
  await page.screenshot({ path: "e2e-results/04-insufficient.png", fullPage: true });
});

test("cross-tenant case is not visible", async ({ page }) => {
  await page.goto("/");
  await persona(page, /Ava Moreau/);
  await page.goto("/#/workspace/C-1012");
  await expect(page.getByRole("alert")).toContainText("Case not found in your scope");
});

test("overview and evaluation render from persisted data", async ({ page }) => {
  await page.goto("/");
  await persona(page, /Emma Laurent/);
  await page.goto("/#/overview");
  await expect(page.getByText("Cases in scope")).toBeVisible();
  await page.goto("/#/evaluation");
  await expect(page.locator("main")).toContainText(/Latest evaluation|No evaluation runs recorded/);
});
