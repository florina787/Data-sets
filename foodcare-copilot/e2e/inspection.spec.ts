import { expect, test } from "@playwright/test";
import path from "path";

// Potato inspection studio on SYNTHETIC rendered images (drawn shapes, not photos).
const SHOTS = "../docs/screenshots";

test("potato inspection: upload, grade, inspect one potato, thresholds", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Signed in as").selectOption({ label: "Val Park (Viewer)" });
  await page.getByRole("navigation", { name: "Primary" }).getByRole("link", { name: "Potato inspection" }).click();
  const main = page.getByRole("main");
  await expect(main.getByText(/classical image processing \(no trained model\)/)).toBeVisible();

  // Upload through the form.
  await main.getByLabel(/Photo of potatoes/).setInputFiles(path.join(__dirname, "fixtures", "synthetic-potatoes.jpg"));
  await main.getByLabel("Batch title").fill("Synthetic upload test");
  await main.getByLabel("Supplier").fill("Synthetic farm A");
  await main.getByRole("button", { name: "Inspect", exact: true }).click();
  const summary = main.getByLabel("Batch summary");
  await expect(summary.getByText("Detected")).toBeVisible();
  await expect(summary.locator(".text-2xl").first()).toHaveText("12");
  await expect(main.getByRole("img", { name: /Annotated inspection image with 12 numbered potato/ })).toBeVisible();

  // Inspect one potato.
  await main.getByRole("list", { name: "Potatoes" }).getByRole("listitem").nth(8).click();
  await expect(main.getByRole("img", { name: /Close-up of potato #9/ })).toBeVisible();
  await expect(main.getByText("Detection score")).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/27-potato-inspection.png`, fullPage: true });

  // Loosening the dark-area limit re-grades from stored measurements.
  const goodBefore = await summary.locator(".card").nth(1).locator(".text-2xl").innerText();
  await main.getByText(/Quality thresholds/).click();
  await main.getByLabel("max dark pct good").fill("50");
  await main.getByLabel("max dark pct moderate").fill("60");
  await main.getByRole("button", { name: "Apply thresholds" }).click();
  await expect(summary.locator(".card").nth(1).locator(".text-2xl")).not.toHaveText(goodBefore);

  // History lists it; the synthetic sample creates a second batch.
  await main.getByRole("button", { name: "Try a synthetic sample" }).click();
  await expect(main.getByRole("heading", { name: /Synthetic sample/ })).toBeVisible();
  await expect(main.getByRole("button", { name: /^Synthetic upload test/ })).toBeVisible();
});
