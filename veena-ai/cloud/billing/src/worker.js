// VEENA Billing — Cloudflare Worker + D1 + Stripe (REST, no SDK). TEST MODE until the owner approves live.
//
// The app never sends content: only an installation id, a feature name, an operation id and minutes.
//
//  POST /v1/auth/start      {email, install_id}           -> emails a 6-digit code (rate limited)
//  POST /v1/auth/verify     {email, code, install_id}     -> {token}  (links account <-> installation)
//  GET  /v1/me                                             -> plan, credit minutes, trial remaining per feature
//  POST /v1/usage/authorize {op_id, feature, minutes?}    -> {allowed, kind}  (reserves; nothing is charged yet)
//  POST /v1/usage/commit    {op_id}                        -> charges ONLY after the operation succeeded
//  POST /v1/usage/release   {op_id}                        -> failed / cancelled: nothing is charged
//  POST /v1/checkout        {package}                      -> {url} Stripe-hosted Checkout (test mode)
//  POST /v1/portal                                         -> {url} Stripe customer portal
//  GET  /v1/history                                        -> payments + credit ledger
//  POST /v1/appeal          {reason}                       -> recorded for the owner
//  POST /v1/stripe/webhook                                 -> signature-verified, idempotent
//  GET  /v1/prices                                         -> public price list (the website reads this)

export const PRICES = {
  credits_1: { kind: "credits", usd_cents: 1900, minutes: 60, name: "1 Credit (60 minutes)" },
  credits_3: { kind: "credits", usd_cents: 2950, minutes: 180, name: "3 Credits (180 minutes)" },
  credits_8: { kind: "credits", usd_cents: 5900, minutes: 480, name: "8 Credits (480 minutes)" },
  credits_15: { kind: "credits", usd_cents: 8850, minutes: 900, name: "15 Credits (900 minutes)" },
  unlimited_monthly: { kind: "subscription", usd_cents: 7495, interval: "month", plan: "monthly", name: "VEENA Unlimited — monthly" },
  unlimited_annual: { kind: "subscription", usd_cents: 29995, interval: "year", plan: "annual", name: "VEENA Unlimited — annual" },
};
// Verified, user-facing AI features. Each gets TRIAL_USES successful free uses.
export const FEATURES = ["chat", "documents", "screen", "meeting", "interview"];
export const SESSION_FEATURES = ["meeting", "interview"]; // charged in 30-minute blocks of credit time
export const TRIAL_USES = 3;
const BLOCK = 30, MAX_ACCOUNTS_PER_INSTALL_WITH_TRIAL = 2, RESERVE_TTL_MIN = 180;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const EMAIL = /^[^\s@]{1,64}@[^\s@]{1,190}\.[a-z]{2,24}$/i;

export class HttpError extends Error { constructor(status, msg) { super(msg); this.status = status; } }
const json = (d, s = 200) => new Response(JSON.stringify(d), { status: s, headers: { "content-type": "application/json", "cache-control": "no-store" } });
const nowIso = (n) => (n || new Date()).toISOString();
const day = (n) => nowIso(n).slice(0, 10);
const hex = (buf) => [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
export async function sha256(s) { return hex(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s))); }
const randomToken = () => hex(crypto.getRandomValues(new Uint8Array(32)));
function safeEqual(a, b) { if (a.length !== b.length) return false; let d = 0; for (let i = 0; i < a.length; i++) d |= a.charCodeAt(i) ^ b.charCodeAt(i); return d === 0; }

async function body(request, max = 4096) {
  const t = await request.text();
  if (t.length > max) throw new HttpError(413, "body too large");
  try { return JSON.parse(t || "{}"); } catch { throw new HttpError(400, "invalid JSON"); }
}
async function bump(env, key, limit, now) {
  const r = await env.DB.prepare("INSERT INTO rate (key, day, n) VALUES (?1, ?2, 1) ON CONFLICT (key, day) DO UPDATE SET n = n + 1 RETURNING n").bind(key, day(now)).first();
  if (r.n > limit) throw new HttpError(429, "too many requests, try again tomorrow");
}

// ---------------- accounts ----------------
function requirePepper(env) {
  if (!env.CODE_PEPPER || env.CODE_PEPPER.length < 16) throw new HttpError(503, "sign-in is not configured");
}

export async function authStart(env, b, now = new Date()) {
  requirePepper(env);
  const email = String(b.email || "").trim().toLowerCase();
  if (!EMAIL.test(email)) throw new HttpError(400, "enter a valid email address");
  if (!UUID.test(b.install_id || "")) throw new HttpError(400, "bad install_id");
  await bump(env, "email:" + email, 5, now);
  await bump(env, "install:" + b.install_id, 10, now);
  const code = String(crypto.getRandomValues(new Uint32Array(1))[0] % 1000000).padStart(6, "0");
  await env.DB.prepare("INSERT INTO email_codes (email, code_hash, expires_at, attempts) VALUES (?1, ?2, ?3, 0) ON CONFLICT (email) DO UPDATE SET code_hash = ?2, expires_at = ?3, attempts = 0")
    .bind(email, await sha256(env.CODE_PEPPER + code), nowIso(new Date(now.getTime() + 10 * 60000))).run();
  await env.sendEmail(email, "Your VEENA sign-in code", `Your VEENA code is ${code}. It expires in 10 minutes.`);
  return { sent: true };
}

export async function authVerify(env, b, now = new Date()) {
  requirePepper(env);
  const email = String(b.email || "").trim().toLowerCase();
  if (!UUID.test(b.install_id || "")) throw new HttpError(400, "bad install_id");
  const row = await env.DB.prepare("SELECT * FROM email_codes WHERE email = ?1").bind(email).first();
  if (!row || row.expires_at < nowIso(now) || row.attempts >= 5) throw new HttpError(400, "code expired, request a new one");
  if (!safeEqual(row.code_hash, await sha256(env.CODE_PEPPER + String(b.code || "")))) {
    await env.DB.prepare("UPDATE email_codes SET attempts = attempts + 1 WHERE email = ?1").bind(email).run();
    throw new HttpError(400, "wrong code");
  }
  await env.DB.prepare("DELETE FROM email_codes WHERE email = ?1").bind(email).run();
  let acct = await env.DB.prepare("SELECT * FROM accounts WHERE email = ?1").bind(email).first();
  if (!acct) {
    // Repeat-registration rule: an installation that already created MAX accounts gives no new trial.
    const n = (await env.DB.prepare("SELECT COUNT(*) n FROM account_installs WHERE install_id = ?1").bind(b.install_id).first()).n;
    acct = { id: crypto.randomUUID(), trial_blocked: n >= MAX_ACCOUNTS_PER_INSTALL_WITH_TRIAL ? 1 : 0 };
    await env.DB.prepare("INSERT INTO accounts (id, email, verified_at, trial_blocked, created_at) VALUES (?1, ?2, ?3, ?4, ?3)").bind(acct.id, email, nowIso(now), acct.trial_blocked).run();
  }
  await env.DB.prepare("INSERT OR IGNORE INTO account_installs (account_id, install_id, linked_at) VALUES (?1, ?2, ?3)").bind(acct.id, b.install_id, nowIso(now)).run();
  const token = randomToken();
  await env.DB.prepare("INSERT INTO sessions (token_hash, account_id, install_id, expires_at) VALUES (?1, ?2, ?3, ?4)")
    .bind(await sha256(token), acct.id, b.install_id, nowIso(new Date(now.getTime() + 90 * 86400000))).run();
  return { token, account_id: acct.id };
}

async function session(env, request, now = new Date()) {
  const tok = (request.headers.get("authorization") || "").replace(/^Bearer\s+/i, "");
  if (!/^[0-9a-f]{64}$/.test(tok)) throw new HttpError(401, "sign in required");
  const s = await env.DB.prepare("SELECT * FROM sessions WHERE token_hash = ?1").bind(await sha256(tok)).first();
  if (!s || s.expires_at < nowIso(now)) throw new HttpError(401, "sign in required");
  return s;
}

// ---------------- entitlements ----------------
const balanceSql = "SELECT COALESCE(SUM(delta),0) - COALESCE((SELECT SUM(minutes) FROM operations WHERE account_id = ?1 AND kind = 'credits' AND status = 'reserved'),0) AS available FROM credit_ledger WHERE account_id = ?1";

export async function trialRemaining(env, accountId, installId) {
  const acct = await env.DB.prepare("SELECT trial_blocked FROM accounts WHERE id = ?1").bind(accountId).first();
  const rows = (await env.DB.prepare("SELECT subject, feature, used FROM trial_usage WHERE subject IN (?1, ?2)").bind("a:" + accountId, "i:" + installId).all()).results;
  const reserved = (await env.DB.prepare("SELECT feature, COUNT(*) n FROM operations WHERE (account_id = ?1 OR install_id = ?2) AND kind = 'trial' AND status = 'reserved' GROUP BY feature").bind(accountId, installId).all()).results;
  const out = {};
  for (const f of FEATURES) {
    if (acct?.trial_blocked) { out[f] = 0; continue; }
    const used = Math.max(0, ...rows.filter((r) => r.feature === f).map((r) => r.used));
    out[f] = Math.max(0, TRIAL_USES - used - (reserved.find((r) => r.feature === f)?.n || 0));
  }
  return out;
}

export async function entitlements(env, s, now = new Date()) {
  const sub = await env.DB.prepare("SELECT * FROM subscriptions WHERE account_id = ?1").bind(s.account_id).first();
  // Unlimited only while a paid period is running (past_due keeps access until that period ends).
  const unlimited = !!sub && ["active", "past_due"].includes(sub.status) && !!sub.current_period_end && sub.current_period_end >= nowIso(now);
  const bal = (await env.DB.prepare(balanceSql).bind(s.account_id).first()).available;
  return { unlimited, plan: unlimited ? sub.plan : null, subscription: sub || null, credit_minutes: bal, trial_remaining: await trialRemaining(env, s.account_id, s.install_id), trial_uses: TRIAL_USES };
}

/** Reserve the right to run one operation. Order: Unlimited, then free trial, then credits (session features only). */
export async function authorize(env, s, b, now = new Date()) {
  if (!UUID.test(b.op_id || "")) throw new HttpError(400, "op_id must be a UUID v4");
  if (!FEATURES.includes(b.feature)) throw new HttpError(400, "unknown feature");
  const prev = await env.DB.prepare("SELECT * FROM operations WHERE op_id = ?1").bind(b.op_id).first();
  if (prev && prev.account_id !== s.account_id) throw new HttpError(409, "operation id already used");
  if (prev) return { allowed: prev.status !== "released", kind: prev.kind, idempotent: true };
  const e = await entitlements(env, s, now);
  const t = nowIso(now);
  const insert = (kind, minutes) => env.DB.prepare("INSERT INTO operations (op_id, account_id, install_id, feature, kind, minutes, status, created_at, updated_at) VALUES (?1, ?2, ?3, ?4, ?5, ?6, 'reserved', ?7, ?7)")
    .bind(b.op_id, s.account_id, s.install_id, b.feature, kind, minutes, t).run();
  if (e.unlimited) { await insert("unlimited", 0); return { allowed: true, kind: "unlimited" }; }
  if (e.trial_remaining[b.feature] > 0) { await insert("trial", 0); return { allowed: true, kind: "trial", remaining_after: e.trial_remaining[b.feature] - 1 }; }
  if (SESSION_FEATURES.includes(b.feature)) {
    const minutes = Math.max(BLOCK, Math.ceil((Number(b.minutes) || BLOCK) / BLOCK) * BLOCK);
    // Atomic: the reservation is only written if the available balance (incl. other reservations) covers it.
    const r = await env.DB.prepare(`INSERT INTO operations (op_id, account_id, install_id, feature, kind, minutes, status, created_at, updated_at)
      SELECT ?1, ?2, ?3, ?4, 'credits', ?5, 'reserved', ?6, ?6 WHERE (${balanceSql.replace(/\?1/g, "?2")}) >= ?5`)
      .bind(b.op_id, s.account_id, s.install_id, b.feature, minutes, t).run();
    if (r.meta.changes === 1) return { allowed: true, kind: "credits", minutes };
    return { allowed: false, reason: "not_enough_credits", needed_minutes: minutes, available_minutes: e.credit_minutes };
  }
  return { allowed: false, reason: "trial_used", message: "Your free uses of this feature are used. Unlimited covers it; credits currently apply to meeting and interview sessions." };
}

/** Charge only after success. Idempotent: committing twice charges once. */
export async function commit(env, s, b, now = new Date()) {
  const op = await env.DB.prepare("SELECT * FROM operations WHERE op_id = ?1 AND account_id = ?2").bind(b.op_id, s.account_id).first();
  if (!op) throw new HttpError(404, "unknown operation");
  if (op.status === "committed") return { committed: true, idempotent: true };
  if (op.status === "released") throw new HttpError(409, "operation was released");
  const t = nowIso(now), stmts = [env.DB.prepare("UPDATE operations SET status = 'committed', updated_at = ?2 WHERE op_id = ?1 AND status = 'reserved'").bind(op.op_id, t)];
  if (op.kind === "trial") for (const subj of ["a:" + op.account_id, "i:" + op.install_id])
    stmts.push(env.DB.prepare("INSERT INTO trial_usage (subject, feature, used) VALUES (?1, ?2, 1) ON CONFLICT (subject, feature) DO UPDATE SET used = used + 1").bind(subj, op.feature));
  if (op.kind === "credits") stmts.push(env.DB.prepare("INSERT OR IGNORE INTO credit_ledger (account_id, delta, reason, ref, created_at) VALUES (?1, ?2, 'usage', ?3, ?4)").bind(op.account_id, -op.minutes, "op:" + op.op_id, t));
  await env.DB.batch(stmts);
  return { committed: true };
}

export async function release(env, s, b, now = new Date()) {
  await env.DB.prepare("UPDATE operations SET status = 'released', updated_at = ?3 WHERE op_id = ?1 AND account_id = ?2 AND status = 'reserved'").bind(b.op_id, s.account_id, nowIso(now)).run();
  return { released: true };
}

// ---------------- Stripe ----------------
async function stripe(env, path, params, method = "POST") {
  if (!/^sk_test_/.test(env.STRIPE_SECRET_KEY || "") && env.ALLOW_LIVE !== "yes")
    throw new HttpError(503, "payments are not configured (test-mode key required)");
  const res = await env.fetch("https://api.stripe.com/v1/" + path, {
    method, headers: { authorization: "Bearer " + env.STRIPE_SECRET_KEY, "content-type": "application/x-www-form-urlencoded", "stripe-version": "2024-06-20" },
    body: method === "POST" ? new URLSearchParams(params).toString() : undefined,
  });
  const data = await res.json();
  if (!res.ok) throw new HttpError(502, "stripe: " + (data.error?.message || res.status));
  return data;
}

export async function checkout(env, s, b, now = new Date()) {
  await bump(env, "checkout:" + s.account_id, 20, now);
  const p = PRICES[b.package];
  if (!p) throw new HttpError(400, "unknown package");
  const acct = await env.DB.prepare("SELECT * FROM accounts WHERE id = ?1").bind(s.account_id).first();
  const params = {
    mode: p.kind === "subscription" ? "subscription" : "payment",
    "line_items[0][quantity]": "1",
    "line_items[0][price_data][currency]": "usd",
    "line_items[0][price_data][unit_amount]": String(p.usd_cents),
    "line_items[0][price_data][product_data][name]": p.name,
    client_reference_id: s.account_id,
    "metadata[account_id]": s.account_id, "metadata[package]": b.package,
    success_url: env.SITE_URL + "/pricing.html?checkout=success&session_id={CHECKOUT_SESSION_ID}",
    cancel_url: env.SITE_URL + "/pricing.html?checkout=cancelled",
  };
  if (p.kind === "subscription") { params["line_items[0][price_data][recurring][interval]"] = p.interval; params["subscription_data[metadata][account_id]"] = s.account_id; params["subscription_data[metadata][plan]"] = p.plan; }
  else params["payment_intent_data[metadata][account_id]"] = s.account_id;
  if (acct.stripe_customer_id) params.customer = acct.stripe_customer_id; else { params.customer_email = acct.email; if (p.kind !== "subscription") params.customer_creation = "always"; }
  const cs = await stripe(env, "checkout/sessions", params);
  return { url: cs.url, id: cs.id };
}

export async function portal(env, s, now = new Date()) {
  await bump(env, "portal:" + s.account_id, 20, now);
  const acct = await env.DB.prepare("SELECT stripe_customer_id FROM accounts WHERE id = ?1").bind(s.account_id).first();
  if (!acct?.stripe_customer_id) throw new HttpError(404, "no billing account yet");
  const ps = await stripe(env, "billing_portal/sessions", { customer: acct.stripe_customer_id, return_url: env.SITE_URL + "/pricing.html" });
  return { url: ps.url };
}

/** Verifies Stripe-Signature (HMAC-SHA256 of "t.payload"), rejects stale or tampered events. */
export async function verifyStripe(payload, header, secret, now = new Date(), toleranceS = 300) {
  const parts = Object.fromEntries((header || "").split(",").map((kv) => kv.split("=").map((x) => x.trim())).filter((p) => p.length === 2 && p[0] !== "v1"));
  const sigs = (header || "").split(",").map((x) => x.trim()).filter((x) => x.startsWith("v1=")).map((x) => x.slice(3));
  const t = Number(parts.t);
  if (!t || !sigs.length) return false;
  if (Math.abs(now.getTime() / 1000 - t) > toleranceS) return false;
  const key = await crypto.subtle.importKey("raw", new TextEncoder().encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const expected = hex(await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(`${t}.${payload}`)));
  return sigs.some((s) => safeEqual(s, expected));
}

export async function handleEvent(env, ev, now = new Date()) {
  const first = await env.DB.prepare("INSERT OR IGNORE INTO stripe_events (id, type, received_at) VALUES (?1, ?2, ?3)").bind(ev.id, ev.type, nowIso(now)).run();
  if (first.meta.changes === 0) return "duplicate";            // replayed delivery: already processed
  const o = ev.data.object, t = nowIso(now);
  const accountFor = async (meta, customer) => meta?.account_id || (customer && (await env.DB.prepare("SELECT id FROM accounts WHERE stripe_customer_id = ?1").bind(customer).first())?.id);
  switch (ev.type) {
    case "checkout.session.expired":
      return "expired";                                        // abandoned checkout: nothing is granted
    case "checkout.session.async_payment_succeeded":
    case "checkout.session.completed": {
      const accountId = o.client_reference_id || o.metadata?.account_id, p = PRICES[o.metadata?.package];
      if (!accountId || !p) return "ignored";
      if (o.customer) await env.DB.prepare("UPDATE accounts SET stripe_customer_id = ?2 WHERE id = ?1 AND stripe_customer_id IS NULL").bind(accountId, o.customer).run();
      if (p.kind === "credits") {
        if (o.payment_status !== "paid") return "unpaid";      // e.g. delayed payment methods: wait for async_payment_succeeded
        // Defence in depth: credit only if Stripe confirms exactly this package's price in USD.
        if (o.amount_total !== p.usd_cents || String(o.currency).toLowerCase() !== "usd") return "amount_mismatch";
        await env.DB.batch([
          env.DB.prepare("INSERT OR IGNORE INTO credit_ledger (account_id, delta, reason, ref, created_at) VALUES (?1, ?2, 'purchase', ?3, ?4)").bind(accountId, p.minutes, "cs:" + o.id, t),
          env.DB.prepare("INSERT OR IGNORE INTO payments (id, account_id, kind, description, amount_cents, currency, status, created_at) VALUES (?1, ?2, 'credits', ?3, ?4, ?5, 'paid', ?6)").bind(o.payment_intent || o.id, accountId, p.name, o.amount_total, o.currency, t),
        ]);
      } else {
        await env.DB.prepare("INSERT INTO subscriptions (account_id, stripe_subscription_id, plan, status, updated_at) VALUES (?1, ?2, ?3, 'incomplete', ?4) ON CONFLICT (account_id) DO UPDATE SET stripe_subscription_id = ?2, plan = ?3, updated_at = ?4")
          .bind(accountId, o.subscription, p.plan, t).run();
      }
      return "ok";
    }
    case "invoice.paid": {
      const accountId = await accountFor(o.subscription_details?.metadata || o.parent?.subscription_details?.metadata, o.customer);
      if (!accountId) return "ignored";
      const end = o.lines?.data?.[0]?.period?.end;
      await env.DB.batch([
        env.DB.prepare("UPDATE subscriptions SET status = 'active', current_period_end = ?2, updated_at = ?3 WHERE account_id = ?1").bind(accountId, end ? new Date(end * 1000).toISOString() : null, t),
        env.DB.prepare("INSERT OR IGNORE INTO payments (id, account_id, kind, description, amount_cents, currency, status, created_at) VALUES (?1, ?2, 'subscription', 'VEENA Unlimited', ?3, ?4, 'paid', ?5)").bind(o.id, accountId, o.amount_paid, o.currency, t),
      ]);
      return "ok";
    }
    case "invoice.payment_failed": {
      const accountId = await accountFor(null, o.customer);
      if (!accountId) return "ignored";
      await env.DB.batch([
        env.DB.prepare("UPDATE subscriptions SET status = 'past_due', updated_at = ?2 WHERE account_id = ?1").bind(accountId, t),
        env.DB.prepare("INSERT OR IGNORE INTO payments (id, account_id, kind, description, amount_cents, currency, status, created_at) VALUES (?1, ?2, 'subscription', 'VEENA Unlimited (payment failed)', ?3, ?4, 'failed', ?5)").bind(o.id, accountId, o.amount_due, o.currency, t),
      ]);
      return "ok";
    }
    case "customer.subscription.updated":
    case "customer.subscription.deleted": {
      const accountId = await accountFor(o.metadata, o.customer);
      if (!accountId) return "ignored";
      const status = ev.type.endsWith("deleted") ? "canceled" : o.status === "active" || o.status === "trialing" ? "active" : o.status === "past_due" ? "past_due" : o.status === "canceled" ? "canceled" : "incomplete";
      await env.DB.prepare("UPDATE subscriptions SET status = ?2, cancel_at_period_end = ?3, current_period_end = COALESCE(?4, current_period_end), updated_at = ?5 WHERE account_id = ?1")
        .bind(accountId, status, o.cancel_at_period_end ? 1 : 0, o.current_period_end ? new Date(o.current_period_end * 1000).toISOString() : null, t).run();
      return "ok";
    }
    case "charge.refunded": {
      const accountId = await accountFor(o.metadata, o.customer);
      if (!accountId) return "ignored";
      // Credit purchase refunded: remove the refunded share of its minutes (balance may go to zero, never below via usage).
      const pay = await env.DB.prepare("SELECT * FROM payments WHERE id = ?1 OR id = ?2").bind(o.payment_intent || "", o.invoice || "").first();
      const p = pay && Object.values(PRICES).find((x) => x.name === pay.description);
      const stmts = [env.DB.prepare("INSERT OR IGNORE INTO payments (id, account_id, kind, description, amount_cents, currency, status, created_at) VALUES (?1, ?2, 'refund', 'Refund', ?3, ?4, 'refunded', ?5)").bind("re:" + o.id, accountId, -o.amount_refunded, o.currency, t)];
      // A fully refunded subscription payment ends Unlimited immediately.
      if (pay?.kind === "subscription" && o.amount_refunded >= o.amount)
        stmts.push(env.DB.prepare("UPDATE subscriptions SET status = 'refunded', updated_at = ?2 WHERE account_id = ?1").bind(accountId, t));
      if (p?.kind === "credits") stmts.push(env.DB.prepare("INSERT OR IGNORE INTO credit_ledger (account_id, delta, reason, ref, created_at) VALUES (?1, ?2, 'refund', ?3, ?4)")
        .bind(accountId, -Math.round(p.minutes * o.amount_refunded / o.amount), "refund:" + o.id, t));
      await env.DB.batch(stmts);
      return "ok";
    }
    default: return "ignored";
  }
}

export async function history(env, s) {
  const pays = (await env.DB.prepare("SELECT id, kind, description, amount_cents, currency, status, created_at FROM payments WHERE account_id = ?1 ORDER BY created_at DESC LIMIT 100").bind(s.account_id).all()).results;
  const ledger = (await env.DB.prepare("SELECT delta, reason, created_at FROM credit_ledger WHERE account_id = ?1 ORDER BY id DESC LIMIT 200").bind(s.account_id).all()).results;
  return { payments: pays, ledger };
}

export async function expireReservations(env, now = new Date()) {
  await env.DB.prepare("DELETE FROM sessions WHERE expires_at < ?1").bind(nowIso(now)).run();
  await env.DB.prepare("DELETE FROM email_codes WHERE expires_at < ?1").bind(nowIso(now)).run();
  const cutoff = nowIso(new Date(now.getTime() - RESERVE_TTL_MIN * 60000));
  return (await env.DB.prepare("UPDATE operations SET status = 'released', updated_at = ?2 WHERE status = 'reserved' AND created_at < ?1").bind(cutoff, nowIso(now)).run()).meta.changes;
}

// ---------------- email (provider-independent) ----------------
// EMAIL_PROVIDER = "resend" (RESEND_API_KEY secret, EMAIL_FROM var) | unset (sign-in disabled).
// Add a provider by returning another async (to, subject, text) function here. Only the address and
// the code are sent; no other user data.
export function makeMailer(env) {
  if (env.EMAIL_PROVIDER === "resend") {
    if (!env.RESEND_API_KEY || !env.EMAIL_FROM) return async () => { throw new HttpError(503, "email provider is not configured"); };
    return async (to, subject, text) => {
      const r = await env.fetch("https://api.resend.com/emails", { method: "POST",
        headers: { authorization: "Bearer " + env.RESEND_API_KEY, "content-type": "application/json" },
        body: JSON.stringify({ from: env.EMAIL_FROM, to: [to], subject, text }) });
      if (!r.ok) throw new HttpError(502, "could not send the email, try again later");
    };
  }
  return async () => { throw new HttpError(503, "email sending is not configured yet"); };
}

export default {
  async fetch(request, env) {
    env.fetch = env.fetch || fetch.bind(globalThis);
    env.sendEmail = env.sendEmail || makeMailer(env);
    const url = new URL(request.url), p = url.pathname, m = request.method;
    try {
      if (m === "GET" && p === "/v1/prices") return json({ currency: "usd", prices: PRICES, trial_uses: TRIAL_USES, trial_features: FEATURES, credit_features: SESSION_FEATURES });
      if (m === "POST" && p === "/v1/auth/start") return json(await authStart(env, await body(request)));
      if (m === "POST" && p === "/v1/auth/verify") return json(await authVerify(env, await body(request)));
      if (m === "POST" && p === "/v1/stripe/webhook") {
        const payload = await request.text();
        if (!(await verifyStripe(payload, request.headers.get("stripe-signature"), env.STRIPE_WEBHOOK_SECRET || "")))
          return json({ error: "bad signature" }, 400);
        return json({ result: await handleEvent(env, JSON.parse(payload)) });
      }
      const s = await session(env, request);
      if (m === "GET" && p === "/v1/me") return json(await entitlements(env, s));
      if (m === "POST" && p === "/v1/auth/logout") {
        const tok = (request.headers.get("authorization") || "").replace(/^Bearer\s+/i, "");
        await env.DB.prepare("DELETE FROM sessions WHERE token_hash = ?1").bind(await sha256(tok)).run();
        return json({ signed_out: true });
      }
      if (m === "POST" && p === "/v1/usage/authorize") return json(await authorize(env, s, await body(request)));
      if (m === "POST" && p === "/v1/usage/commit") return json(await commit(env, s, await body(request)));
      if (m === "POST" && p === "/v1/usage/release") return json(await release(env, s, await body(request)));
      if (m === "POST" && p === "/v1/checkout") return json(await checkout(env, s, await body(request)));
      if (m === "POST" && p === "/v1/portal") return json(await portal(env, s));
      if (m === "GET" && p === "/v1/history") return json(await history(env, s));
      if (m === "POST" && p === "/v1/appeal") {
        const b = await body(request);
        await env.DB.prepare("INSERT INTO appeals (account_id, reason, created_at) VALUES (?1, ?2, ?3)").bind(s.account_id, String(b.reason || "").slice(0, 2000), nowIso()).run();
        return json({ received: true });
      }
      return json({ error: "not found" }, 404);
    } catch (e) {
      if (e instanceof HttpError) return json({ error: e.message }, e.status);
      return json({ error: "server error" }, 500);
    }
  },
  async scheduled(event, env, ctx) { ctx.waitUntil(expireReservations(env)); },
};
