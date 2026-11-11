import { expect, test } from "@playwright/test";

// Global supply-chain maps: one reusable component on several pages, a shared geographic
// selection, provenance labels, OriginTrace, reduced motion and a phone-width layout.
const SHOTS = "../docs/screenshots";

test("global supply map: drill-down, shared selection, OriginTrace", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Signed in as").selectOption({ label: "Val Park (Viewer)" });
  const map = page.getByTestId("supply-map").first();
  await map.scrollIntoViewIfNeeded();
  await expect(map.getByText(/161 countries, USD 2.40B annual revenue/)).toBeVisible();
  await expect(map.getByText(/not verified business facts/)).toBeVisible();
  await expect(map.getByTestId("prov-verified")).toHaveText(/0$/);
  await expect(map).toHaveAttribute("data-render-ms", /^\d+$/, { timeout: 15_000 });
  expect(Number(await map.getAttribute("data-render-ms"))).toBeLessThan(5000);

  // 2D map, then drill down: country -> site, through the keyboard-accessible table.
  await map.getByRole("button", { name: "2D map" }).click();
  await expect(map.getByTestId("map-2d")).toBeVisible();
  await map.locator("summary").click();
  await map.getByRole("button", { name: "Select Peru" }).click();
  const crumbs = map.getByRole("navigation", { name: "Geographic selection" });
  await expect(crumbs.getByRole("button", { name: "Peru" })).toBeVisible();
  await expect(page).toHaveURL(/geo=c%3A604/);
  const site = map.getByRole("button", { name: /^Select Synthetic .* Peru/ }).first();
  await site.click();
  await expect(crumbs.getByRole("button", { name: /GEO-/ })).toBeVisible();
  await map.getByRole("tab", { name: "Forecast & risk" }).click();
  await expect(map.getByTestId("risk-bands").getByText("180 days")).toBeVisible();
  await map.getByRole("tab", { name: "OriginTrace" }).click();
  await expect(map.getByRole("list", { name: "Upstream paths" })).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/38-global-supply-map.png`, fullPage: false });

  // The selection follows the user to another dashboard and survives a reload.
  const chip = page.getByTestId("geo-chip");
  await expect(chip).toContainText("Peru › GEO-");
  await page.getByRole("navigation", { name: "Primary" }).getByRole("link", { name: "Inventory" }).click();
  await expect(chip).toContainText("Peru › GEO-");
  await expect(page.getByTestId("supply-map").getByRole("navigation", { name: "Geographic selection" }).getByRole("button", { name: "Peru" })).toBeVisible();
  await page.reload();
  await expect(page.getByTestId("geo-chip")).toContainText("Peru › GEO-");

  // OriginTrace answers in the copilot with citations.
  await page.getByTestId("supply-map").getByRole("button", { name: "Investigate with OriginTrace" }).click();
  const drawer = page.getByRole("complementary", { name: "Ask Copilot" });
  await expect(drawer.getByText(/OriginTrace for Synthetic/)).toBeVisible();
  await expect(drawer.getByText(/Modelled risk \(scenario, not a forecast/)).toBeVisible();
  await drawer.getByRole("button", { name: "Close" }).click();

  // Quality Intelligence opens on the incidents view of the same component.
  await page.getByRole("navigation", { name: "Primary" }).getByRole("link", { name: "Quality Intelligence" }).click();
  const qmap = page.getByTestId("supply-map");
  await expect(qmap.getByRole("tab", { name: "Quality incidents" })).toHaveAttribute("aria-selected", "true");
  await page.getByTestId("geo-chip").getByRole("button", { name: "Clear geographic selection" }).click();
  await expect(page.getByTestId("geo-chip")).toHaveCount(0);
  await expect(page).not.toHaveURL(/geo=/);
});

test("reduced motion starts on the 2D map; phone width has no sideways scroll", async ({ browser }) => {
  const ctx = await browser.newContext({ reducedMotion: "reduce", viewport: { width: 390, height: 844 } });
  const page = await ctx.newPage();
  await page.goto("/");
  const map = page.getByTestId("supply-map");
  await map.scrollIntoViewIfNeeded();
  await expect(map).toHaveAttribute("data-mode", "2d");
  await expect(map.getByTestId("map-2d")).toBeVisible();
  const overflow = await page.evaluate(() => document.scrollingElement!.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
  await ctx.close();
});
