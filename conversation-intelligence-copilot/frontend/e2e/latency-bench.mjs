// Browser time-to-answer for deterministic questions: from pressing Enter to the rendered answer in the DOM.
// Covers the whole path a user waits for: SSE request, routing, DuckDB, QA, governance, response assembly and React rendering.
// Each question starts from a fresh session (no follow-up context) on an already-loaded page (a warm browser tab).
// Usage: APP_URL=http://127.0.0.1:4173 node e2e/latency-bench.mjs <label> [runsPerCategory]
// BENCH_CAP_S=<seconds> stops a category early once its runs have taken that long (reported as n).
// Writes ../data/manifests/browser_latency_<label>.json
import { chromium } from "@playwright/test";
import fs from "node:fs";

const label = process.argv[2] ?? "after";
const runs = Number(process.argv[3] ?? 20);
const base = process.env.APP_URL ?? "http://127.0.0.1:4173";
const capS = Number(process.env.BENCH_CAP_S ?? 0);
const CATEGORIES = {
  greeting: ["Hi", "Hello", "hey there", "How are you?", "Good morning", "thanks!", "What can you do?"],
  positive_statements: ["What are the top 5 positive statements from users?", "Show the top 5 positive statements customers made",
    "What are the most common positive comments from customers?", "List the top 3 positive customer statements"],
  negative_statements: ["What are the top 5 negative statements from users?", "Show the top 3 negative statements customers made",
    "What are the most common negative comments from customers?", "List the top 10 negative customer statements"],
  complaints: ["What are the top complaints?", "What were the top 5 topics most associated with negative sentiment?",
    "Which topics have the most negative conversations?", "What do customers complain about most?"],
  sentiment_percentages: ["What is the overall sentiment mix?", "What percentage of conversations are negative?",
    "Show the sentiment distribution across conversations", "How many conversations are positive, neutral and negative?"],
  sentiment_trend: ["Show the sentiment trend over time.", "Compare sentiment this month vs last month",
    "How has negative sentiment changed month over month?", "What is the monthly sentiment trend?"],
  rankings: ["Which recurring customer concerns should leadership review first?", "Which support agents may benefit from coaching on empathy?",
    "Rank the customer concerns leadership should prioritise", "Which agents need coaching on empathy?"],
};
const ANSWER = "[data-testid=routing-strip], [data-testid=small-talk]";

const pct = (xs, q) => {
  const s = [...xs].sort((a, b) => a - b);
  const k = (s.length - 1) * q, lo = Math.floor(k), hi = Math.min(lo + 1, s.length - 1);
  return Math.round((s[lo] + (s[hi] - s[lo]) * (k - lo)) * 10) / 10;
};

const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || "/opt/pw-browsers/chromium" });
const page = await browser.newPage({ viewport: { width: 1400, height: 900 } });
const out = { label, base, runs_per_category: runs, categories: {}, generated_at: new Date().toISOString() };
for (const [name, questions] of Object.entries(CATEGORIES)) {
  const rows = [];
  const started = Date.now();
  for (let i = 0; i < runs; i++) {
    if (capS && (Date.now() - started) / 1000 > capS) { console.log(`${name}: stopped after ${rows.length} runs (cap ${capS}s)`); break; }
    const q = questions[i % questions.length];
    await page.goto(base + "/");
    await page.evaluate(() => localStorage.removeItem("cic.session"));
    await page.goto(base + "/");
    await page.getByRole("textbox").fill(q);
    // Time inside the page: Enter keydown -> the answer element is in the DOM and has been painted.
    await page.evaluate((sel) => {
      window.__bench = { t0: 0, t1: 0 };
      document.addEventListener("keydown", (e) => { if (e.key === "Enter") window.__bench.t0 = performance.now(); }, { capture: true, once: true });
      new MutationObserver((_, obs) => {
        if (document.querySelector(sel)) { obs.disconnect(); requestAnimationFrame(() => { window.__bench.t1 = performance.now(); }); }
      }).observe(document.body, { childList: true, subtree: true });
    }, ANSWER);
    await page.keyboard.press("Enter");
    await page.waitForFunction(() => window.__bench.t1 > 0, null, { timeout: 120000, polling: 50 });
    const ms = await page.evaluate(() => Math.round((window.__bench.t1 - window.__bench.t0) * 10) / 10);
    const text = (await page.locator("h2, [data-testid=small-talk] p").first().innerText()).slice(0, 160);
    rows.push({ question: q, ms, rendered: text });
    console.log(`${name.padEnd(22)} ${String(i + 1).padStart(2)} ${String(ms).padStart(8)} ms  ${q.slice(0, 60)}`);
  }
  const ms = rows.map((r) => r.ms);
  out.categories[name] = { n: rows.length, p50_ms: pct(ms, 0.5), p95_ms: pct(ms, 0.95), max_ms: Math.max(...ms), runs: rows };
}
const all = Object.values(out.categories).flatMap((c) => c.runs.map((r) => r.ms));
out.deterministic_overall = { n: all.length, p50_ms: pct(all, 0.5), p95_ms: pct(all, 0.95), max_ms: Math.max(...all) };
await browser.close();
const path = `../data/manifests/browser_latency_${label}.json`;
fs.writeFileSync(path, JSON.stringify(out, null, 2));
console.log("\ncategory               n   p50 ms   p95 ms");
for (const [n, c] of Object.entries(out.categories)) console.log(`${n.padEnd(22)} ${String(c.n).padStart(2)} ${String(c.p50_ms).padStart(8)} ${String(c.p95_ms).padStart(8)}`);
console.log(`deterministic overall: n=${all.length} p50 ${out.deterministic_overall.p50_ms} ms, p95 ${out.deterministic_overall.p95_ms} ms\nwrote ${path}`);
