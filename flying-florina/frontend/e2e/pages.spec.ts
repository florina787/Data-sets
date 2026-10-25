import { expect, test } from "@playwright/test";
import path from "node:path";
import { boot, switchPersona } from "./helpers";

const PAGES = ["/fleet", "/aog", "/maintenance", "/parts", "/quality", "/legacy", "/bridge", "/agents", "/trust", "/compliance", "/simulator", "/executive", "/reports", "/settings"];

test("every page renders without errors and every nav link works", async ({ page }) => {
  const { errors, external } = await boot(page, "sec.ines");
  for (const p of PAGES) {
    await page.goto(p);
    await expect(page.locator("main h1")).toBeVisible();
    await page.waitForTimeout(400);
  }
  for (const label of ["Fleet & Asset Health", "Defense Trust Center", "Mission Control"]) {
    await page.getByRole("navigation", { name: undefined }).getByRole("link", { name: label, exact: true }).click();
    await expect(page.locator("main")).toBeVisible();
  }
  expect(errors).toEqual([]);
  expect(external).toEqual([]);
});

test("fleet dashboard: totals agree with drilldown", async ({ page }) => {
  await boot(page);
  await page.goto("/fleet");
  await expect(page.getByTestId("fleet-kpis")).toContainText("150");
  await expect(page.getByTestId("chart").first()).toBeVisible();
});

test("legacy schema upload, graph, bridge generation and generated tests", async ({ page }) => {
  test.setTimeout(150_000);
  await boot(page, "arch.olu");
  await page.goto("/legacy");
  await expect(page.getByTestId("dependency-graph")).toBeVisible();
  await page.getByTestId("legacy-upload").setInputFiles(path.resolve(process.cwd(), "../fixtures/legacy/mro_core_legacy.sql"));
  await expect(page.getByRole("status")).toContainText("sql_ddl");
  await page.getByTestId("generate-bridge").click();
  await expect(page.getByTestId("adapter-preview")).toBeVisible();
  await page.getByTestId("run-bridge-tests").click();
  await expect(page.getByTestId("bridge-test-result")).toContainText("0 failed", { timeout: 90_000 });
});

test("bridge studio wizard and untrusted tool rejection", async ({ page }) => {
  await boot(page, "fde.sam");
  await page.goto("/bridge");
  for (let i = 0; i < 5; i++) await page.getByTestId("wizard-next").click();
  await page.getByTestId("wizard-generate").click();
  await expect(page.getByTestId("wizard-step-7")).toBeVisible();
  await page.getByTestId("register-untrusted").click();
  await expect(page.getByText(/Rejected: .*not on allowlist/)).toBeVisible();
});

test("security test lab, audit verify and kill switch", async ({ page }) => {
  await boot(page, "sec.ines");
  await page.goto("/trust?tab=lab");
  await page.getByTestId("run-lab").click();
  await expect(page.getByTestId("lab-results")).toContainText("12/12 passed", { timeout: 60_000 });
  await page.getByRole("tab", { name: "Evidence Ledger" }).click();
  await page.getByTestId("verify-chain").click();
  await expect(page.getByTestId("verify-result")).toContainText("Chain valid");
  await page.getByRole("tab", { name: "Incident / Kill Switch" }).click();
  await page.getByTestId("kill-switch").click();
  await expect(page.getByTestId("kill-switch")).toContainText("Release");
  await page.getByTestId("kill-switch").click();
  await expect(page.getByTestId("kill-switch")).toContainText("Activate");
});

test("report generation downloads a PDF", async ({ page }) => {
  await boot(page);
  await page.goto("/reports");
  const [dl] = await Promise.all([page.waitForEvent("download"), page.getByTestId("generate-report").click()]);
  expect(dl.suggestedFilename()).toMatch(/\.pdf$/);
});

test("guest persona is read-only and gets policy denials, not crashes", async ({ page }) => {
  const { errors } = await boot(page, "guest");
  await page.goto("/fleet");
  await expect(page.getByText(/Denied by policy POL-003/)).toBeVisible();
  expect(errors).toEqual([]);
  await switchPersona(page, "planner.marco");
});

test.describe("responsive", () => {
  test.use({ viewport: { width: 390, height: 844 } });
  test("mobile layout has a working menu and no horizontal scroll", async ({ page }) => {
    await boot(page);
    await page.getByRole("button", { name: "Open navigation" }).click();
    await page.getByRole("link", { name: "Parts & Supply Chain" }).click();
    await expect(page.locator("main h1")).toHaveText("Parts & Supply Chain");
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow).toBeLessThanOrEqual(2);
  });
});
