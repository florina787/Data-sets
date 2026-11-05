import { expect, test } from "@playwright/test";
import path from "path";

// Potato inspection studio on SYNTHETIC rendered images (drawn shapes, not photos).
const SHOTS = "../docs/screenshots";

test("potato inspection: upload, grade, inspect one potato, thresholds", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Signed in as").selectOption({ label: "Val Park (Viewer)" });
  await page.getByRole("navigation", { name: "Primary" }).getByRole("link", { name: "Potato Inspection" }).click();
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

  // Inspector correction: kept next to the rules' grade and counted in the summary.
  await main.getByText("Correct this grade (inspector review)").click();
  await main.getByLabel("New grade").selectOption("Good");
  await main.getByLabel(/Reason \(required/).fill("dark patch is soil, not rot");
  await main.getByRole("button", { name: "Save correction" }).click();
  await expect(main.getByText(/Inspector correction by val.viewer/)).toBeVisible();
  await expect(main.getByRole("img", { name: /^Quality: Good/ })).toBeVisible();
  await expect(main.getByText("Classical CV")).toBeVisible();

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

  // Ask the copilot about this batch, then about one potato (answers come from the stored results).
  await main.getByRole("button", { name: "Ask about this batch" }).click();
  const drawer = page.getByRole("complementary", { name: "Ask Copilot" });
  await expect(drawer.getByText(/12 potatoes detected/)).toBeVisible();
  await expect(drawer.getByText(/not a trained or validated defect classifier/).first()).toBeVisible();
  await drawer.getByLabel("Ask the copilot").fill("Show me potato #8");
  await drawer.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(drawer.getByRole("img", { name: /Potato #8 from inspection/ })).toBeVisible();
  await drawer.getByLabel("Ask the copilot").fill("Why was it rejected?");
  await drawer.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(drawer.getByText(/Potato #8/).last()).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/28-inspection-copilot.png` });
  await drawer.getByRole("button", { name: "Close" }).click();

  // Quality Intelligence aggregates the stored batches.
  await page.getByRole("navigation", { name: "Primary" }).getByRole("link", { name: "Quality Intelligence" }).click();
  await expect(main.getByText("Inspection recommendations")).toBeVisible();
  await expect(main.getByText(/Reject candidate · needs approval/).first()).toBeVisible();
  await main.getByRole("tab", { name: "Human review" }).click();
  await expect(main.getByText("Corrections", { exact: true })).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/34-quality-intelligence.png`, fullPage: true });
});
