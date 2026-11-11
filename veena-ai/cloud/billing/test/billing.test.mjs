// VEENA Billing tests: real Worker code on SQLite (D1 shim) with a local Stripe SIMULATOR.
// No network, no real Stripe account, no real payments. Webhooks are signed exactly like Stripe's.
//   node --test cloud/billing/test/billing.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { DatabaseSync } from "node:sqlite";
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import * as B from "../src/worker.js";

const root = path.resolve(import.meta.dirname, "..");
function d1() {
  const db = new DatabaseSync(":memory:");
  db.exec(fs.readFileSync(path.join(root, "schema.sql"), "utf8"));
  const norm = (sql) => sql.replace(/\?(\d+)/g, "?");
  const expand = (sql, a) => { const o = [...sql.matchAll(/\?(\d+)/g)].map((m) => Number(m[1]) - 1); return o.length ? o.map((i) => a[i]) : a; };
  const prep = (sql) => { const st = { args: [], bind(...a) { return { ...st, args: a }; },
    async all() { return { results: db.prepare(norm(sql)).all(...expand(sql, this.args)) }; },
    async first() { return db.prepare(norm(sql)).get(...expand(sql, this.args)) ?? null; },
    async run() { const r = db.prepare(norm(sql)).run(...expand(sql, this.args)); return { meta: { changes: Number(r.changes) } }; } }; return st; };
  return { db, prepare: prep, async batch(l) { db.exec("BEGIN"); try { for (const s of l) await s.run(); db.exec("COMMIT"); } catch (e) { db.exec("ROLLBACK"); throw e; } } };
}

// ---- Stripe simulator ----
function stripeSim() {
  const calls = [];
  let n = 0;
  const fetch = async (url, init) => {
    const params = Object.fromEntries(new URLSearchParams(init.body || ""));
    calls.push({ url, params, auth: init.headers.authorization });
    if (url.endsWith("/checkout/sessions")) return new Response(JSON.stringify({ id: "cs_test_" + ++n, url: "https://checkout.stripe.com/c/pay/cs_test_" + n }), { status: 200 });
    if (url.endsWith("/billing_portal/sessions")) return new Response(JSON.stringify({ url: "https://billing.stripe.com/p/session/test_" + ++n }), { status: 200 });
    return new Response(JSON.stringify({ error: { message: "not simulated" } }), { status: 400 });
  };
  return { fetch, calls };
}
const WHSEC = "whsec_test_simulator";
const sign = (payload, t = Math.floor(Date.now() / 1000), secret = WHSEC) =>
  `t=${t},v1=${crypto.createHmac("sha256", secret).update(`${t}.${payload}`).digest("hex")}`;

function mkEnv(over = {}) {
  const sim = stripeSim(), mail = [];
  return { sim, mail, env: { DB: d1(), CODE_PEPPER: "test-pepper-0123456789abcdef", STRIPE_SECRET_KEY: "sk_test_simulator", STRIPE_WEBHOOK_SECRET: WHSEC, SITE_URL: "https://florina787.github.io/Data-sets",
    fetch: sim.fetch, sendEmail: async (to, subj, text) => mail.push({ to, code: text.match(/\d{6}/)[0] }), ...over } };
}
const call = (env, method, p, body, token, headers = {}) => B.default.fetch(new Request("https://billing.example" + p, {
  method, body: body === undefined ? undefined : typeof body === "string" ? body : JSON.stringify(body),
  headers: { "content-type": "application/json", ...(token ? { authorization: "Bearer " + token } : {}), ...headers } }), env).then(async (r) => ({ status: r.status, body: await r.json() }));
const install = () => crypto.randomUUID();
async function signIn(ctx, email, inst) {
  await call(ctx.env, "POST", "/v1/auth/start", { email, install_id: inst });
  const code = ctx.mail.filter((m) => m.to === email.toLowerCase()).at(-1).code;
  return (await call(ctx.env, "POST", "/v1/auth/verify", { email, code, install_id: inst })).body.token;
}
const useOnce = async (env, tok, feature, ok = true) => {
  const op = crypto.randomUUID();
  const a = await call(env, "POST", "/v1/usage/authorize", { op_id: op, feature }, tok);
  if (!a.body.allowed) return a.body;
  await call(env, "POST", ok ? "/v1/usage/commit" : "/v1/usage/release", { op_id: op }, tok);
  return a.body;
};
const webhook = (env, ev, sig) => { const payload = JSON.stringify(ev); return call(env, "POST", "/v1/stripe/webhook", payload, null, { "stripe-signature": sig ?? sign(payload) }); };

test("prices are exactly the approved USD packages", async () => {
  const { env } = mkEnv();
  const r = await call(env, "GET", "/v1/prices");
  const p = r.body.prices;
  assert.deepEqual([p.credits_1.usd_cents, p.credits_3.usd_cents, p.credits_8.usd_cents, p.credits_15.usd_cents], [1900, 2950, 5900, 8850]);
  assert.deepEqual([p.credits_1.minutes, p.credits_3.minutes, p.credits_8.minutes, p.credits_15.minutes], [60, 180, 480, 900]);
  assert.equal(p.unlimited_monthly.usd_cents, 7495); assert.equal(p.unlimited_annual.usd_cents, 29995);
  assert.equal(r.body.currency, "usd"); assert.equal(r.body.trial_uses, 3);
});

test("email sign-in: code required, wrong code counted, attempts and requests limited", async () => {
  const ctx = mkEnv(), inst = install();
  await call(ctx.env, "POST", "/v1/auth/start", { email: "Ana@Example.com", install_id: inst });
  assert.equal((await call(ctx.env, "POST", "/v1/auth/verify", { email: "ana@example.com", code: "000000", install_id: inst })).status, 400);
  const code = ctx.mail.at(-1).code;
  const ok = await call(ctx.env, "POST", "/v1/auth/verify", { email: "ana@example.com", code, install_id: inst });
  assert.equal(ok.status, 200); assert.match(ok.body.token, /^[0-9a-f]{64}$/);
  assert.equal(ctx.env.DB.db.prepare("SELECT COUNT(*) n FROM email_codes").get().n, 0, "code is single-use");
  for (let i = 0; i < 5; i++) await call(ctx.env, "POST", "/v1/auth/start", { email: "spam@example.com", install_id: inst });
  assert.equal((await call(ctx.env, "POST", "/v1/auth/start", { email: "spam@example.com", install_id: inst })).status, 429);
  assert.equal(ctx.env.DB.db.prepare("SELECT COUNT(*) n FROM email_codes WHERE code_hash LIKE '%' AND length(code_hash)=64").get().n >= 1, true, "only hashes stored");
});

test("free trial: 3 successful uses per feature; failures and cancellations are free; commits are idempotent", async () => {
  const ctx = mkEnv(), tok = await signIn(ctx, "t@example.com", install());
  assert.deepEqual((await call(ctx.env, "GET", "/v1/me", undefined, tok)).body.trial_remaining, { chat: 3, documents: 3, screen: 3, meeting: 3, interview: 3 });
  await useOnce(ctx.env, tok, "chat", false);                          // failed -> released
  const op = crypto.randomUUID();
  await call(ctx.env, "POST", "/v1/usage/authorize", { op_id: op, feature: "chat" }, tok);
  await call(ctx.env, "POST", "/v1/usage/commit", { op_id: op }, tok);
  await call(ctx.env, "POST", "/v1/usage/commit", { op_id: op }, tok);  // retried commit
  let me = (await call(ctx.env, "GET", "/v1/me", undefined, tok)).body;
  assert.equal(me.trial_remaining.chat, 2, "one success = one use, release and duplicate commit free");
  await useOnce(ctx.env, tok, "chat"); await useOnce(ctx.env, tok, "chat");
  const fourth = await useOnce(ctx.env, tok, "chat");
  assert.equal(fourth.allowed, false); assert.equal(fourth.reason, "trial_used");
  me = (await call(ctx.env, "GET", "/v1/me", undefined, tok)).body;
  assert.equal(me.trial_remaining.chat, 0); assert.equal(me.trial_remaining.documents, 3, "features are independent");
});

test("abuse: a new email on the same installation does not reset the trial; repeat registrations are blocked", async () => {
  const ctx = mkEnv(), inst = install();
  const a = await signIn(ctx, "first@example.com", inst);
  for (let i = 0; i < 3; i++) await useOnce(ctx.env, a, "screen");
  const b = await signIn(ctx, "second@example.com", inst);
  assert.equal((await call(ctx.env, "GET", "/v1/me", undefined, b)).body.trial_remaining.screen, 0);
  assert.equal((await call(ctx.env, "GET", "/v1/me", undefined, b)).body.trial_remaining.chat, 3);
  const c = await signIn(ctx, "third@example.com", inst);                // 3rd account on one installation
  assert.deepEqual(Object.values((await call(ctx.env, "GET", "/v1/me", undefined, c)).body.trial_remaining), [0, 0, 0, 0, 0]);
  assert.equal((await call(ctx.env, "POST", "/v1/appeal", { reason: "Family computer, new account" }, c)).status, 200);
});

test("reinstall: the same account on a new installation keeps its used trial", async () => {
  const ctx = mkEnv();
  const a = await signIn(ctx, "re@example.com", install());
  for (let i = 0; i < 2; i++) await useOnce(ctx.env, a, "documents");
  const again = await signIn(ctx, "re@example.com", install());
  assert.equal((await call(ctx.env, "GET", "/v1/me", undefined, again)).body.trial_remaining.documents, 1);
});

test("checkout uses Stripe test mode only; success redirect alone grants nothing", async () => {
  const ctx = mkEnv(), tok = await signIn(ctx, "buy@example.com", install());
  const r = await call(ctx.env, "POST", "/v1/checkout", { package: "credits_3" }, tok);
  assert.equal(r.status, 200); assert.match(r.body.url, /^https:\/\/checkout\.stripe\.com\//);
  const sent = ctx.sim.calls.at(-1).params;
  assert.equal(sent["line_items[0][price_data][unit_amount]"], "2950"); assert.equal(sent["line_items[0][price_data][currency]"], "usd"); assert.equal(sent.mode, "payment");
  assert.equal((await call(ctx.env, "GET", "/v1/me", undefined, tok)).body.credit_minutes, 0, "no credit until Stripe confirms by webhook");
  const live = mkEnv({ STRIPE_SECRET_KEY: "sk_live_x" }), lt = await signIn(live, "l@example.com", install());
  assert.equal((await call(live.env, "POST", "/v1/checkout", { package: "credits_1" }, lt)).status, 503, "live keys refused");
  const sub = await call(ctx.env, "POST", "/v1/checkout", { package: "unlimited_annual" }, tok);
  assert.equal(sub.status, 200);
  assert.equal(ctx.sim.calls.at(-1).params["line_items[0][price_data][recurring][interval]"], "year");
});

test("webhooks: signature verified, stale and tampered rejected, replays processed once", async () => {
  const ctx = mkEnv(), tok = await signIn(ctx, "w@example.com", install());
  const acct = ctx.env.DB.db.prepare("SELECT id FROM accounts").get().id;
  const ev = { id: "evt_1", type: "checkout.session.completed", data: { object: { id: "cs_test_9", client_reference_id: acct, customer: "cus_1", payment_status: "paid", payment_intent: "pi_1", amount_total: 1900, currency: "usd", metadata: { account_id: acct, package: "credits_1" } } } };
  const payload = JSON.stringify(ev);
  assert.equal((await webhook(ctx.env, ev, sign(payload, undefined, "whsec_wrong"))).status, 400);
  assert.equal((await webhook(ctx.env, ev, sign(payload, Math.floor(Date.now() / 1000) - 3600))).status, 400, "stale");
  assert.equal((await call(ctx.env, "POST", "/v1/stripe/webhook", payload.replace("1900", "1"), null, { "stripe-signature": sign(payload) })).status, 400, "tampered");
  assert.equal((await webhook(ctx.env, ev)).body.result, "ok");
  assert.equal((await webhook(ctx.env, ev)).body.result, "duplicate");
  assert.equal((await webhook(ctx.env, { ...ev, id: "evt_1b" })).body.result, "ok", "same session, new event id");
  const me = (await call(ctx.env, "GET", "/v1/me", undefined, tok)).body;
  assert.equal(me.credit_minutes, 60, "credited exactly once");
  const unpaid = { id: "evt_2", type: "checkout.session.completed", data: { object: { ...ev.data.object, id: "cs_test_10", payment_status: "unpaid" } } };
  assert.equal((await webhook(ctx.env, unpaid)).body.result, "unpaid");
  assert.equal((await call(ctx.env, "GET", "/v1/me", undefined, tok)).body.credit_minutes, 60);
});

test("credits: session features charged in 30-minute blocks after success; concurrent reservations can't overspend; refunds reverse", async () => {
  const ctx = mkEnv(), tok = await signIn(ctx, "c@example.com", install());
  const acct = ctx.env.DB.db.prepare("SELECT id FROM accounts").get().id;
  for (let i = 0; i < 3; i++) await useOnce(ctx.env, tok, "meeting");    // trial first
  await webhook(ctx.env, { id: "evt_c", type: "checkout.session.completed", data: { object: { id: "cs_c", client_reference_id: acct, customer: "cus_c", payment_status: "paid", payment_intent: "pi_c", amount_total: 1900, currency: "usd", metadata: { package: "credits_1" } } } });
  const ops = [crypto.randomUUID(), crypto.randomUUID(), crypto.randomUUID()];
  const res = await Promise.all(ops.map((op) => call(ctx.env, "POST", "/v1/usage/authorize", { op_id: op, feature: "meeting", minutes: 25 }, tok)));
  assert.equal(res.filter((r) => r.body.allowed).length, 2, "60 minutes cover two 30-minute blocks, not three");
  assert.equal(res.find((r) => r.body.allowed).body.minutes, 30);
  const allowed = ops.filter((_, i) => res[i].body.allowed);
  await call(ctx.env, "POST", "/v1/usage/commit", { op_id: allowed[0] }, tok);
  await call(ctx.env, "POST", "/v1/usage/release", { op_id: allowed[1] }, tok);   // e.g. cancelled
  assert.equal((await call(ctx.env, "GET", "/v1/me", undefined, tok)).body.credit_minutes, 30);
  assert.equal((await useOnce(ctx.env, tok, "chat")).kind, "trial");
  await webhook(ctx.env, { id: "evt_r", type: "charge.refunded", data: { object: { id: "ch_1", payment_intent: "pi_c", customer: "cus_c", amount: 1900, amount_refunded: 950, currency: "usd", metadata: {} } } });
  assert.equal((await call(ctx.env, "GET", "/v1/me", undefined, tok)).body.credit_minutes, 0, "half refunded = 30 minutes removed");
  const h = (await call(ctx.env, "GET", "/v1/history", undefined, tok)).body;
  assert.equal(h.payments.length, 2); assert.ok(h.ledger.some((l) => l.reason === "refund"));
});

test("subscriptions: create, renew, failed payment, cancel", async () => {
  const ctx = mkEnv(), tok = await signIn(ctx, "s@example.com", install());
  const acct = ctx.env.DB.db.prepare("SELECT id FROM accounts").get().id;
  const end = (d) => Math.floor(Date.now() / 1000) + d * 86400;
  await webhook(ctx.env, { id: "e1", type: "checkout.session.completed", data: { object: { id: "cs_s", client_reference_id: acct, customer: "cus_s", subscription: "sub_1", payment_status: "paid", metadata: { package: "unlimited_monthly" } } } });
  assert.equal((await call(ctx.env, "GET", "/v1/me", undefined, tok)).body.unlimited, false, "not active until the invoice is paid");
  await webhook(ctx.env, { id: "e2", type: "invoice.paid", data: { object: { id: "in_1", customer: "cus_s", amount_paid: 7495, currency: "usd", lines: { data: [{ period: { end: end(30) } }] } } } });
  let me = (await call(ctx.env, "GET", "/v1/me", undefined, tok)).body;
  assert.equal(me.unlimited, true); assert.equal(me.plan, "monthly");
  assert.equal((await useOnce(ctx.env, tok, "screen")).kind, "unlimited");
  assert.equal((await call(ctx.env, "GET", "/v1/me", undefined, tok)).body.trial_remaining.screen, 3, "unlimited use does not burn trial");
  await webhook(ctx.env, { id: "e3", type: "invoice.paid", data: { object: { id: "in_2", customer: "cus_s", amount_paid: 7495, currency: "usd", lines: { data: [{ period: { end: end(60) } }] } } } });
  await webhook(ctx.env, { id: "e4", type: "invoice.payment_failed", data: { object: { id: "in_3", customer: "cus_s", amount_due: 7495, currency: "usd" } } });
  assert.equal((await call(ctx.env, "GET", "/v1/me", undefined, tok)).body.subscription.status, "past_due");
  await webhook(ctx.env, { id: "e5", type: "customer.subscription.deleted", data: { object: { id: "sub_1", customer: "cus_s", status: "canceled", metadata: {} } } });
  me = (await call(ctx.env, "GET", "/v1/me", undefined, tok)).body;
  assert.equal(me.unlimited, false); assert.equal(me.subscription.status, "canceled");
  const h = (await call(ctx.env, "GET", "/v1/history", undefined, tok)).body;
  assert.deepEqual(h.payments.map((p) => p.status).sort(), ["failed", "paid", "paid"]);
  assert.equal((await call(ctx.env, "POST", "/v1/portal", undefined, tok)).status, 200);
});

test("unauthorised access is refused; one account can't touch another's operations", async () => {
  const ctx = mkEnv();
  assert.equal((await call(ctx.env, "GET", "/v1/me")).status, 401);
  assert.equal((await call(ctx.env, "GET", "/v1/me", undefined, "f".repeat(64))).status, 401);
  const a = await signIn(ctx, "a@example.com", install()), b = await signIn(ctx, "b@example.com", install());
  const op = crypto.randomUUID();
  await call(ctx.env, "POST", "/v1/usage/authorize", { op_id: op, feature: "chat" }, a);
  assert.equal((await call(ctx.env, "POST", "/v1/usage/commit", { op_id: op }, b)).status, 404);
  assert.equal((await call(ctx.env, "POST", "/v1/checkout", { package: "credits_1" })).status, 401);
});

test("abandoned reservations expire and are never charged", async () => {
  const ctx = mkEnv(), tok = await signIn(ctx, "x@example.com", install());
  await call(ctx.env, "POST", "/v1/usage/authorize", { op_id: crypto.randomUUID(), feature: "interview" }, tok);
  assert.equal((await call(ctx.env, "GET", "/v1/me", undefined, tok)).body.trial_remaining.interview, 2, "reserved");
  assert.equal(await B.expireReservations(ctx.env, new Date(Date.now() + 4 * 3600000)), 1);
  assert.equal((await call(ctx.env, "GET", "/v1/me", undefined, tok)).body.trial_remaining.interview, 3, "released, not consumed");
});

// ---------------- security fixes (2026-11-11 audit) ----------------
test("security: another account's operation id is refused, not reported as allowed", async () => {
  const ctx = mkEnv(), a = await signIn(ctx, "sa@example.com", install()), b = await signIn(ctx, "sb@example.com", install());
  const op = crypto.randomUUID();
  await call(ctx.env, "POST", "/v1/usage/authorize", { op_id: op, feature: "chat" }, a);
  assert.equal((await call(ctx.env, "POST", "/v1/usage/authorize", { op_id: op, feature: "chat" }, b)).status, 409);
});

test("security: credits granted only for the exact package amount in USD", async () => {
  const ctx = mkEnv(), tok = await signIn(ctx, "amt@example.com", install());
  const acct = ctx.env.DB.db.prepare("SELECT id FROM accounts").get().id;
  const base = { client_reference_id: acct, customer: "cus_a", payment_status: "paid", currency: "usd", metadata: { package: "credits_15" } };
  assert.equal((await webhook(ctx.env, { id: "ea1", type: "checkout.session.completed", data: { object: { ...base, id: "cs_a1", payment_intent: "pi_a1", amount_total: 1900 } } })).body.result, "amount_mismatch");
  assert.equal((await webhook(ctx.env, { id: "ea2", type: "checkout.session.completed", data: { object: { ...base, id: "cs_a2", payment_intent: "pi_a2", amount_total: 8850, currency: "eur" } } })).body.result, "amount_mismatch");
  assert.equal((await call(ctx.env, "GET", "/v1/me", undefined, tok)).body.credit_minutes, 0);
  assert.equal((await webhook(ctx.env, { id: "ea3", type: "checkout.session.completed", data: { object: { ...base, id: "cs_a3", payment_intent: "pi_a3", amount_total: 8850 } } })).body.result, "ok");
  assert.equal((await call(ctx.env, "GET", "/v1/me", undefined, tok)).body.credit_minutes, 900);
});

test("security: expired checkout grants nothing; delayed payment success credits once", async () => {
  const ctx = mkEnv(), tok = await signIn(ctx, "exp@example.com", install());
  const acct = ctx.env.DB.db.prepare("SELECT id FROM accounts").get().id;
  const o = { id: "cs_e", client_reference_id: acct, customer: "cus_e", payment_intent: "pi_e", amount_total: 1900, currency: "usd", metadata: { package: "credits_1" } };
  assert.equal((await webhook(ctx.env, { id: "ex1", type: "checkout.session.expired", data: { object: { ...o, payment_status: "unpaid" } } })).body.result, "expired");
  assert.equal((await webhook(ctx.env, { id: "ex2", type: "checkout.session.completed", data: { object: { ...o, payment_status: "unpaid" } } })).body.result, "unpaid");
  assert.equal((await webhook(ctx.env, { id: "ex3", type: "checkout.session.async_payment_succeeded", data: { object: { ...o, payment_status: "paid" } } })).body.result, "ok");
  assert.equal((await call(ctx.env, "GET", "/v1/me", undefined, tok)).body.credit_minutes, 60);
});

test("security: checkout and portal are rate limited per account", async () => {
  const ctx = mkEnv(), tok = await signIn(ctx, "rl@example.com", install());
  let last;
  for (let i = 0; i < 21; i++) last = await call(ctx.env, "POST", "/v1/checkout", { package: "credits_1" }, tok);
  assert.equal(last.status, 429);
});

test("security: sign-out revokes the server session", async () => {
  const ctx = mkEnv(), tok = await signIn(ctx, "lo@example.com", install());
  assert.equal((await call(ctx.env, "POST", "/v1/auth/logout", undefined, tok)).status, 200);
  assert.equal((await call(ctx.env, "GET", "/v1/me", undefined, tok)).status, 401);
});

test("security: sign-in refuses to run without a strong code pepper", async () => {
  const ctx = mkEnv({ CODE_PEPPER: "" });
  assert.equal((await call(ctx.env, "POST", "/v1/auth/start", { email: "p@example.com", install_id: install() })).status, 503);
});

test("security: a fully refunded subscription payment ends Unlimited; an active row with no paid period is not unlimited", async () => {
  const ctx = mkEnv(), tok = await signIn(ctx, "rf@example.com", install());
  const acct = ctx.env.DB.db.prepare("SELECT id FROM accounts").get().id;
  await webhook(ctx.env, { id: "r1", type: "checkout.session.completed", data: { object: { id: "cs_r", client_reference_id: acct, customer: "cus_r", subscription: "sub_r", payment_status: "paid", metadata: { package: "unlimited_annual" } } } });
  ctx.env.DB.db.prepare("UPDATE subscriptions SET status='active' WHERE account_id=?").run(acct);
  assert.equal((await call(ctx.env, "GET", "/v1/me", undefined, tok)).body.unlimited, false, "no paid period yet");
  await webhook(ctx.env, { id: "r2", type: "invoice.paid", data: { object: { id: "in_r", customer: "cus_r", amount_paid: 29995, currency: "usd", lines: { data: [{ period: { end: Math.floor(Date.now() / 1000) + 365 * 86400 } }] } } } });
  assert.equal((await call(ctx.env, "GET", "/v1/me", undefined, tok)).body.unlimited, true);
  await webhook(ctx.env, { id: "r3", type: "charge.refunded", data: { object: { id: "ch_r", invoice: "in_r", customer: "cus_r", amount: 29995, amount_refunded: 29995, currency: "usd", metadata: {} } } });
  assert.equal((await call(ctx.env, "GET", "/v1/me", undefined, tok)).body.unlimited, false);
});

test("email: Resend provider sends only the address and the code; unconfigured provider fails closed", async () => {
  const sent = [];
  const mailer = B.makeMailer({ EMAIL_PROVIDER: "resend", RESEND_API_KEY: "re_test", EMAIL_FROM: "VEENA <codes@example.com>",
    fetch: async (url, init) => { sent.push({ url, body: JSON.parse(init.body), auth: init.headers.authorization }); return new Response("{}", { status: 200 }); } });
  await mailer("user@example.com", "Your VEENA sign-in code", "Your VEENA code is 123456.");
  assert.equal(sent[0].url, "https://api.resend.com/emails");
  assert.deepEqual(Object.keys(sent[0].body).sort(), ["from", "subject", "text", "to"]);
  await assert.rejects(B.makeMailer({})("a@b.co", "s", "t"), /not configured/);
  await assert.rejects(B.makeMailer({ EMAIL_PROVIDER: "resend" })("a@b.co", "s", "t"), /not configured/);
});
