import { expect, test, type Page } from "@playwright/test";

const shots = process.env.E2E_SCREENSHOTS;

async function signIn(page: Page, name: string) {
  await page.goto("/");
  await page.getByRole("button", { name: new RegExp(name) }).click();
  await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();
}

test("patient journey: Christina chat finds earlier MRI options @mobile", async ({ page }) => {
  await signIn(page, "Demo Patient");
  await expect(page.getByText("DEMONSTRATION DATA").first()).toBeVisible();
  await page.goto("/christina");
  await expect(page.getByText("I'm Christina, your virtual healthcare access assistant").first()).toBeVisible();
  const input = page.getByLabel("Message Christina");
  await input.fill("I need an MRI. My appointment is three months away.");
  await input.press("Enter");
  await expect(page.getByText(/Do you have a physician's requisition/)).toBeVisible();
  await input.fill("Yes, I have a requisition");
  await input.press("Enter");
  await input.fill("Toronto. Search within 25 kilometres.");
  await input.press("Enter");
  await expect(page.getByText(/The earliest verified MRI opening is at Northgate/)).toBeVisible();
  if (shots) await page.screenshot({ path: `${shots}/christina-${test.info().project.name}.png`, fullPage: true });
  await page.getByRole("button", { name: /View full results/ }).click();
  await expect(page.getByRole("heading", { name: "Verified alternatives" })).toBeVisible();
  await expect(page.getByText("NOT CONFIRMED — contact provider").first()).toBeVisible();
  if (shots) await page.screenshot({ path: `${shots}/results-${test.info().project.name}.png`, fullPage: true });
});

test("emergency language interrupts the search", async ({ page }) => {
  await signIn(page, "Demo Patient");
  await page.goto("/christina");
  const input = page.getByLabel("Message Christina");
  await input.fill("I have chest pain and need a CT scan");
  await input.press("Enter");
  await expect(page.getByText(/call 911/).first()).toBeVisible();
});

test("booking handoff requires approval and is never shown as confirmed", async ({ page }) => {
  await signIn(page, "Demo Patient");
  await page.goto("/search/MRI");
  await page.getByRole("button", { name: "Search appointments" }).click();
  await expect(page.getByRole("heading", { name: "Verified alternatives" })).toBeVisible();
  await page.getByRole("button", { name: /Prepare booking handoff|Get contact instructions/ }).first().click();
  const dialog = page.getByRole("dialog");
  await dialog.getByRole("checkbox").check();
  await dialog.getByRole("button", { name: "Continue" }).click();
  await dialog.getByRole("button", { name: "Approve" }).click();
  await expect(dialog.getByText("Handoff ready — NOT CONFIRMED")).toBeVisible();
  if (shots) await page.screenshot({ path: `${shots}/booking-handoff.png` });
});

test("patients cannot see engineering navigation", async ({ page }) => {
  await signIn(page, "Demo Patient");
  const nav = page.getByRole("navigation", { name: "Main" });
  await expect(nav.getByText("AI-SDLC Command Center")).toHaveCount(0);
  await page.goto("/sdlc");
  await expect(page.getByText("Not available for your role")).toBeVisible();
});

test("AI-SDLC challenge: defect detected, fixed and released with approvals", async ({ page }) => {
  await signIn(page, "Demo Engineer");
  await page.goto("/sdlc");
  await page.getByLabel("Simulation volume").fill("60");
  await page.getByRole("button", { name: /Start the challenge|Restart challenge/ }).click();
  await expect(page.getByText("Human clarification required (Stage 3)")).toBeVisible();
  await page.getByRole("button", { name: /Record decision/ }).click();
  await expect(page.getByText("Release approval required (Stage 13)")).toBeVisible();
  await expect(page.getByText(/Waiting for a release approver/)).toBeVisible();
  if (shots) await page.screenshot({ path: `${shots}/sdlc-awaiting-release.png`, fullPage: true });
  await page.getByRole("button", { name: "Sign out" }).click();
  await signIn(page, "Demo Release Approver");
  await page.goto("/sdlc");
  await page.getByRole("button", { name: "Approve production deployment" }).click();
  await expect(page.getByText("Lifecycle complete")).toBeVisible();
  await page.getByRole("tab", { name: "root cause" }).click();
  await expect(page.getByText("Root cause confirmed with evidence")).toBeVisible();
  if (shots) await page.screenshot({ path: `${shots}/sdlc-complete.png`, fullPage: true });
});

test("no API keys or secrets in the served frontend", async ({ page }) => {
  const bodies: string[] = [];
  page.on("response", async (r) => { if (/\.(js|html)$/.test(new URL(r.url()).pathname) || r.url().endsWith("/")) bodies.push(await r.text().catch(() => "")); });
  await page.goto("/");
  await page.waitForLoadState("networkidle");
  for (const b of bodies) {
    expect(b).not.toMatch(/sk-ant-|ANTHROPIC_API_KEY|LANGSMITH_API_KEY|lsv2_/);
  }
});
