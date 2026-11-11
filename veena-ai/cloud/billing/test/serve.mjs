// Serves the REAL billing Worker locally on SQLite for end-to-end tests of the desktop app
// (tests/test_billing_e2e.py). Test-only extras under /__test: read the last emailed code, run
// signed webhooks through the Stripe simulator, expire reservations. Never deployed.
//   node cloud/billing/test/serve.mjs <port>
import http from "node:http";
import crypto from "node:crypto";
import { DatabaseSync } from "node:sqlite";
import fs from "node:fs";
import path from "node:path";
import * as B from "../src/worker.js";

const root = path.resolve(import.meta.dirname, "..");
const db = new DatabaseSync(":memory:");
db.exec(fs.readFileSync(path.join(root, "schema.sql"), "utf8"));
const norm = (sql) => sql.replace(/\?(\d+)/g, "?");
const expand = (sql, a) => { const o = [...sql.matchAll(/\?(\d+)/g)].map((m) => Number(m[1]) - 1); return o.length ? o.map((i) => a[i]) : a; };
const prep = (sql) => { const st = { args: [], bind(...a) { return { ...st, args: a }; },
  async all() { return { results: db.prepare(norm(sql)).all(...expand(sql, this.args)) }; },
  async first() { return db.prepare(norm(sql)).get(...expand(sql, this.args)) ?? null; },
  async run() { const r = db.prepare(norm(sql)).run(...expand(sql, this.args)); return { meta: { changes: Number(r.changes) } }; } }; return st; };
const mail = [];
const env = { DB: { prepare: prep, async batch(l) { db.exec("BEGIN"); try { for (const s of l) await s.run(); db.exec("COMMIT"); } catch (e) { db.exec("ROLLBACK"); throw e; } } },
  CODE_PEPPER: "test-pepper-0123456789abcdef", STRIPE_SECRET_KEY: "sk_test_simulator", STRIPE_WEBHOOK_SECRET: "whsec_sim", SITE_URL: "https://example.invalid",
  sendEmail: async (to, s, text) => mail.push({ to, code: text.match(/\d{6}/)[0] }),
  fetch: async () => new Response(JSON.stringify({ id: "cs_test_sim", url: "https://checkout.stripe.com/c/pay/cs_test_sim" })) };

http.createServer(async (req, res) => {
  const chunks = []; for await (const c of req) chunks.push(c);
  const body = Buffer.concat(chunks).toString();
  const url = new URL(req.url, "http://x");
  if (url.pathname === "/__test/code") { res.end(JSON.stringify(mail.at(-1) || null)); return; }
  if (url.pathname === "/__test/webhook") {
    const t = Math.floor(Date.now() / 1000), sig = crypto.createHmac("sha256", env.STRIPE_WEBHOOK_SECRET).update(`${t}.${body}`).digest("hex");
    const r = await B.default.fetch(new Request("http://x/v1/stripe/webhook", { method: "POST", body, headers: { "stripe-signature": `t=${t},v1=${sig}` } }), env);
    res.end(await r.text()); return;
  }
  if (url.pathname === "/__test/accounts") { res.end(JSON.stringify(db.prepare("SELECT id, email FROM accounts").all())); return; }
  const r = await B.default.fetch(new Request("http://x" + req.url, { method: req.method, headers: req.headers, body: ["GET", "HEAD"].includes(req.method) ? undefined : body }), env);
  res.writeHead(r.status, { "content-type": "application/json" }); res.end(await r.text());
}).listen(Number(process.argv[2]), "127.0.0.1", () => console.log("ready"));
