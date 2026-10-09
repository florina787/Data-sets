import { expect, test } from "@playwright/test";

// Enterprise copilot: executive overview, domain screens and grounded Q&A.
const SHOTS = "../docs/screenshots";

test("executive overview, domain screens and Ask Copilot", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Executive overview" })).toBeVisible();
  await expect(page.getByText("Revenue, last 4 weeks")).toBeVisible();
  await expect(page.getByText(/FreshSip Apple/).first()).toBeVisible(); // campaign stock risk surfaced
  await page.getByLabel("Signed in as").selectOption({ label: "Val Park (Viewer)" });
  await page.screenshot({ path: `${SHOTS}/20-executive-overview.png`, fullPage: true });

  // Copilot answers with citations from read-only tools.
  await page.getByRole("button", { name: "Ask Copilot for a briefing" }).click();
  const drawer = page.getByRole("complementary", { name: "Ask Copilot" });
  await expect(drawer.getByText("Briefing (synthetic data)")).toBeVisible();
  await expect(drawer.getByRole("button", { name: "S1" }).first()).toBeVisible();
  await expect(drawer.getByText("Deterministic answer from read-only queries")).toBeVisible();
  await drawer.getByLabel("Ask the copilot").fill("Is there enough apple stock for the Ontario weekend campaign?");
  await drawer.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(drawer.getByText(/high risk/).first()).toBeVisible();
  await expect(drawer.getByText(/PO-55102/).first()).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/21-copilot-drawer.png` });
  await drawer.getByRole("button", { name: "Close" }).click();

  // Honest refusal for questions outside the data.
  await page.getByRole("navigation", { name: "Primary" }).getByRole("link", { name: "Ask Copilot" }).click();
  await page.getByRole("main").getByLabel("Ask the copilot").fill("What is the weather in Paris?");
  await page.getByRole("main").getByRole("button", { name: "Ask", exact: true }).click();
  await expect(page.getByRole("main").getByText(/can't answer that from FoodCare's data/)).toBeVisible();
  await page.getByRole("main").getByLabel("Ask the copilot").fill("Which listings have allergen issues?");
  await page.getByRole("main").getByRole("button", { name: "Ask", exact: true }).click();
  await expect(page.getByRole("main").getByText(/oats \(gluten\)/).first()).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/22-copilot-page.png`, fullPage: true });

  // Domain screens.
  const nav = page.getByRole("navigation", { name: "Primary" });
  await nav.getByRole("link", { name: "Sales & promotions" }).click();
  await expect(page.getByText("Promotion uplift in units")).toBeVisible();
  await expect(page.getByText("Rentrée 3-for-2").first()).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/23-sales-promotions.png`, fullPage: true });
  await nav.getByRole("link", { name: "Inventory" }).click();
  await expect(page.getByText(/Days of cover, as of/)).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/24-inventory.png`, fullPage: true });
  await nav.getByRole("link", { name: "Product compliance" }).click();
  await expect(page.getByRole("main").getByText("listing is missing declared allergen(s): oats (gluten)")).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/25-product-compliance.png`, fullPage: true });
});
