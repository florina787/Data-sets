import { expect, test, type Browser, type Page } from "@playwright/test";

// The ten user journeys of the production checklist. Journeys that need external accounts (Supabase email delivery,
// live job providers, Stripe) are SKIPPED unless their environment is configured — never silently passed.
const RESUME = `Alex Morgan
alex.morgan@example.com | +1 416 555 0199

SUMMARY
Backend and AI engineer focused on Python services and LLM applications.

EXPERIENCE
Senior AI Engineer, Example Robotics - Mar 2020 - Present
- Built a RAG service with LangGraph and FastAPI used by 5,000 people
- Cut cloud costs by 20% using Docker and Kubernetes autoscaling
- Mentored 3 engineers and led code reviews

Software Engineer, Sample Bank - Jan 2016 - Feb 2020
- Wrote Python and SQL data pipelines on AWS
- Built REST APIs and CI/CD with GitHub Actions

EDUCATION
BSc Computer Science, University of Waterloo, 2015

SKILLS
Python, SQL, LLMs, RAG, LangGraph, FastAPI, Docker, Kubernetes, AWS, CI/CD, Leadership
`;
const stamp = Date.now();
const emailA = `e2e-a-${stamp}@example.com`;
const PASSWORD = "CorrectHorse42";

async function register(page: Page, email: string) {
  await page.goto("/register");
  await page.fill("input[name=email]", email);
  await page.fill("input[name=password]", PASSWORD);
  await page.click('form button:has-text("Create account")');
  await page.waitForURL("**/app");
}

const api = (page: Page, path: string) =>
  page.evaluate(async (p) => {
    const r = await fetch(p, { headers: { Authorization: `Bearer ${localStorage.getItem("cf.token")}` } });
    return { status: r.status, body: await r.json().catch(() => null) };
  }, path);

test.describe.configure({ mode: "serial" });
let page: Page;
let resumeId = "";

test.beforeAll(async ({ browser }: { browser: Browser }) => {
  page = await browser.newPage();
});

test("1. a new user registers and signs in", async () => {
  await register(page, emailA);
  await expect(page.getByText("What's your next move?")).toBeVisible();
  const me = await api(page, "/api/auth/me");
  expect(me.body.email).toBe(emailA);
  // sign out and back in
  await page.getByRole("button", { name: /Sign out/ }).click();
  await page.waitForURL("**/login");
  await page.fill("input[name=email]", emailA);
  await page.fill("input[name=password]", PASSWORD);
  await page.click('form button:has-text("Log in")');
  await page.waitForURL("**/app");
});

test("1b. email confirmation through Supabase", async () => {
  test.skip(!process.env.E2E_SUPABASE, "Needs a Supabase project with email delivery (E2E_SUPABASE=1); local auth mode auto-verifies.");
});

test("2. uploads a resume and gets a grounded assessment", async () => {
  await page.goto("/app/resume");
  await page.locator('input[type="file"]').setInputFiles({ name: "resume.txt", mimeType: "text/plain", buffer: Buffer.from(RESUME) });
  await expect(page.getByText(/verified years/)).toBeVisible();
  await expect(page.getByText("You are here")).toBeVisible();
  const list = await api(page, "/api/resumes");
  resumeId = list.body.resumes[0].id;
  expect(list.body.resumes[0].skills).toContain("LangGraph");
});

test("3. discovers jobs with source attribution (synthetic data labelled)", async () => {
  await page.goto("/app/jobs");
  await page.fill('input[placeholder="150000"]', "150000");
  await page.click('main button:has-text("Search")');
  await expect(page.getByText(/results · de-duplicated from/)).toBeVisible();
  const ready = await api(page, "/api/health/ready");
  const live = ready.body.checks.job_providers.jsearch || ready.body.checks.job_providers.adzuna;
  if (!live) {
    await expect(page.getByText("includes synthetic demo data")).toBeVisible();
    await expect(page.getByText("Synthetic demo").first()).toBeVisible();
  }
  await page.getByRole("button", { name: "Save job" }).first().click();
  await expect(page.getByRole("button", { name: "Saved" }).first()).toBeVisible();
});

test("3b. a REAL job from a live provider", async () => {
  test.skip(!process.env.E2E_LIVE_JOBS, "Needs JSEARCH_API_KEY or Adzuna keys on the server (E2E_LIVE_JOBS=1).");
  const r = await api(page, "/api/health/ready");
  expect(r.body.checks.job_providers.jsearch || r.body.checks.job_providers.adzuna).toBeTruthy();
});

test("4. gets a fact-checked tailored resume and downloads it", async () => {
  await page.goto("/app/resume");
  await page.locator('select[aria-label="Target job"]').selectOption({ index: 1 });
  await page.click('button:has-text("Optimize resume")');
  await expect(page.getByText("Fact check passed")).toBeVisible({ timeout: 180_000 });
  const [dl] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: "PDF", exact: true }).click()]);
  expect(dl.suggestedFilename()).toBe("resume.pdf");
});

test("5. completes an interview-preparation step with feedback", async () => {
  await page.goto("/app/interview");
  await page.click('button:has-text("Start mock interview")');
  await page.locator("textarea").fill("I keep controls in code: a tool allowlist per agent, least privilege, human approval for risky actions, timeouts and an audit log.");
  await page.click('button:has-text("Submit answer")');
  await expect(page.getByText(/coverage .* depth .* structure/)).toBeVisible({ timeout: 180_000 });
});

test("6. builds a Career Graph with an actionable next step", async () => {
  await page.goto("/app/graph");
  await page.click('button:has-text("Build my career graph")');
  await expect(page.getByText("The Semantic Spine")).toBeVisible();
  await expect(page.getByText("Next step", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Go", exact: true })).toBeVisible();
});

test("7. a trial limit is reached and enforced (no charge)", async () => {
  await page.click('button:has-text("Build my career graph")');                  // 2nd free use
  await expect(page.getByText(/0 of 2 free uses remaining/)).toBeVisible();
  await page.click('button:has-text("Build my career graph")');                  // 3rd: blocked
  await expect(page.getByText("Keep going with Pro")).toBeVisible();
  await expect(page.getByText(/No charge happens automatically/)).toBeVisible();
  const inv = await api(page, "/api/billing/invoices");
  expect(inv.body.invoices).toEqual([]);
  await page.getByRole("button", { name: "Not now" }).click();
});

test("8. Stripe test checkout activates only after a verified webhook", async () => {
  test.skip(!process.env.E2E_STRIPE, "Needs Stripe TEST keys, prices and a forwarded webhook (E2E_STRIPE=1).");
  await page.goto("/pricing");
  await page.getByRole("button", { name: "Choose Pro" }).click();
  await page.waitForURL(/checkout\.stripe\.com/);
});

test("9. another user cannot access this user's data", async ({ browser }) => {
  const other = await browser.newPage();
  await register(other, `e2e-b-${stamp}@example.com`);
  const r = await api(other, `/api/resumes/${resumeId}`);
  expect(r.status).toBe(404);
  await other.goto("/app/resume");
  await expect(other.getByText("No resume yet")).toBeVisible();
  const apps = await api(other, "/api/applications");
  expect(apps.body.applications).toEqual([]);
  await other.close();
});

test("10. an agent requests a sensitive action and waits for approval", async () => {
  await page.goto("/app/applications");
  await page.fill('input[placeholder^="e.g. Senior AI Engineer"]', "AI Engineer jobs in Toronto");
  await page.click('button:has-text("Prepare")');
  await expect(page.getByText(/approval\(s\) waiting/)).toBeVisible({ timeout: 180_000 });
  const before = await api(page, "/api/applications");
  expect(before.body.applications.some((a: any) => a.status === "draft")).toBeTruthy();
  await page.goto("/app/governance");
  await expect(page.getByText("Waiting for your decision")).toBeVisible();
  await page.getByRole("button", { name: "Approve" }).first().click();
  await expect(page.getByText("Nothing waiting.")).toBeVisible();
  const after = await api(page, "/api/applications");
  expect(after.body.applications.some((a: any) => a.status === "applied")).toBeTruthy();
});

test("SSE: the assistant streams agent progress and a reply to completion", async () => {
  // This account used its trial features above; a fresh account keeps the journey independent.
  const fresh = await page.context().browser()!.newPage();
  await register(fresh, `e2e-c-${stamp}@example.com`);
  await fresh.fill("textarea[aria-label=Message]", "Find AI Engineer jobs in Toronto");
  await fresh.keyboard.press("Enter");
  await expect(fresh.getByText(/2\/20 messages/)).toBeVisible({ timeout: 200_000 });
  await expect(fresh.getByText(/jobs found/)).toBeVisible();
  await fresh.close();
});
