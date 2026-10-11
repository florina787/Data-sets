import { expect, Page, test } from "@playwright/test";

// Full seeded BR-101 journey through the UI, switching demo personas. Results are computed live by
// the backend from fixtures; the test asserts on computed gate statuses, not hard-coded screens.

async function as(page: Page, persona: string) {
  await page.getByTestId("persona").selectOption(persona);
}
async function tab(page: Page, name: string) {
  await page.getByRole("navigation", { name: "Change sections" }).getByRole("link", { name, exact: true }).click();
}
async function status(page: Page, s: string) {
  await expect(page.locator("h1 + .row .badge").first()).toHaveAttribute("data-status", s, { timeout: 60_000 });
}

test("BR-101: clarify → evidence → impact → failing candidate blocked → corrected candidate → approval → canary → alert → rollback", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("banner")).toContainText("Independent beauty AI prototype — synthetic evaluation data");
  await page.getByTestId("open-BR-101").click();
  await status(page, "NEEDS_CLARIFICATION");

  // Requirements: resolve ambiguity with configured demo clarifications, approve.
  await as(page, "u-po");
  await tab(page, "Requirements");
  await page.getByTestId("use-all-demo").click();
  await page.getByTestId("approve-requirements").click();
  await status(page, "REQUIREMENTS_APPROVED");

  // Evidence + impact.
  await as(page, "u-ml-eng");
  await tab(page, "Evidence");
  await page.getByTestId("investigate").click();
  await status(page, "IMPACT_REVIEW");
  await page.getByTestId("source-link").first().click();
  await expect(page.getByTestId("excerpt")).toBeVisible();
  await page.getByRole("button", { name: "Close" }).click();
  await expect(page.getByText("Instruction-like text ignored")).toBeVisible();
  await as(page, "u-po");
  await tab(page, "Impact");
  await page.getByTestId("accept-impact").click();
  await status(page, "DEVELOPMENT");

  // Failing candidate rc1.
  await as(page, "u-cv-eng");
  await tab(page, "Development");
  await page.getByTestId("register-shade-matcher-v2.4.0-rc1").click();
  await as(page, "u-ml-eng");
  await page.getByTestId("run-evaluation").click();
  await status(page, "EVALUATION_FAILED");
  await tab(page, "Evaluation");
  await expect(page.locator('[data-gate="G-NO-REGRESSION"]')).toHaveAttribute("data-status", "FAIL");
  await expect(page.locator('[data-gate="G-TARGET"]').first()).toHaveAttribute("data-status", "PASS");
  await page.getByTestId("cell-TS-3|cool_fluorescent").click();
  await expect(page.getByTestId("cell-TS-3|cool_fluorescent")).toContainText("beyond limit");

  // Corrected candidate rc2.
  await as(page, "u-cv-eng");
  await tab(page, "Development");
  await page.getByTestId("register-shade-matcher-v2.4.0-rc2").click();
  await status(page, "DEVELOPMENT");
  await as(page, "u-qa");
  await page.getByTestId("approve-code").click();
  await as(page, "u-ml-eng");
  await page.getByTestId("run-evaluation").click();
  await status(page, "REVIEW_REQUIRED");

  // Reviews and distinct release approval.
  await tab(page, "Approvals");
  await as(page, "u-domain");
  await page.getByTestId("review-domain").click();
  await as(page, "u-privacy");
  await page.getByTestId("review-privacy").click();
  await as(page, "u-release");
  await page.getByTestId("approve-release").click();
  await status(page, "RELEASE_APPROVED");

  // Simulated canary and monitoring.
  await tab(page, "Release");
  await page.getByTestId("start-canary").click();
  await status(page, "CANARY");
  await tab(page, "Monitoring");
  for (let i = 0; i < 6; i++) {
    await as(page, "u-ops");
    await page.getByTestId("advance-window").click();
    await page.waitForTimeout(300);
    if (await page.getByTestId("investigate-alert").count()) break;
    await as(page, "u-release");
    await tab(page, "Release");
    await page.getByTestId("promote").click();
    await page.waitForTimeout(300);
    await tab(page, "Monitoring");
  }
  await expect(page.getByText("DEV-T3|warm_indoor").first()).toBeVisible();
  await page.getByTestId("investigate-alert").click();
  await expect(page.getByText("Suspected cause:")).toBeVisible();
  await status(page, "ROLLBACK_RECOMMENDED");
  await page.getByTestId("request-rollback").click();
  await as(page, "u-release");
  await page.getByTestId("approve-rollback").click();
  await status(page, "ROLLED_BACK");

  await tab(page, "Audit");
  await expect(page.getByTestId("trace-chain")).toContainText("rollback EXECUTED");
  await expect(page.getByText(/chain valid/)).toBeVisible();
});

test("unauthorized action is refused by the server", async ({ page, request }) => {
  const r = await request.post("http://127.0.0.1:8000/api/changes/BR-101/requirements/approve", { headers: { "X-Demo-User": "u-cv-eng" } });
  expect(r.status()).toBe(403);
  await page.goto("/changes/BR-101/requirements");
  await page.getByTestId("persona").selectOption("u-cv-eng");
  await expect(page.getByTestId("approve-requirements")).toHaveCount(0);
});
