import { expect, Page, test } from "@playwright/test";
import { STORE } from "./playwright.config";

// Browser verification of the flagship workflow, driven through the real UIs:
// clarification -> failing test -> diff -> same test passing -> blocked unauthorised
// approval -> authorised deployment -> working storefront -> injected timeout ->
// incident evidence -> rollback + reviewed repair -> verified recovery.

const SHOTS = "../docs/screenshots";
const LONG = { timeout: 180_000 };

async function signIn(page: Page, displayName: string) {
  await page.getByLabel("Signed in as").selectOption({ label: displayName });
  await expect(page.getByLabel("Signed in as")).toHaveValue(/./);
  await page.waitForTimeout(300);
}

async function go(page: Page, label: string) {
  await page.getByRole("navigation", { name: "Primary" }).getByRole("link", { name: label }).click();
}

async function shot(page: Page, name: string) {
  await page.screenshot({ path: `${SHOTS}/${name}.png`, fullPage: true });
}

test("flagship delivery, release and incident workflow", async ({ page, context }) => {
  page.on("dialog", (dialog) => dialog.accept());
  await page.goto("/");
  await expect(page.getByText("DEMO ENVIRONMENT")).toBeVisible();
  await expect(page.getByText(/release REL-BASELINE/)).toBeVisible();

  // A. Clarify before building
  await signIn(page, "Maya Chen (Marketing)");
  await go(page, "Brief intake");
  await page.getByRole("button", { name: "Submit brief" }).click();
  await expect(page.getByText("The Brief Analyst has finished its analysis")).toBeVisible(LONG);
  const once = page.locator("li", { hasText: "Q-ONCE" }).first();
  await expect(once).toContainText("Customer limit scope");
  await expect(once).toContainText("Policy gap");
  await shot(page, "01-brief-clarifications");

  await signIn(page, "Eli Novak (Engineer)");
  await page.getByRole("button", { name: "Try to start implementation" }).click();
  await expect(page.getByText(/Blocked by server: Implementation cannot start/)).toBeVisible();

  await signIn(page, "Maya Chen (Marketing)");
  await page.getByRole("button", { name: "Apply seeded demo decisions" }).click();
  await expect(page.getByText("Seeded demo decisions recorded and labelled.")).toBeVisible();
  await expect(page.getByText("Selected demo decision").first()).toBeVisible();
  await page.getByRole("button", { name: "Continue workflow" }).click();
  await expect(page.getByText("Workflow advanced to the next human gate.")).toBeVisible(LONG);

  // B. Requirements approval, then the faulty test fails and the same test passes after repair
  await signIn(page, "Omar Haddad (Product Owner)");
  await go(page, "Requirements");
  await page.getByRole("button", { name: "Approve v1" }).click();
  await expect(page.getByText(/Requirement set v1 approved/)).toBeVisible();
  await go(page, "Delivery board");
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await expect(page.getByText("Workflow advanced until the next human gate")).toBeVisible(LONG);
  await expect(page.getByText(/Waiting for a human: release approval and deploy/)).toBeVisible();
  await shot(page, "02-delivery-board");

  await go(page, "Quality");
  const rows = page.locator("table").first().locator("tbody tr");
  await expect(rows).toHaveCount(2);
  await rows.nth(0).getByRole("radio").check();
  await expect(rows.nth(0)).toContainText("failed");
  await expect(page.getByLabel("pytest output")).toContainText("FAILED");
  await expect(page.getByLabel("pytest output")).toContainText("test_removing_qualifying_paid_units_removes_the_free_unit");
  await shot(page, "03-quality-failing-regression");
  await rows.nth(1).getByRole("radio").check();
  await expect(rows.nth(1)).toContainText("passed");
  await expect(page.getByLabel("pytest output")).toContainText("passed");
  await shot(page, "04-quality-passing-after-repair");

  await go(page, "Engineering");
  await page.getByRole("button", { name: /Re-derive free-unit entitlement/ }).click();
  await expect(page.getByLabel("Unified diff")).toContainText("promotions.remove_free_unit(conn, cart_id)");
  await shot(page, "05-engineering-diff");

  await go(page, "Requirements");
  await expect(page.getByText("gap: no test evidence")).toHaveCount(0);
  await shot(page, "06-requirements-traceability");

  // Unauthorised approval is rejected server-side; authorised approval binds to the manifest
  await signIn(page, "Eli Novak (Engineer)");
  await go(page, "Release center");
  await page.getByRole("button", { name: /Approve manifest/ }).click();
  await expect(page.getByText(/not permitted to perform release.approve/)).toBeVisible();
  await signIn(page, "Rina Das (Release Approver)");
  await page.getByRole("button", { name: /Approve manifest/ }).click();
  await expect(page.getByText("Approval recorded for this exact revision and manifest.")).toBeVisible();
  await page.getByRole("button", { name: "Deploy to local storefront" }).click();
  await expect(page.getByText("Deployed and health-checked.")).toBeVisible(LONG);
  await shot(page, "07-release-center-deployed");

  // Functioning storefront on the deployed revision
  const store = await context.newPage();
  await store.goto(STORE);
  await expect(store.getByText("DEMO STORE")).toBeVisible();
  await expect(store.getByText(/FreshSip Ontario Weekend/)).toBeVisible();
  await store.getByLabel("Customer fixture").selectOption({ label: "Amara Okafor (demo)" });
  await store.getByRole("button", { name: "Add one FreshSip Mango" }).click();
  await expect(store.getByLabel("FreshSip Mango quantity")).toHaveText("1");
  await store.getByRole("button", { name: "Add one FreshSip Mango" }).click();
  await expect(store.getByLabel("FreshSip Mango quantity")).toHaveText("2");
  await store.getByLabel("Ship to province").selectOption("ON");
  await store.getByRole("button", { name: "Add free unit" }).click();
  await expect(store.getByText("FREE", { exact: true })).toBeVisible();
  await store.getByRole("button", { name: "Remove one FreshSip Mango" }).click();
  await expect(store.getByText(/Free unit removed/)).toBeVisible();
  await store.getByRole("button", { name: "Add one FreshSip Mango" }).click();
  await expect(store.getByLabel("FreshSip Mango quantity")).toHaveText("2");
  await store.getByRole("button", { name: "Add free unit" }).click();
  await expect(store.getByText("$4.98").first()).toBeVisible();
  await store.getByRole("button", { name: "Place order (mock payment)" }).click();
  await expect(store.getByLabel("Order result")).toContainText("Status: paid");
  await shot(store, "08-storefront-order");

  // C. Injected timeout -> real failures -> incident evidence
  await page.bringToFront();
  await signIn(page, "Eli Novak (Engineer)");
  await go(page, "Incidents");
  await page.getByRole("button", { name: "Inject inventory timeout" }).click();
  await expect(page.getByText("Injected fault active: inventory timeout")).toBeVisible();
  await page.getByRole("button", { name: "Send synthetic shopper traffic" }).click();
  await expect(page.getByText(/checkout_500/)).toBeVisible(LONG);
  await page.getByRole("button", { name: "Analyse telemetry" }).click();
  await expect(page.getByText("Incident analysis complete.")).toBeVisible(LONG);
  await expect(page.getByText("Scripted fault demonstration.").first()).toBeVisible();
  await expect(page.getByText("Hypotheses (not proven)")).toBeVisible();
  await expect(page.getByText(/timeout=None/).first()).toBeVisible();
  await shot(page, "09-incident-evidence");

  // Mitigation: approved rollback to the last known good release
  await signIn(page, "Rina Das (Release Approver)");
  await go(page, "Release center");
  await page.getByRole("button", { name: "Roll back to last-known-good" }).click();
  await expect(page.getByText("Rollback deployed and health-checked.")).toBeVisible(LONG);

  // Reviewed repair release: REQ-9 approved, regression fails on release and passes on repair
  await signIn(page, "Omar Haddad (Product Owner)");
  await go(page, "Requirements");
  await page.getByRole("button", { name: "Approve v2" }).click();
  await expect(page.getByText(/Requirement set v2 approved/)).toBeVisible();
  await go(page, "Delivery board");
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await expect(page.getByText("Workflow advanced until the next human gate")).toBeVisible(LONG);
  await signIn(page, "Rina Das (Release Approver)");
  await go(page, "Release center");
  await page.getByRole("button", { name: /Approve manifest/ }).click();
  await expect(page.getByText("Approval recorded for this exact revision and manifest.")).toBeVisible();
  await page.getByRole("button", { name: "Deploy to local storefront" }).click();
  await expect(page.getByText("Deployed and health-checked.")).toBeVisible(LONG);
  await shot(page, "10-release-center-repair");

  // Corrected storefront under the fault: fails fast, keeps the cart, creates no order
  await store.bringToFront();
  await store.reload();
  await expect(store.getByText(/code v1\.2\.0/)).toBeVisible();
  await store.getByRole("button", { name: "Add one FreshSip Apple" }).click();
  await expect(store.getByLabel("FreshSip Apple quantity")).toHaveText("1");
  await store.getByLabel("Ship to province").selectOption("ON");
  await store.getByRole("button", { name: "Place order (mock payment)" }).click();
  await expect(store.getByRole("alert")).toContainText("Checkout temporarily unavailable");
  await expect(store.getByRole("alert")).toContainText("Your cart has been saved");
  await expect(store.getByLabel("FreshSip Apple quantity")).toHaveText("1");
  await shot(store, "11-storefront-temporarily-unavailable");

  // Recovery after the fault is cleared, verified by the incident flow
  await page.bringToFront();
  await signIn(page, "Eli Novak (Engineer)");
  await go(page, "Incidents");
  await page.getByRole("button", { name: "Clear injected fault" }).click();
  await expect(page.getByText(/Fault cleared/)).toBeVisible();
  await expect(page.getByRole("button", { name: /INC-.*resolved/ })).toBeVisible(LONG);
  await shot(page, "12-incident-resolved");

  await store.bringToFront();
  await store.getByRole("button", { name: "Place order (mock payment)" }).click();
  await expect(store.getByLabel("Order result")).toContainText("Status: paid");

  await page.bringToFront();
  await go(page, "Delivery overview");
  await shot(page, "13-overview");
  await go(page, "Evidence & audit");
  await expect(page.getByText("release.approve").first()).toBeVisible();
  await shot(page, "14-evidence-audit");
});
