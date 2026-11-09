// Captures the README screenshots from a running demo stack (backend :8000 with Qwen, frontend :5173, seeded demo user).
// Usage: node scripts/readme_screenshots.cjs docs/assets/screens
const { chromium } = require('playwright');
const OUT = process.argv[2];
const U = 'http://localhost:5173';
(async () => {
  const b = await chromium.launch();
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 } });
  const p = await ctx.newPage();
  const shot = (n, o = {}) => p.screenshot({ path: `${OUT}/${n}.png`, ...o });
  await p.goto(U + '/'); await p.waitForTimeout(2500); await shot('landing');
  await p.locator('section[aria-label="Product preview"]').screenshot({ path: `${OUT}/hero-cards.png` });
  await p.goto(U + '/login');
  await p.fill('input[name=email]', 'demo@careerflo.example'); await p.fill('input[name=password]', 'DemoPassword123');
  await p.click('form button:has-text("Log in")'); await p.waitForURL('**/app'); await p.waitForTimeout(1500);
  await shot('assistant-empty');
  // Real multi-agent run with Qwen
  await p.fill('textarea[aria-label=Message]', 'Find Senior AI Engineer jobs in Toronto paying over CAD 150,000, analyze my resume, rank the best opportunities, and prepare me for interviews.');
  await p.keyboard.press('Enter');
  await p.waitForTimeout(6000); await shot('assistant-agents-working');
  await p.waitForSelector('text=/messages ·/', { timeout: 300000 }); await p.waitForTimeout(1000);
  await p.evaluate(() => window.scrollTo(0, 0)); await shot('assistant-results');
  await p.screenshot({ path: `${OUT}/assistant-full.png`, fullPage: true });
  // Jobs
  await p.goto(U + '/app/jobs'); await p.waitForTimeout(800);
  await p.fill('input[placeholder="150000"]', '150000');
  await p.click('main button:has-text("Search")'); await p.waitForTimeout(3000); await shot('jobs');
  const marks = p.locator('button[aria-label="Save job"]');
  for (let i = 0; i < 3; i++) { await marks.nth(0).click(); await p.waitForTimeout(500); }
  // Resume tailoring with Qwen summary
  await p.goto(U + '/app/resume'); await p.waitForTimeout(1500);
  await p.locator('select[aria-label="Target job"]').selectOption({ index: 1 });
  await p.click('button:has-text("Optimize resume")');
  await p.waitForSelector('text=/Fact check passed|unsupported statements/', { timeout: 300000 }); await p.waitForTimeout(800);
  await shot('resume-progression');
  await p.locator('text=Tailor for a job').scrollIntoViewIfNeeded(); await p.evaluate(() => window.scrollBy(0, 300)); await shot('resume-tailored');
  // Interview with Qwen feedback
  await p.goto(U + '/app/interview'); await p.waitForTimeout(1000);
  await p.click('button:has-text("Start mock interview")'); await p.waitForSelector('text=Submit answer');
  await p.fill('textarea', 'I keep safety controls in code, not prompts: a static allowlist of tools per agent, least privilege, human approval for consequential actions, timeouts and a tool-call budget, and an audit log of every call. External text is treated as untrusted data.');
  await p.click('button:has-text("Submit answer")');
  await p.waitForSelector('text=/coverage/', { timeout: 300000 }); await p.waitForTimeout(800); await shot('interview');
  // Learning
  await p.goto(U + '/app/learning'); await p.waitForTimeout(1200);
  await p.click('button:has-text("Build my personal plan")'); await p.waitForTimeout(3000); await shot('learning');
  await p.locator('main .grid').first().screenshot({ path: `${OUT}/growth-paths.png` });
  // Others
  for (const [path, name] of [['applications', 'applications'], ['mission', 'mission-control'], ['mcp', 'mcp-registry'], ['governance', 'governance'], ['billing', 'billing']]) {
    await p.goto(U + '/app/' + path); await p.waitForTimeout(2200); await shot(name);
  }
  await p.goto(U + '/app/analytics'); await p.waitForTimeout(1000);
  await p.click('button:has-text("Generate full report")'); await p.waitForTimeout(3500);
  await p.evaluate(() => window.scrollBy(0, 330)); await p.waitForTimeout(800); await shot('analytics');
  await p.goto(U + '/pricing'); await p.waitForTimeout(1500); await shot('pricing');
  // Dark mode
  await p.evaluate(() => localStorage.setItem('cf.theme', 'dark'));
  await p.goto(U + '/app/learning'); await p.waitForTimeout(1500); await shot('dark-learning');
  await p.goto(U + '/app/jobs'); await p.waitForTimeout(800); await p.click('main button:has-text("Search")'); await p.waitForTimeout(2500); await shot('dark-jobs');
  // Mobile
  const m = await b.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 });
  await m.goto(U + '/'); await m.waitForTimeout(1500); await m.screenshot({ path: `${OUT}/mobile-landing.png` });
  await b.close();
  console.log('done');
})().catch(e => { console.error(e); process.exit(1); });
