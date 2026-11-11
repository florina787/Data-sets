// Serves the REAL Insights Worker on SQLite for end-to-end tests of an INSTALLED app (CI).
// Test-only extra: GET /__test/summary returns the dashboard summary. Never deployed.
//   node cloud/insights/test/serve.mjs <port>
import http from "node:http";
import { DatabaseSync } from "node:sqlite";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";

const root = path.resolve(import.meta.dirname, "..");
const html = fs.readFileSync(path.join(root, "src/dashboard.html"), "utf8");
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "veena-insights-"));
fs.writeFileSync(path.join(tmp, "worker.mjs"), fs.readFileSync(path.join(root, "src/worker.js"), "utf8")
  .replace('import DASHBOARD_HTML from "./dashboard.html";', `const DASHBOARD_HTML = ${JSON.stringify(html)};`));
const W = await import(pathToFileURL(path.join(tmp, "worker.mjs")).href);

const db = new DatabaseSync(":memory:");
db.exec(fs.readFileSync(path.join(root, "schema.sql"), "utf8"));
const norm = (s) => s.replace(/\?(\d+)/g, "?");
const expand = (s, a) => { const o = [...s.matchAll(/\?(\d+)/g)].map((m) => Number(m[1]) - 1); return o.length ? o.map((i) => a[i]) : a; };
const prep = (sql) => { const st = { args: [], bind(...a) { return { ...st, args: a }; },
  async all() { return { results: db.prepare(norm(sql)).all(...expand(sql, this.args)) }; },
  async first() { return db.prepare(norm(sql)).get(...expand(sql, this.args)) ?? null; },
  async run() { const r = db.prepare(norm(sql)).run(...expand(sql, this.args)); return { meta: { changes: Number(r.changes) } }; } }; return st; };
const env = { DB: { prepare: prep, async batch(l) { db.exec("BEGIN"); try { for (const s of l) await s.run(); db.exec("COMMIT"); } catch (e) { db.exec("ROLLBACK"); throw e; } } },
  DASHBOARD_TOKEN: "ci-dashboard-token-".padEnd(40, "x"), ALLOWED_ORIGINS: "", RATE_SALT: "ci" };

http.createServer(async (req, res) => {
  const chunks = []; for await (const c of req) chunks.push(c);
  if (req.url.startsWith("/__test/summary")) { res.end(JSON.stringify(await W.summary(env, { days: 7, test: false }))); return; }
  const r = await W.default.fetch(new Request("http://x" + req.url, { method: req.method, headers: req.headers, body: ["GET", "HEAD"].includes(req.method) ? undefined : Buffer.concat(chunks) }), env);
  res.writeHead(r.status, { "content-type": "application/json" }); res.end(await r.text());
}).listen(Number(process.argv[2]), "127.0.0.1", () => console.log("ready"));
