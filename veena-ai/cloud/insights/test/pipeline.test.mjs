// End-to-end test of VEENA Insights with SYNTHETIC data, using the real Worker code against SQLite
// (node:sqlite) through a small D1-compatible shim. Every synthetic row is marked is_test = 1.
//   node --test cloud/insights/test/pipeline.test.mjs           (writes test/out/summary.json, test/out/dashboard.html)
import { test } from "node:test";
import assert from "node:assert/strict";
import { DatabaseSync } from "node:sqlite";
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

const here = import.meta.dirname, root = path.resolve(here, "..");
const out = path.join(here, "out");
fs.mkdirSync(out, { recursive: true });
// Load worker.js with the dashboard HTML inlined (Wrangler does this with its Text rule).
const html = fs.readFileSync(path.join(root, "src/dashboard.html"), "utf8");
const src = fs.readFileSync(path.join(root, "src/worker.js"), "utf8").replace('import DASHBOARD_HTML from "./dashboard.html";', `const DASHBOARD_HTML = ${JSON.stringify(html)};`);
fs.writeFileSync(path.join(out, "worker.bundle.mjs"), src);
const W = await import(pathToFileURL(path.join(out, "worker.bundle.mjs")).href);

// ---- D1 shim ----
function d1() {
  const db = new DatabaseSync(":memory:");
  db.exec(fs.readFileSync(path.join(root, "schema.sql"), "utf8"));
  const norm = (sql) => sql.replace(/\?(\d+)/g, "?");                 // node:sqlite numbered params -> positional
  const expand = (sql, args) => { const order = [...sql.matchAll(/\?(\d+)/g)].map((m) => Number(m[1]) - 1); return order.length ? order.map((i) => args[i]) : args; };
  const prep = (sql) => {
    const st = { sql, args: [],
      bind(...a) { return { ...st, args: a }; },
      async all() { return { results: db.prepare(norm(sql)).all(...expand(sql, this.args)) }; },
      async first() { return db.prepare(norm(sql)).get(...expand(sql, this.args)) ?? null; },
      async run() { const r = db.prepare(norm(sql)).run(...expand(sql, this.args)); return { meta: { changes: Number(r.changes) } }; },
    };
    return st;
  };
  return { db, prepare: prep, async batch(list) { db.exec("BEGIN"); try { const r = []; for (const s of list) r.push(await s.run()); db.exec("COMMIT"); return r; } catch (e) { db.exec("ROLLBACK"); throw e; } } };
}
const TOKEN = "test-token-" + "x".repeat(40);
const mkEnv = () => ({ DB: d1(), DASHBOARD_TOKEN: TOKEN, ALLOWED_ORIGINS: "https://florina787.github.io", RETENTION_DAYS: "395" });
const NOW = new Date("2026-11-10T12:00:00Z");
const day = (n) => new Date(NOW.getTime() - n * 86400000).toISOString().slice(0, 10);
const uuid = (i) => `${(0x10000000 + i).toString(16)}-1111-4111-8111-${String(i).padStart(12, "0")}`;
const req = (p, body, headers = {}) => new Request("https://insights.example" + p, { method: "POST", body: JSON.stringify(body), headers: { "content-type": "application/json", ...headers } });

test("rejects anything outside the allow-listed schema (no content can be stored)", async () => {
  const env = mkEnv(), base = { install_id: uuid(1), os: "windows", app_version: "0.1.0", test: true };
  for (const [name, body] of [
    ["prompt text", { ...base, events: [{ event: "feature", feature: "chat", day: day(0), prompt: "my secret question" }] }],
    ["extra top-level field", { ...base, email: "a@b.c", events: [{ event: "active", day: day(0) }] }],
    ["unknown feature", { ...base, events: [{ event: "feature", feature: "keylogger", day: day(0) }] }],
    ["free-text error", { ...base, events: [{ event: "error", error_code: "Traceback: C:\\Users\\name\\file.pdf", day: day(0) }] }],
    ["not a UUID", { ...base, install_id: "user@example.com", events: [{ event: "active", day: day(0) }] }],
    ["day far in the past", { ...base, events: [{ event: "active", day: "2020-01-01" }] }],
  ]) {
    const r = await W.default.fetch(req("/v1/events", body), env);
    assert.equal(r.status, 400, name);
  }
  assert.equal(env.DB.db.prepare("SELECT COUNT(*) n FROM events").get().n, 0);
});

test("oversized bodies are refused", async () => {
  const env = mkEnv();
  const r = await W.default.fetch(new Request("https://x/v1/events", { method: "POST", body: "x".repeat(9000) }), env);
  assert.equal(r.status, 413);
});

test("rate limit per installation per hour", async () => {
  const env = mkEnv(), id = uuid(2);
  let last;
  for (let i = 0; i < 8; i++) {
    const events = Array.from({ length: 50 }, () => ({ event: "error", error_code: "other", day: day(0) }));
    last = await W.default.fetch(req("/v1/events", { install_id: id, os: "linux", app_version: "0.1.0", test: true, events }), env);
  }
  assert.equal(last.status, 429);
});

test("duplicate first_launch / active rows are de-duplicated", async () => {
  const env = mkEnv(), id = uuid(3), body = { install_id: id, os: "macos", app_version: "0.1.0", test: true, events: [{ event: "first_launch", day: day(0) }, { event: "active", day: day(0) }] };
  await W.default.fetch(req("/v1/events", body), env);
  await W.default.fetch(req("/v1/events", body), env);
  assert.equal(env.DB.db.prepare("SELECT COUNT(*) n FROM events WHERE install_id=?").get(id).n, 2);
});

test("withdrawal deletes every row of that installation and logs the deletion", async () => {
  const env = mkEnv(), id = uuid(4);
  await W.default.fetch(req("/v1/events", { install_id: id, os: "windows", app_version: "0.1.0", test: true, events: [{ event: "first_launch", day: day(1) }, { event: "feature", feature: "documents", day: day(0) }] }), env);
  const r = await W.default.fetch(req("/v1/delete", { install_id: id }), env);
  assert.deepEqual(await r.json(), { deleted: 2 });
  assert.equal(env.DB.db.prepare("SELECT COUNT(*) n FROM events WHERE install_id=?").get(id).n, 0);
  assert.equal(env.DB.db.prepare("SELECT source FROM deletions").get().source, "app_withdrawal");
});

test("website counter: allowed origin only, no identifier stored", async () => {
  const env = mkEnv();
  const bad = await W.default.fetch(req("/v1/web", { kind: "pageview", page: "/" }, { origin: "https://evil.example" }), env);
  assert.equal(bad.status, 403);
  const ok = await W.default.fetch(req("/v1/web", { kind: "pageview", page: "/", referrer: "www.LinkedIn.com", campaign: "launch", test: true }, { origin: "https://florina787.github.io" }), env);
  assert.equal(ok.status, 204);
  const row = env.DB.db.prepare("SELECT * FROM web_daily").get();
  assert.equal(row.referrer, "linkedin.com");
  assert.deepEqual(Object.keys(row).sort(), ["campaign", "count", "day", "is_test", "kind", "os", "page", "referrer"].sort());
});

test("dashboard API requires the token; a weak token disables it", async () => {
  const env = mkEnv();
  assert.equal((await W.default.fetch(new Request("https://x/api/summary"), env)).status, 401);
  assert.equal((await W.default.fetch(new Request("https://x/api/summary", { headers: { authorization: "Bearer wrong" } }), env)).status, 401);
  assert.equal((await W.default.fetch(new Request("https://x/api/summary", { headers: { authorization: "Bearer " + TOKEN } }), env)).status, 200);
  const weak = { ...env, DASHBOARD_TOKEN: "short" };
  assert.equal((await W.default.fetch(new Request("https://x/api/summary", { headers: { authorization: "Bearer short" } }), weak)).status, 401);
});

test("retention purge removes old rows and records it", async () => {
  const env = mkEnv();
  env.DB.db.prepare("INSERT INTO events (install_id,event,os,app_version,day,is_test,received_at) VALUES (?,?,?,?,?,1,?)").run(uuid(9), "active", "linux", "0.1.0", "2025-01-01", "x");
  const res = await W.daily(env, NOW, async () => new Response("[]", { status: 200 }));
  assert.equal(res.purged, 1);
});

test("full synthetic pipeline -> summary and dashboard", async () => {
  const env = mkEnv();
  let seed = 7; const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
  const oses = ["windows", "windows", "windows", "macos", "macos", "linux"];
  // Website: 90 days of page views and download clicks, LABELLED test.
  for (let d = 89; d >= 0; d--) {
    const views = 20 + Math.floor(rnd() * 30) + (d < 20 ? 25 : 0);
    for (let i = 0; i < views; i++) {
      const ref = rnd() < 0.35 ? "linkedin.com" : rnd() < 0.3 ? "github.com" : rnd() < 0.2 ? "medium.com" : "";
      await W.countWeb(env, W.validateWeb({ kind: "pageview", page: rnd() < 0.7 ? "/" : "/features.html", referrer: ref, campaign: ref === "linkedin.com" && rnd() < 0.5 ? "linkedin-launch" : "", test: true }), new Date(day(d) + "T10:00:00Z"));
    }
    for (let i = 0; i < Math.floor(views * 0.18); i++) await W.countWeb(env, W.validateWeb({ kind: "download_click", os: oses[Math.floor(rnd() * 6)], test: true }), new Date(day(d) + "T10:00:00Z"));
  }
  // GitHub snapshot (test-labelled).
  for (const [os, file, n] of [["windows", "VEENA.AI-Windows-Setup.exe", 412], ["macos", "VEENA.AI-macOS-AppleSilicon.dmg", 233], ["linux", "VEENA.AI-Linux-x86_64.AppImage", 97]])
    env.DB.db.prepare("INSERT INTO release_downloads (day,release,os,file,downloads,is_test) VALUES (?,?,?,?,?,1)").run(day(0), "veena-ai-v0.1.0", os, file, n);
  // Desktop: 160 synthetic opted-in installations over ~80 days.
  const feats = [["chat", .92], ["documents", .55], ["screen", .31], ["meeting", .38], ["interview", .27], ["agents", .12]];
  for (let i = 0; i < 160; i++) {
    const id = uuid(1000 + i), os = oses[Math.floor(rnd() * 6)], start = Math.floor(rnd() * 80), stickiness = rnd();
    const days = [];
    days.push({ event: "first_launch", day: day(start) }, { event: "active", day: day(start) });
    if (rnd() < 0.82) days.push({ event: "ai_first_success", day: day(start) });
    for (let d = start - 1; d >= 0; d--) if (rnd() < 0.5 * stickiness * Math.pow(0.97, start - d)) {
      days.push({ event: "active", day: day(d) });
      for (const [f, p] of feats) if (rnd() < p * 0.6) days.push({ event: "feature", feature: f, day: day(d) });
      if (rnd() < 0.02) days.push({ event: "error", error_code: ["model_error", "asr_error", "screen_capture", "runtime_download"][Math.floor(rnd() * 4)], day: day(d) });
    }
    for (const [f, p] of feats) if (rnd() < p) days.push({ event: "feature", feature: f, day: day(start) });
    // ingest() validates days relative to "now"; synthetic history is inserted at its own date.
    for (const e of days) {
      const batch = W.validateBatch({ install_id: id, os, app_version: rnd() < 0.8 ? "0.1.0" : "0.1.1", test: true, events: [e] }, new Date(e.day + "T12:00:00Z"));
      await W.ingest(env, batch, new Date(e.day + "T12:00:00Z"));
    }
  }
  const fbText = [["chat", 5, "Faster answers on CPU"], ["documents", 4, "Import a whole folder"], ["screen", 3, "Explain a selected region only"], ["meeting", 4, "Speaker names in transcripts"]];
  for (let i = 0; i < 24; i++) { const [f, r, n] = fbText[i % 4]; await W.saveFeedback(env, W.validateFeedback({ kind: i % 7 ? "feedback" : "bug", rating: r, feature: f, worked: "Works offline", next: n, didnt: i % 7 ? "" : "Setup stalled at the model download", email: i % 3 ? null : `tester${i}@example.com`, contact_ok: i % 3 === 0, elapsed_ms: 8000, test: true }), "c" + i, new Date(day(i * 3) + "T12:00:00Z")); }
  for (let d = 60; d >= 0; d -= 3) env.DB.db.prepare("INSERT OR IGNORE INTO release_downloads (day,release,os,file,downloads,is_test) VALUES (?,?,?,?,?,1)").run(day(d), "veena-ai-v0.1.0", "windows", "VEENA.AI-Windows-Setup.exe", 412 - d * 6);
  const real = await W.summary(env, { days: 90, test: false }, NOW);
  assert.equal(real.web.page_views, 0, "real view must not include test data");
  assert.equal(real.installs.first_launches, 0);
  const s = await W.summary(env, { days: 90, test: true }, NOW);
  assert.equal(s.test_data, true);
  assert.equal(s.installs.first_launches, 160);
  assert.ok(s.installs.first_ai_success <= s.installs.first_launches);
  assert.ok(s.installs.active_7d <= s.installs.active_30d);
  assert.equal(s.downloads.total, 412 + 233 + 97);
  assert.equal(s.features.length, 6);
  assert.ok(s.retention.length > 0 && s.weekly_active.length === 12);
  fs.writeFileSync(path.join(out, "summary.json"), JSON.stringify(s, null, 2));
  // A standalone dashboard preview with the synthetic summary baked in (for screenshots only).
  fs.writeFileSync(path.join(out, "dashboard.html"), html.replace("if (token) load(); else show(false);",
    `$("test").value = "1"; render(${JSON.stringify(s)}); show(true);`));
});

// ---------------- feedback (public beta) ----------------
const fbReq = (body, headers = { origin: "https://florina787.github.io", "cf-connecting-ip": "203.0.113.7" }) =>
  new Request("https://insights.example/v1/feedback", { method: "POST", body: JSON.stringify(body), headers: { "content-type": "application/json", ...headers } });
const good = { kind: "feedback", rating: 4, feature: "documents", worked: "Citations", didnt: "", next: "Folder import", elapsed_ms: 9000, test: true };

test("feedback: valid submission stored; spam and bad input rejected", async () => {
  const env = mkEnv();
  assert.equal((await W.default.fetch(fbReq(good), env)).status, 200);
  for (const [name, b] of [["honeypot", { ...good, website: "http://spam" }], ["too fast", { ...good, elapsed_ms: 400 }], ["rating", { ...good, rating: 9 }],
    ["unknown field", { ...good, prompt: "my private question" }], ["empty", { ...good, worked: "", next: "" }], ["email", { ...good, email: "not-an-email" }]])
    assert.equal((await W.default.fetch(fbReq(b), env)).status, 400, name);
  assert.equal((await W.default.fetch(fbReq(good, { origin: "https://evil.example" }), env)).status, 403);
  const row = env.DB.db.prepare("SELECT * FROM feedback").get();
  assert.equal(row.feature, "documents"); assert.equal(row.email, null); assert.equal(row.contact_ok, 0);
  assert.equal(env.DB.db.prepare("SELECT COUNT(*) n FROM feedback").get().n, 1);
});

test("feedback: 5 per client per day; contact permission only with an email", async () => {
  const env = mkEnv();
  let last;
  for (let i = 0; i < 6; i++) last = await W.default.fetch(fbReq({ ...good, email: "Person@Example.com", contact_ok: true }), env);
  assert.equal(last.status, 429);
  const row = env.DB.db.prepare("SELECT email, contact_ok FROM feedback").get();
  assert.equal(row.email, "person@example.com"); assert.equal(row.contact_ok, 1);
  assert.equal((await W.default.fetch(fbReq({ ...good, contact_ok: true }, { origin: "https://florina787.github.io", "cf-connecting-ip": "198.51.100.1" }), env)).status, 200);
  assert.equal(env.DB.db.prepare("SELECT contact_ok FROM feedback ORDER BY id DESC").get().contact_ok, 0, "no email -> not contactable");
});

test("feedback: dashboard statistics, test data separated, retention removes addresses after a year", async () => {
  const env = mkEnv();
  for (const [r, f, ip] of [[5, "chat", "1"], [3, "chat", "2"], [4, "screen", "3"]])
    await W.saveFeedback(env, W.validateFeedback({ ...good, rating: r, feature: f, email: "a@b.co", contact_ok: true }), ip, NOW);
  await W.saveFeedback(env, W.validateFeedback({ kind: "bug", feature: "setup", didnt: "Crash on start", elapsed_ms: 5000, test: true }), "4", NOW);
  const s = await W.summary(env, { days: 30, test: true }, NOW);
  assert.equal(s.feedback.total, 4); assert.equal(s.feedback.bugs, 1); assert.equal(s.feedback.avg_rating, 4);
  assert.equal(s.feedback.contactable, 3); assert.equal(s.feedback.anonymous, 1);
  assert.equal((await W.summary(env, { days: 30, test: false }, NOW)).feedback.total, 0, "real view shows no test feedback");
  env.DB.db.prepare("UPDATE feedback SET day = '2025-06-01'").run();
  await W.daily(env, NOW, async () => new Response("[]"));
  assert.equal(env.DB.db.prepare("SELECT COUNT(*) n FROM feedback WHERE email IS NOT NULL").get().n, 0);
});

test("health: reports schema and secret presence without revealing values", async () => {
  const env = mkEnv();
  const r = await W.default.fetch(new Request("https://x/health"), env);
  const h = await r.json();
  assert.equal(r.status, 200); assert.equal(h.schema, "ok"); assert.equal(h.ok, true);
  assert.ok(!JSON.stringify(h).includes(env.DASHBOARD_TOKEN || "never-present"), "token value never returned");
  env.DB.db.exec("DROP TABLE feedback");
  const bad = await W.default.fetch(new Request("https://x/health"), env);
  assert.equal(bad.status, 503); assert.match((await bad.json()).schema, /missing: feedback/);
});
