// REAL Stripe sandbox test of the billing Worker (test mode only; refuses any key not starting sk_test_).
//   STRIPE_SECRET_KEY=sk_test_... node cloud/billing/test/sandbox.mjs
// Makes real test-mode Checkout payments in a browser with Stripe test cards, fetches the REAL resulting
// events from Stripe's API and delivers them to the Worker. Without a public webhook URL (nothing is
// deployed) Stripe cannot sign deliveries to this machine, so deliveries are signed locally with
// Stripe's documented scheme; the event payloads are Stripe's own.
import { createRequire } from "node:module";
import crypto from "node:crypto";
import { DatabaseSync } from "node:sqlite";
import fs from "node:fs";
import path from "node:path";
import * as B from "../src/worker.js";

const KEY = process.env.STRIPE_SECRET_KEY || "";
if (!KEY.startsWith("sk_test_")) { console.error("refusing: a Stripe TEST key (sk_test_...) is required"); process.exit(2); }
const require = createRequire(path.join(process.cwd(), "noop.js"));
const { chromium } = require("playwright");
const root = path.resolve(import.meta.dirname, "..");
const results = [];
const record = (name, pass, detail = "") => { results.push({ name, pass, detail }); console.log(`${pass ? "PASS" : "FAIL"}  ${name}${detail ? "  — " + detail : ""}`); };

// ---- Worker on SQLite (D1 shim), REAL fetch to api.stripe.com ----
const db = new DatabaseSync(":memory:");
db.exec(fs.readFileSync(path.join(root, "schema.sql"), "utf8"));
const norm = (s) => s.replace(/\?(\d+)/g, "?"), expand = (s, a) => { const o = [...s.matchAll(/\?(\d+)/g)].map((m) => Number(m[1]) - 1); return o.length ? o.map((i) => a[i]) : a; };
const prep = (sql) => { const st = { args: [], bind(...a) { return { ...st, args: a }; },
  async all() { return { results: db.prepare(norm(sql)).all(...expand(sql, this.args)) }; },
  async first() { return db.prepare(norm(sql)).get(...expand(sql, this.args)) ?? null; },
  async run() { const r = db.prepare(norm(sql)).run(...expand(sql, this.args)); return { meta: { changes: Number(r.changes) } }; } }; return st; };
const WHSEC = "whsec_local_" + crypto.randomBytes(12).toString("hex"), mail = [];
const env = { DB: { prepare: prep, async batch(l) { db.exec("BEGIN"); try { for (const s of l) await s.run(); db.exec("COMMIT"); } catch (e) { db.exec("ROLLBACK"); throw e; } } },
  STRIPE_SECRET_KEY: KEY, STRIPE_WEBHOOK_SECRET: WHSEC, CODE_PEPPER: crypto.randomBytes(24).toString("hex"),
  SITE_URL: "https://florina787.github.io/Data-sets", fetch: fetch.bind(globalThis), sendEmail: async (to, s, t) => mail.push(t.match(/\d{6}/)[0]) };
const call = async (method, p, body, token) => {
  const r = await B.default.fetch(new Request("http://w" + p, { method, body: body ? JSON.stringify(body) : undefined, headers: { "content-type": "application/json", ...(token ? { authorization: "Bearer " + token } : {}) } }), env);
  return { status: r.status, body: await r.json() };
};
const deliver = async (ev) => { // Stripe's real event, signed locally (see header comment)
  const payload = JSON.stringify(ev), t = Math.floor(Date.now() / 1000);
  const sig = crypto.createHmac("sha256", WHSEC).update(`${t}.${payload}`).digest("hex");
  const r = await B.default.fetch(new Request("http://w/v1/stripe/webhook", { method: "POST", body: payload, headers: { "stripe-signature": `t=${t},v1=${sig}` } }), env);
  return (await r.json()).result;
};
const stripe = async (method, p, params) => {
  const r = await fetch("https://api.stripe.com/v1/" + p, { method, headers: { authorization: "Bearer " + KEY, "content-type": "application/x-www-form-urlencoded" }, body: params ? new URLSearchParams(params).toString() : undefined });
  const j = await r.json(); if (!r.ok) throw new Error(`${p}: ${j.error?.message}`); return j;
};
const since = Math.floor(Date.now() / 1000) - 5;
async function events(type, match, tries = 20) {
  for (let i = 0; i < tries; i++) {
    const list = await stripe("GET", `events?type=${type}&created[gte]=${since}&limit=100`);
    const hit = list.data.filter(match);
    if (hit.length) return hit;
    await new Promise((r) => setTimeout(r, 3000));
  }
  return [];
}
const me = async (tok) => (await call("GET", "/v1/me", null, tok)).body;

// ---- Stripe-hosted Checkout in a browser with a test card ----
const browser = await chromium.launch();
async function pay(url, card, expectSuccess = true) {
  const page = await browser.newPage();
  await page.goto(url, { waitUntil: "domcontentloaded" });
  await page.locator("#cardNumber").waitFor({ timeout: 60000 });
  await page.fill("#cardNumber", card); await page.fill("#cardExpiry", "12 / 34"); await page.fill("#cardCvc", "123");
  await page.fill("#billingName", "VEENA Sandbox Test");
  if (await page.locator("#billingPostalCode").isVisible().catch(() => false)) await page.fill("#billingPostalCode", "94103");
  const linkOptIn = page.locator("#enableStripePass");
  if (await linkOptIn.isChecked().catch(() => false)) await linkOptIn.uncheck().catch(() => {});
  await page.locator(".SubmitButton, button[type=submit]").first().click();
  let ok = false;
  try { await page.waitForURL(/checkout=success/, { timeout: 90000 }); ok = true; } catch { /* declined or still on page */ }
  if (!ok && !expectSuccess) await page.waitForTimeout(5000);
  const text = ok ? "" : (await page.locator("body").innerText()).slice(0, 4000);
  await page.close();
  return { ok, text };
}

try {
  // Sign in (email code captured locally; no email provider involved).
  const inst = crypto.randomUUID(), email = `sandbox+${Date.now()}@example.com`;
  await call("POST", "/v1/auth/start", { email, install_id: inst });
  const tok = (await call("POST", "/v1/auth/verify", { email, code: mail.at(-1), install_id: inst })).body.token;
  const acct = db.prepare("SELECT id FROM accounts").get().id;
  record("sign-in (local code)", !!tok);

  // 1. Checkout session creation, validated by Stripe itself.
  const c1 = await call("POST", "/v1/checkout", { package: "credits_1" }, tok);
  const cs1 = c1.body.id && (await stripe("GET", `checkout/sessions/${c1.body.id}`));
  record("checkout session created by Stripe (credits_1)", c1.status === 200 && cs1.amount_total === 1900 && cs1.currency === "usd" && cs1.livemode === false,
    c1.status === 200 ? `amount ${cs1.amount_total} ${cs1.currency}, livemode ${cs1.livemode}` : JSON.stringify(c1.body));

  // 2. Success redirect alone grants nothing.
  record("no credit before Stripe confirms", (await me(tok)).credit_minutes === 0);

  // 3. Successful test purchase -> real event -> credit.
  const p1 = await pay(c1.body.url, "4242424242424242");
  record("test card 4242 payment completed on Stripe Checkout", p1.ok, p1.ok ? "" : p1.text.slice(0, 200));
  const done1 = await events("checkout.session.completed", (e) => e.data.object.id === c1.body.id);
  record("real checkout.session.completed event received from Stripe", done1.length === 1);
  if (done1.length) {
    record("event processed -> 60 credit minutes", (await deliver(done1[0])) === "ok" && (await me(tok)).credit_minutes === 60);
    record("replayed event processed once", (await deliver(done1[0])) === "duplicate" && (await me(tok)).credit_minutes === 60);
  }

  // 4. Declined card -> no event, no credit.
  const c2 = await call("POST", "/v1/checkout", { package: "credits_3" }, tok);
  const p2 = await pay(c2.body.url, "4000000000000002", false);
  record("declined card 4000…0002 does not complete checkout", !p2.ok, /declin/i.test(p2.text) ? "Stripe showed a decline message" : "no success redirect");
  const done2 = await events("checkout.session.completed", (e) => e.data.object.id === c2.body.id, 3);
  record("no completion event for the declined session; balance unchanged", done2.length === 0 && (await me(tok)).credit_minutes === 60);

  // 5. Expired session.
  await stripe("POST", `checkout/sessions/${c2.body.id}/expire`);
  const exp = await events("checkout.session.expired", (e) => e.data.object.id === c2.body.id);
  record("real checkout.session.expired -> nothing granted", exp.length === 1 && (await deliver(exp[0])) === "expired" && (await me(tok)).credit_minutes === 60);

  // 6. Refund the credit purchase -> real charge.refunded -> minutes removed.
  if (done1.length) {
    await stripe("POST", "refunds", { payment_intent: done1[0].data.object.payment_intent });
    const ref = await events("charge.refunded", (e) => e.data.object.payment_intent === done1[0].data.object.payment_intent);
    record("real charge.refunded -> credit minutes removed", ref.length === 1 && (await deliver(ref[0])) === "ok" && (await me(tok)).credit_minutes === 0,
      ref.length ? `balance ${(await me(tok)).credit_minutes}` : "no event");
  }

  // 7. Monthly subscription -> real events -> Unlimited; cancel -> ended.
  const c3 = await call("POST", "/v1/checkout", { package: "unlimited_monthly" }, tok);
  const cs3 = await stripe("GET", `checkout/sessions/${c3.body.id}`);
  record("subscription checkout session (monthly, USD 74.95)", cs3.mode === "subscription" && cs3.amount_total === 7495);
  const p3 = await pay(c3.body.url, "4242424242424242");
  record("subscription paid on Stripe Checkout", p3.ok, p3.ok ? "" : p3.text.slice(0, 200));
  const done3 = await events("checkout.session.completed", (e) => e.data.object.id === c3.body.id);
  const subId = done3[0]?.data.object.subscription;
  if (done3.length) await deliver(done3[0]);
  const paid = await events("invoice.paid", (e) => e.data.object.customer === done3[0]?.data.object.customer);
  if (paid.length) await deliver(paid[0]);
  const m3 = await me(tok);
  record("real invoice.paid -> Unlimited active", m3.unlimited === true && m3.plan === "monthly", `period end ${m3.subscription?.current_period_end}`);
  const portal = await call("POST", "/v1/portal", null, tok);
  record("customer portal session", portal.status === 200 && /billing\.stripe\.com/.test(portal.body.url || ""), portal.status === 200 ? "" : portal.body.error);
  if (subId) {
    await stripe("DELETE", `subscriptions/${subId}`);
    const del = await events("customer.subscription.deleted", (e) => e.data.object.id === subId);
    record("real customer.subscription.deleted -> Unlimited ended", del.length === 1 && (await deliver(del[0])) === "ok" && (await me(tok)).unlimited === false);
  }
  // 8. Every package creates a Stripe session with exactly the approved USD amount.
  const want = { credits_1: 1900, credits_3: 2950, credits_8: 5900, credits_15: 8850, unlimited_monthly: 7495, unlimited_annual: 29995 };
  const got = {};
  for (const pkg of Object.keys(want)) { const c = await call("POST", "/v1/checkout", { package: pkg }, tok); got[pkg] = (await stripe("GET", `checkout/sessions/${c.body.id}`)).amount_total; }
  record("all six packages priced exactly by Stripe", Object.keys(want).every((k) => got[k] === want[k]), JSON.stringify(got));
  const annual = await stripe("GET", `checkout/sessions/${(await call("POST", "/v1/checkout", { package: "unlimited_annual" }, tok)).body.id}?expand[]=line_items`);
  record("annual plan recurs yearly", annual.line_items?.data?.[0]?.price?.recurring?.interval === "year");

  // 9. Renewal and failed renewal with a Stripe TEST CLOCK (fast-forwards a sandbox customer).
  const clock = await stripe("POST", "test_helpers/test_clocks", { frozen_time: String(Math.floor(Date.now() / 1000)), name: "VEENA renewal test" });
  try {
    const cus = await stripe("POST", "customers", { email: `renewal+${Date.now()}@example.com`, test_clock: clock.id, payment_method: "pm_card_visa", "invoice_settings[default_payment_method]": "pm_card_visa" });
    db.prepare("UPDATE accounts SET stripe_customer_id = ? WHERE id = ?").run(cus.id, acct);
    const prod = await stripe("POST", "products", { name: "VEENA Unlimited (sandbox test)" });
    const price = await stripe("POST", "prices", { product: prod.id, currency: "usd", unit_amount: "7495", "recurring[interval]": "month" });
    const sub = await stripe("POST", "subscriptions", { customer: cus.id, "items[0][price]": price.id, "metadata[account_id]": acct });
    db.prepare("INSERT OR REPLACE INTO subscriptions (account_id, stripe_subscription_id, plan, status, updated_at) VALUES (?, ?, 'monthly', 'incomplete', ?)").run(acct, sub.id, new Date().toISOString());
    const first = await events("invoice.paid", (e) => e.data.object.subscription === sub.id || e.data.object.parent?.subscription_details?.subscription === sub.id || e.data.object.customer === cus.id);
    if (first.length) await deliver(first[0]);
    const end1 = (await me(tok)).subscription?.current_period_end;
    const advance = async (days) => {
      const t = (await stripe("GET", `test_helpers/test_clocks/${clock.id}`)).frozen_time + days * 86400;
      await stripe("POST", `test_helpers/test_clocks/${clock.id}/advance`, { frozen_time: String(t) });
      for (let i = 0; i < 40 && (await stripe("GET", `test_helpers/test_clocks/${clock.id}`)).status !== "ready"; i++) await new Promise((r) => setTimeout(r, 3000));
    };
    await advance(32);
    const paid = (await events("invoice.paid", (e) => e.data.object.customer === cus.id)).filter((e) => e.id !== first[0]?.id);
    for (const e of paid) await deliver(e);
    const end2 = (await me(tok)).subscription?.current_period_end;
    record("renewal: real renewal invoice.paid extends the paid period", paid.length >= 1 && end2 > end1, `${end1} -> ${end2}`);
    // Failed renewal: switch to a card that is declined on later charges, then advance another month.
    const bad = await stripe("POST", "payment_methods/pm_card_chargeCustomerFail/attach", { customer: cus.id }).catch(() => null)
      || await stripe("POST", "payment_methods/pm_card_visa_chargeDeclined/attach", { customer: cus.id });
    await stripe("POST", `customers/${cus.id}`, { "invoice_settings[default_payment_method]": bad.id });
    await advance(32);
    const failed = await events("invoice.payment_failed", (e) => e.data.object.customer === cus.id);
    for (const e of failed.slice(0, 1)) await deliver(e);
    record("failed renewal: real invoice.payment_failed -> past_due", failed.length >= 1 && (await me(tok)).subscription?.status === "past_due",
      `status ${(await me(tok)).subscription?.status}`);
  } finally {
    await stripe("DELETE", `test_helpers/test_clocks/${clock.id}`).catch(() => {});  // removes the sandbox test customer too
  }

  record("payment history recorded", (await call("GET", "/v1/history", null, tok)).body.payments.length >= 2);
  void acct;
} catch (e) {
  record("sandbox run completed without errors", false, e.message);
} finally {
  await browser.close();
  const out = path.join(root, "test", "sandbox-results.json");
  fs.writeFileSync(out, JSON.stringify({ ran_at: new Date().toISOString(), stripe_mode: "test", signature_note: "event payloads from Stripe; delivery signed locally", results }, null, 2));
  console.log(`\n${results.filter((r) => r.pass).length}/${results.length} passed · ${out}`);
}
