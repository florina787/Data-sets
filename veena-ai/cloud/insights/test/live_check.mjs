// Verifies the DEPLOYED Insights Worker end to end with synthetic records only.
//   DASHBOARD_TOKEN=... node test/live_check.mjs https://veena-insights.<subdomain>.workers.dev
// Every record it writes carries test:true (is_test=1): the dashboard's real view never shows them,
// and the deploy workflow deletes them right after this script. The token is read from the
// environment and never printed.
import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";

const base = (process.argv[2] || "").replace(/\/$/, "");
const token = process.env.DASHBOARD_TOKEN || "";
if (!base.startsWith("https://")) { console.error("usage: node live_check.mjs https://<worker>"); process.exit(2); }
const SITE = "https://florina787.github.io";
const results = [];
const check = async (name, fn) => {
  try { await fn(); results.push(["PASS", name]); console.log("PASS", name); }
  catch (e) { results.push(["FAIL", name]); console.log("FAIL", name, "-", e.message); }
};
const post = (path, body, headers = {}) => fetch(base + path, { method: "POST", headers: { "content-type": "application/json", origin: SITE, ...headers }, body: typeof body === "string" ? body : JSON.stringify(body) });
const auth = (t) => ({ authorization: "Bearer " + t });
const summary = async (test) => (await (await fetch(`${base}/api/summary?days=7&test=${test ? 1 : 0}`, { headers: auth(token) })).json());
const day = new Date().toISOString().slice(0, 10);
const fb = { kind: "feedback", rating: 4, feature: "documents", worked: "Synthetic deployment check", elapsed_ms: 4000, test: true };

let realBefore;
await check("health: Worker up, D1 schema complete, both secrets configured", async () => {
  const r = await fetch(base + "/health"); const h = await r.json();
  assert.equal(r.status, 200, JSON.stringify(h));
  assert.equal(h.schema, "ok"); assert.equal(h.dashboard_token, "set"); assert.equal(h.rate_salt, "set");
});
await check("dashboard: page served privately (noindex, no-store)", async () => {
  const r = await fetch(base + "/dashboard");
  assert.equal(r.status, 200); assert.match(r.headers.get("x-robots-tag") || "", /noindex/);
  assert.match(r.headers.get("cache-control") || "", /no-store/);
});
await check("dashboard data: refused without a token and with a wrong token", async () => {
  assert.equal((await fetch(base + "/api/summary")).status, 401);
  assert.equal((await fetch(base + "/api/summary", { headers: auth("x".repeat(40)) })).status, 401);
});
await check("dashboard data: available with the owner's token", async () => {
  assert.ok(token.length >= 32, "DASHBOARD_TOKEN env missing");
  const r = await fetch(base + "/api/summary?days=7", { headers: auth(token) });
  assert.equal(r.status, 200); realBefore = await r.json(); assert.ok(realBefore.feedback);
});
await check("CORS: website origin allowed, other origins refused", async () => {
  const ok = await fetch(base + "/v1/feedback", { method: "OPTIONS", headers: { origin: SITE, "access-control-request-method": "POST" } });
  assert.equal(ok.status, 204); assert.equal(ok.headers.get("access-control-allow-origin"), SITE);
  const bad = await fetch(base + "/v1/feedback", { method: "OPTIONS", headers: { origin: "https://evil.example" } });
  assert.equal(bad.status, 403);
  assert.equal((await post("/v1/feedback", fb, { origin: "https://evil.example" })).status, 403);
});
await check("website feedback with optional email and contact consent", async () => {
  const r = await post("/v1/feedback", { ...fb, email: "deploy-check@example.com", contact_ok: true });
  assert.equal(r.status, 200, await r.text()); assert.equal(r.headers.get("access-control-allow-origin"), SITE);
});
await check("bug report without email (anonymous)", async () => {
  const r = await post("/v1/feedback", { kind: "bug", feature: "setup", didnt: "Synthetic bug report", elapsed_ms: 4000, test: true });
  assert.equal(r.status, 200, await r.text());
});
await check("application feedback (with OS and app version)", async () => {
  const r = await post("/v1/feedback", { ...fb, feature: "chat", os: "windows", app_version: "0.1.0" });
  assert.equal(r.status, 200, await r.text());
});
await check("feedback reaches the dashboard (test view) and not the real view", async () => {
  const t = await summary(true);
  assert.ok(t.feedback.total >= 3, "test feedback total " + t.feedback.total);
  assert.ok(t.feedback.contactable >= 1 && t.feedback.bugs >= 1);
  assert.equal((await summary(false)).feedback.total, realBefore.feedback.total, "real view must not count synthetic feedback");
});
await check("spam and error handling: honeypot, too fast, unknown field, bad JSON, oversize, unknown route", async () => {
  assert.equal((await post("/v1/feedback", { ...fb, website: "http://spam" })).status, 400);
  assert.equal((await post("/v1/feedback", { ...fb, elapsed_ms: 200 })).status, 400);
  assert.equal((await post("/v1/feedback", { ...fb, prompt: "private text" })).status, 400);
  assert.equal((await post("/v1/feedback", "{not json")).status, 400);
  assert.equal((await post("/v1/feedback", { ...fb, worked: "x".repeat(9000) })).status, 413);
  assert.equal((await fetch(base + "/nope")).status, 404);
});

const id = randomUUID();
await check("opt-in statistics: allow-listed events accepted", async () => {
  const r = await fetch(base + "/v1/events", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ install_id: id, os: "linux", app_version: "0.1.0", test: true,
    events: [{ event: "first_launch", day }, { event: "active", day }, { event: "ai_first_success", day }, { event: "feature", feature: "chat", day }] }) });
  const body = await r.text();
  assert.equal(r.status, 200, body); assert.equal(JSON.parse(body).accepted, 4);
});
await check("privacy: content fields are refused (no prompt, no message text)", async () => {
  const r = await fetch(base + "/v1/events", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ install_id: randomUUID(), os: "linux", app_version: "0.1.0", test: true,
    events: [{ event: "active", day, prompt: "secret question" }] }) });
  assert.equal(r.status, 400);
});
await check("statistics reach the private dashboard (test view)", async () => {
  const t = await summary(true);
  assert.ok(t.installs.first_launches >= 1 && t.installs.first_ai_success >= 1 && t.installs.active_1d >= 1, JSON.stringify(t.installs));
});
await check("withdrawal deletes that installation's rows", async () => {
  const before = (await summary(true)).installs.first_launches;
  const r = await fetch(base + "/v1/delete", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ install_id: id }) });
  assert.equal(r.status, 200); assert.equal((await r.json()).deleted, 4);
  assert.equal((await summary(true)).installs.first_launches, before - 1);
});
await check("rate limit: at most 5 feedback submissions per client per day", async () => {
  let status = 0;
  for (let i = 0; i < 6 && status !== 429; i++) status = (await post("/v1/feedback", { ...fb, worked: "Synthetic rate-limit check " + i })).status;
  assert.equal(status, 429);
});

const failed = results.filter((r) => r[0] === "FAIL").length;
console.log(`\n${results.length - failed}/${results.length} live checks passed`);
process.exit(failed ? 1 : 0);
