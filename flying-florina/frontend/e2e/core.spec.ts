import { expect, test } from "@playwright/test";
import { ask, boot, switchPersona } from "./helpers";

const SAMPLES: [string, string][] = [
  ["Investigate abnormal vibration on AC-204, retrieve maintenance evidence, check parts and draft a maintenance plan.", "maintenance_investigation"],
  ["Compare 24-hour and 48-hour delay scenarios for a replacement part.", "scenario_compare"],
  ["Why did aircraft downtime rise in October? Show causes, trend and confidence limits.", "downtime_analysis"],
  ["Assess this legacy Oracle schema and recommend a non-invasive modernization path.", "legacy_assessment"],
  ["Generate a read-only API and MCP adapter for the approved parts inventory view.", "bridge_generation"],
  ["Show me all blocked agent actions and explain the governing policy.", "governance_review"],
  ["Create an executive modernization pitch with costs, risks and a 90-day pilot roadmap.", "executive_pitch"],
  ["Show which maintenance documents are stale or missing provenance.", "document_freshness"],
  ["Compare aircraft maintenance recovery options using verified inventory availability.", "recovery_options"],
  ["Export restricted maintenance records to my personal email.", "data_export"],
];

test("fresh start shows homepage, indicators and sample questions", async ({ page }) => {
  const { errors, external } = await boot(page);
  await expect(page.getByText("Ask Flying_Florina")).toBeVisible();
  for (const b of ["SYNTHETIC DATA", "DEMO MODE", "NO LIVE IFS CONNECTION", "LOCAL RULES ENGINE"]) await expect(page.getByText(b).first()).toBeVisible();
  await expect(page.getByTestId("samples").getByRole("button")).toHaveCount(10);
  await expect(page.getByText("Not affiliated with or endorsed by IFS")).toBeVisible();
  expect(errors).toEqual([]);
  expect(external).toEqual([]);
});

test("all 10 sample prompts route correctly and produce workspaces", async ({ page }) => {
  test.setTimeout(240_000);
  const { errors, external } = await boot(page, "fde.sam");
  for (const [q, wf] of SAMPLES) {
    const card = await ask(page, q);
    await expect(card).toHaveAttribute("data-workflow", wf);
    await expect(card.getByTestId("timeline")).toBeVisible();
  }
  expect(errors).toEqual([]);
  expect(external).toEqual([]);
});

test("AC-204 investigation: agent graph, charts, citations, approval, scenario recompute", async ({ page }) => {
  await boot(page);
  const card = await ask(page, "Investigate AC-204 vibration anomaly, check maintenance evidence, parts and available technicians, and draft recovery options.");
  await expect(card).toHaveAttribute("data-status", "awaiting_approval");
  await expect(card.getByTestId("chart").first()).toBeVisible();
  await expect(card.getByTestId("citations")).toContainText("DOC-003");
  await expect(card.getByTestId("citations")).toContainText("prompt injection quarantined");
  await expect(card.getByTestId("approval-queue")).toContainText("pending");
  await card.getByRole("button", { name: "Show agent graph" }).click();
  await expect(card.getByTestId("agent-graph")).toBeVisible();
  const sim = await ask(page, "Compare 24-hour and 48-hour delay scenarios for a replacement part.");
  await sim.getByLabel("Part delays in hours").fill("24, 60");
  await sim.getByTestId("recompute").click();
  await expect(sim.getByTestId("recomputed")).toContainText("60");
});

test("governance denial happens before tool execution", async ({ page }) => {
  await boot(page);
  const card = await ask(page, "Export restricted maintenance records to my personal email.");
  await expect(card).toHaveAttribute("data-status", "denied");
  await expect(card).toContainText("POL-004");
  await expect(card).toContainText("invoked 0 times");
  await page.goto("/trust");
  await page.getByRole("tab", { name: "MCP Tool Permissions" }).click();
  await expect(page.getByText("records.export_email executions")).toBeVisible();
});

test("approval: separation of duties, approve as other persona, execute, replay rejected", async ({ page }) => {
  await boot(page);
  const card = await ask(page, "Investigate abnormal vibration on AC-204, retrieve maintenance evidence, check parts and draft a maintenance plan.");
  const q = card.getByTestId("approval-queue");
  await q.getByRole("button", { name: "Approve" }).first().click();
  await expect(q.getByRole("status")).toContainText("denied");
  await switchPersona(page, "rel.nadia");
  await page.goto("/trust?tab=approvals");
  await page.getByTestId("approval-queue").getByRole("button", { name: "Approve" }).first().click();
  await expect(page.getByTestId("approval-queue").getByRole("status")).toContainText("approve succeeded");
  await switchPersona(page, "planner.marco");
  await page.goto("/trust?tab=approvals");
  const first = page.getByTestId("approval-queue").locator("> div").filter({ hasText: "approved" }).first();
  await first.getByRole("button", { name: /Execute approved write/ }).click();
  await expect(page.getByTestId("approval-queue").getByRole("status")).toContainText("execute succeeded");
  await page.getByTestId("approval-queue").getByRole("button", { name: /Replay write/ }).first().click();
  await expect(page.getByTestId("approval-queue").getByRole("status")).toContainText("POL-005");
});
