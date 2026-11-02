import { expect, test } from "@playwright/test";
import { ask, boot } from "./helpers";

test("global map: layers, timeline and facility drilldown use computed forecasts, offline", async ({ page }) => {
  const { errors, external } = await boot(page);
  await page.goto("/global");
  await expect(page.getByTestId("timeline")).toBeVisible();
  const kpi = page.getByText(/Removal demand P50/).locator("..");
  await expect(kpi).not.toContainText("…", { timeout: 90_000 });
  const at30 = await kpi.textContent();
  await page.getByRole("button", { name: "+90D" }).click();
  await expect(kpi).toContainText("+90d");
  expect(await kpi.textContent()).not.toEqual(at30);
  await page.getByRole("tab", { name: /Supply chain/ }).click();
  await page.getByRole("button", { name: "Lite" }).click();
  await expect(page.getByTestId("lite-map")).toBeVisible();
  await page.getByLabel("Search locations").fill("hamburg");
  await page.getByRole("button", { name: /Northwind MRO Hub/ }).click();
  await expect(page.getByTestId("facility-panel")).toBeVisible();
  expect(errors).toEqual([]);
  expect(external).toEqual([]);
});

test("chat: 3.0 question, memory follow-up, and agent trace", async ({ page }) => {
  const { errors } = await boot(page);
  await expect(page.getByTestId("suggested-3")).toBeVisible();
  const c1 = await ask(page, "Show hydraulic component shortages in Europe.");
  await expect(c1).toContainText("hydraulics components in Europe");
  const c2 = await ask(page, "What about the next 60 days?");
  await expect(c2).toContainText("+60 days");
  await expect(c2).toContainText("Europe");
  const c3 = await ask(page, "Show the agent execution graph.");
  await expect(c3).toContainText("Agent execution graph (recorded events)");
  expect(errors).toEqual([]);
});

test("forecasting accuracy, digital twin, supply delay simulation and resilience", async ({ page }) => {
  const { errors } = await boot(page);
  await page.goto("/forecasting?tab=accuracy");
  await expect(page.getByText("7-day backtest")).toBeVisible({ timeout: 90_000 });
  await page.goto("/twin");
  await expect(page.getByTestId("twin-detail")).toContainText("Why was this component flagged?", { timeout: 30_000 });
  await page.goto("/supply?supplier=S1");
  await page.getByTestId("run-delay").click();
  await expect(page.getByTestId("delay-result")).toContainText("affects", { timeout: 30_000 });
  await page.goto("/resilience");
  await expect(page.getByTestId("res-kpis")).toContainText("Peak backlog", { timeout: 30_000 });
  expect(errors).toEqual([]);
});

test("airspace lab is honest about capabilities; control tower shows recorded runs", async ({ page }) => {
  const { errors } = await boot(page);
  await page.goto("/airspace");
  await expect(page.getByTestId("vis-statement")).toContainText("No local vision model was found");
  await page.getByTestId("vis-gallery").getByRole("button").first().click();
  await expect(page.getByTestId("vis-result")).toContainText("Frame 0", { timeout: 20_000 });
  await page.goto("/");
  await ask(page, "Show historical forecast accuracy.");
  await page.goto("/control-tower");
  await expect(page.getByText("1 · Agent execution graph")).toBeVisible();
  await expect(page.getByLabel("Select run")).toContainText("forecast_accuracy");
  await page.goto("/change-impact");
  await expect(page.getByTestId("ci-summary")).toContainText("Resolved to", { timeout: 30_000 });
  expect(errors).toEqual([]);
});
