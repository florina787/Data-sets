import { expect, type Page } from "@playwright/test";

export async function boot(page: Page, user = "planner.marco") {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (m) => {
    if (m.type() === "error" && !m.text().includes("401") && !m.text().includes("403") && !m.text().includes("Failed to load resource")) errors.push(m.text());
  });
  // Offline guarantee: any request leaving loopback fails the test.
  const external: string[] = [];
  await page.route(/^(?!https?:\/\/(127\.0\.0\.1|localhost)[:/]).*/, (route) => {
    if (!route.request().url().startsWith("data:") && !route.request().url().startsWith("blob:")) external.push(route.request().url());
    return route.abort();
  });
  await page.goto("/");
  await expect(page.getByTestId("persona-select")).toBeVisible();
  if (user !== "planner.marco") await switchPersona(page, user);
  return { errors, external };
}

export async function switchPersona(page: Page, user: string) {
  await page.getByTestId("persona-select").selectOption(user);
  await expect(page.getByTestId("actor")).toContainText(user === "rel.nadia" ? "reliability_engineer" : "", { timeout: 10_000 });
  await page.waitForTimeout(300);
}

export async function ask(page: Page, query: string) {
  const before = await page.getByTestId("run-card").count();
  await page.getByTestId("prompt").fill(query);
  await page.getByTestId("ask").click();
  const card = page.getByTestId("run-card").nth(before);
  await expect(card.getByTestId("workspace")).toBeVisible({ timeout: 45_000 });
  return card;
}
