import { expect, test } from "@playwright/test";

// Persistent conversation memory: follow-ups, history sidebar, search, resume and delete.
const SHOTS = "../docs/screenshots";

test("conversation history: follow-up, search, resume and delete", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Signed in as").selectOption({ label: "Val Park (Viewer)" });
  await page.getByRole("navigation", { name: "Primary" }).getByRole("link", { name: "Ask Copilot" }).click();
  const main = page.getByRole("main");
  const history = main.getByRole("complementary", { name: "Conversation history" });
  await history.getByRole("button", { name: "New conversation" }).click();

  const ask = async (q: string) => {
    await main.getByLabel("Ask the copilot").fill(q);
    await main.getByRole("button", { name: "Ask", exact: true }).click();
  };
  await ask("Top selling products in Ontario last 8 weeks");
  await expect(main.getByText(/Sales, ON, last 8 week/).first()).toBeVisible();
  await ask("What about Quebec?");
  await expect(main.getByText(/Sales, QC, last 8 week/).first()).toBeVisible();
  await expect(main.getByText(/Follow-up: used the topic of your previous question/)).toBeVisible();
  await expect(history.getByRole("button", { name: /^Top selling products in Ontario/ })).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/26-conversation-history.png`, fullPage: true });

  // A second conversation, then search finds and resumes the first one.
  await history.getByRole("button", { name: "New conversation" }).click();
  await expect(main.getByText(/Sales, QC/)).toHaveCount(0);
  await ask("Which listings have allergen issues?");
  await expect(main.getByText(/oats \(gluten\)/).first()).toBeVisible();
  await history.getByLabel("Search earlier questions").fill("quebec");
  await history.getByRole("button", { name: "Search", exact: true }).click();
  await history.getByRole("button", { name: /^Top selling products in Ontario/ }).click();
  await expect(main.getByText(/Sales, QC, last 8 week/).first()).toBeVisible();

  // Survives a reload (server-side memory, not browser state).
  await page.reload();
  await page.getByRole("navigation", { name: "Primary" }).getByRole("link", { name: "Ask Copilot" }).click();
  const conv = history.getByRole("button", { name: /^Top selling products in Ontario/ });
  await expect(conv).toBeVisible();

  // Delete removes it from history.
  page.once("dialog", (d) => d.accept());
  await history.getByRole("button", { name: /Delete conversation: Top selling products in Ontario/ }).click();
  await expect(conv).toHaveCount(0);
});
