// VEENA Insights — Cloudflare Worker + D1 (free tier). No dependencies, no build step.
//
// Routes
//   POST /v1/events    desktop app, opted-in installations only (strict allow-list schema)
//   POST /v1/delete    desktop app, when the user withdraws consent: deletes that installation's rows
//   POST /v1/web       website: aggregate page-view / download-click counters (no identifier at all)
//   GET  /health       liveness + database schema check (no data, no secrets)
//   GET  /dashboard    the private founder dashboard (HTML; data needs the token)
//   GET  /api/summary  dashboard data            Authorization: Bearer <DASHBOARD_TOKEN>
//   POST /api/delete   owner deletion by install id (support requests)   same auth
//   scheduled          daily: retention purge + GitHub release download snapshot
//
// Never stored: IP address, user agent, cookies, prompts, documents, screenshots, audio,
// transcripts, file names, error messages. Only allow-listed enums, a version string and a UTC day.

import DASHBOARD_HTML from "./dashboard.html";

export const EVENTS = ["first_launch", "ai_first_success", "active", "feature", "error"];
export const FEATURES = ["chat", "documents", "screen", "meeting", "interview", "agents"];
export const ERROR_CODES = ["backend_start", "runtime_download", "model_download", "model_error", "asr_error", "screen_capture", "crash", "other"];
export const OS = ["windows", "macos", "linux"];
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const VERSION = /^\d{1,3}\.\d{1,3}\.\d{1,4}(-[a-z0-9.]{1,20})?$/;
const DAY = /^\d{4}-\d{2}-\d{2}$/;
const LABEL = /^[a-z0-9._-]{1,40}$/;
const PAGES = ["/", "/index.html", "/features.html", "/feedback.html", "/privacy.html"];
const MAX_BODY = 8192, MAX_EVENTS = 50, MAX_PER_HOUR = 300;

const json = (data, status = 200, extra = {}) =>
  new Response(JSON.stringify(data), { status, headers: { "content-type": "application/json", "cache-control": "no-store", ...extra } });
const today = (now = new Date()) => now.toISOString().slice(0, 10);
const addDays = (day, n) => new Date(Date.parse(day + "T00:00:00Z") + n * 86400000).toISOString().slice(0, 10);

async function readJson(request) {
  const len = Number(request.headers.get("content-length") || 0);
  if (len > MAX_BODY) throw new HttpError(413, "body too large");
  const text = await request.text();
  if (text.length > MAX_BODY) throw new HttpError(413, "body too large");
  try { return JSON.parse(text); } catch { throw new HttpError(400, "invalid JSON"); }
}
class HttpError extends Error { constructor(status, msg) { super(msg); this.status = status; } }

/** Validates a desktop batch. Unknown keys anywhere are rejected, so nothing extra can ever be stored. */
export function validateBatch(body, now = new Date()) {
  const allowed = new Set(["install_id", "os", "app_version", "test", "events"]);
  if (typeof body !== "object" || body === null || Array.isArray(body)) throw new HttpError(400, "object expected");
  for (const k of Object.keys(body)) if (!allowed.has(k)) throw new HttpError(400, `unknown field ${k}`);
  if (!UUID.test(body.install_id || "")) throw new HttpError(400, "install_id must be a random UUID v4");
  if (!OS.includes(body.os)) throw new HttpError(400, "bad os");
  if (!VERSION.test(body.app_version || "")) throw new HttpError(400, "bad app_version");
  if (!Array.isArray(body.events) || body.events.length === 0 || body.events.length > MAX_EVENTS) throw new HttpError(400, "1-50 events");
  const lo = addDays(today(now), -7), hi = addDays(today(now), 1);
  const events = body.events.map((e) => {
    if (typeof e !== "object" || e === null) throw new HttpError(400, "bad event");
    for (const k of Object.keys(e)) if (!["event", "feature", "error_code", "day"].includes(k)) throw new HttpError(400, `unknown event field ${k}`);
    if (!EVENTS.includes(e.event)) throw new HttpError(400, "bad event name");
    if (!DAY.test(e.day || "") || e.day < lo || e.day > hi) throw new HttpError(400, "day out of range");
    const feature = e.event === "feature" ? e.feature : null;
    const error_code = e.event === "error" ? e.error_code : null;
    if (e.event === "feature" && !FEATURES.includes(feature)) throw new HttpError(400, "bad feature");
    if (e.event === "error" && !ERROR_CODES.includes(error_code)) throw new HttpError(400, "bad error code");
    if (e.event !== "feature" && e.feature !== undefined) throw new HttpError(400, "feature only on feature events");
    if (e.event !== "error" && e.error_code !== undefined) throw new HttpError(400, "error_code only on error events");
    return { event: e.event, feature, error_code, day: e.day };
  });
  return { install_id: body.install_id, os: body.os, app_version: body.app_version, is_test: body.test === true ? 1 : 0, events };
}

export const FEEDBACK_FEATURES = ["chat", "documents", "screen", "meeting", "interview", "agents", "setup", "other"];
const text = (v, max) => (typeof v === "string" ? v.replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f]/g, "").trim().slice(0, max) : "");

/** Feedback form. Spam protection: hidden honeypot, minimum fill time, strict fields. */
export function validateFeedback(b) {
  const allowed = new Set(["kind", "rating", "feature", "worked", "didnt", "next", "email", "contact_ok", "app_version", "os", "test", "website", "elapsed_ms"]);
  if (typeof b !== "object" || b === null) throw new HttpError(400, "object expected");
  for (const k of Object.keys(b)) if (!allowed.has(k)) throw new HttpError(400, `unknown field ${k}`);
  if (b.website) throw new HttpError(400, "rejected");                       // honeypot: people never see this field
  if (!(Number(b.elapsed_ms) >= 3000)) throw new HttpError(400, "too fast");  // bots submit instantly
  const kind = b.kind === "bug" ? "bug" : "feedback";
  const rating = kind === "feedback" ? Number(b.rating) : null;
  if (kind === "feedback" && !(Number.isInteger(rating) && rating >= 1 && rating <= 5)) throw new HttpError(400, "rating must be 1-5");
  if (!FEEDBACK_FEATURES.includes(b.feature)) throw new HttpError(400, "bad feature");
  const worked = text(b.worked, 1500), didnt = text(b.didnt, 1500), next = text(b.next, 1500);
  if (!worked && !didnt && !next) throw new HttpError(400, "write at least one answer");
  const email = text(b.email, 254).toLowerCase();
  if (email && !/^[^\s@]{1,64}@[^\s@]{1,190}\.[a-z]{2,24}$/.test(email)) throw new HttpError(400, "check the email address");
  const os = OS.includes(b.os) ? b.os : "", app_version = VERSION.test(b.app_version || "") ? b.app_version : "";
  return { kind, rating, feature: b.feature, worked, didnt, next, email: email || null, contact_ok: email && b.contact_ok === true ? 1 : 0, os, app_version, is_test: b.test === true ? 1 : 0 };
}

export async function saveFeedback(env, f, clientKey, now = new Date()) {
  // Rate limits without storing addresses: a daily-salted hash of the client, purged after 2 days.
  const k = "fb:" + (await sha256((env.RATE_SALT || "") + today(now) + clientKey)).slice(0, 32);
  for (const [key, limit] of [[k, 5], ["fb:all", 500]]) {
    const r = await env.DB.prepare("INSERT INTO rate (install_id, hour, n) VALUES (?1, ?2, 1) ON CONFLICT (install_id, hour) DO UPDATE SET n = n + 1 RETURNING n").bind(key, today(now)).first();
    if (r.n > limit) throw new HttpError(429, "thank you, we have received a lot of feedback today; please try tomorrow");
  }
  await env.DB.prepare("INSERT INTO feedback (day, kind, rating, feature, worked, didnt, next, email, contact_ok, app_version, os, is_test, created_at) VALUES (?1,?2,?3,?4,?5,?6,?7,?8,?9,?10,?11,?12,?13)")
    .bind(today(now), f.kind, f.rating, f.feature, f.worked, f.didnt, f.next, f.email, f.contact_ok, f.app_version, f.os, f.is_test, now.toISOString()).run();
}
async function sha256(s) { return [...new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s)))].map((b) => b.toString(16).padStart(2, "0")).join(""); }

export function validateWeb(body) {
  const allowed = new Set(["kind", "page", "referrer", "campaign", "os", "test"]);
  if (typeof body !== "object" || body === null) throw new HttpError(400, "object expected");
  for (const k of Object.keys(body)) if (!allowed.has(k)) throw new HttpError(400, `unknown field ${k}`);
  if (!["pageview", "download_click"].includes(body.kind)) throw new HttpError(400, "bad kind");
  const page = body.kind === "pageview" ? body.page : "";
  if (body.kind === "pageview" && !PAGES.includes(page)) throw new HttpError(400, "bad page");
  const referrer = body.referrer ? String(body.referrer).toLowerCase() : "";
  if (referrer && !/^[a-z0-9.-]{1,80}$/.test(referrer)) throw new HttpError(400, "referrer must be a host name");
  const campaign = body.campaign ? String(body.campaign) : "";
  if (campaign && !LABEL.test(campaign)) throw new HttpError(400, "bad campaign");
  const os = body.kind === "download_click" ? body.os : "";
  if (body.kind === "download_click" && !OS.includes(os)) throw new HttpError(400, "bad os");
  return { kind: body.kind, page, referrer: referrer.replace(/^www\./, ""), campaign, os, is_test: body.test === true ? 1 : 0 };
}

function cors(request, env) {
  const origin = request.headers.get("origin") || "";
  const allowed = (env.ALLOWED_ORIGINS || "").split(",").map((s) => s.trim()).filter(Boolean);
  return allowed.includes(origin) ? { "access-control-allow-origin": origin, "vary": "origin" } : null;
}

function timingSafeEqual(a, b) {
  const x = new TextEncoder().encode(a), y = new TextEncoder().encode(b);
  let diff = x.length ^ y.length;
  for (let i = 0; i < Math.max(x.length, y.length); i++) diff |= (x[i] || 0) ^ (y[i] || 0);
  return diff === 0;
}
function authorised(request, env) {
  const token = env.DASHBOARD_TOKEN || "";
  if (token.length < 32) return false;                       // refuse to run with a weak or missing token
  const got = (request.headers.get("authorization") || "").replace(/^Bearer\s+/i, "");
  return timingSafeEqual(got, token);
}

export async function ingest(env, batch, now = new Date()) {
  const hour = now.toISOString().slice(0, 13);
  // Rate limit per installation per hour (abuse prevention).
  const row = await env.DB.prepare("INSERT INTO rate (install_id, hour, n) VALUES (?1, ?2, ?3) ON CONFLICT (install_id, hour) DO UPDATE SET n = n + ?3 RETURNING n")
    .bind(batch.install_id, hour, batch.events.length).first();
  if (row && row.n > MAX_PER_HOUR) throw new HttpError(429, "rate limited");
  const received = now.toISOString();
  const stmt = env.DB.prepare("INSERT OR IGNORE INTO events (install_id, event, feature, error_code, os, app_version, day, is_test, received_at) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9)");
  await env.DB.batch(batch.events.map((e) => stmt.bind(batch.install_id, e.event, e.feature, e.error_code, batch.os, batch.app_version, e.day, batch.is_test, received)));
  return batch.events.length;
}

export async function deleteInstall(env, installId, source, now = new Date()) {
  if (!UUID.test(installId || "")) throw new HttpError(400, "install_id must be a UUID v4");
  const res = await env.DB.prepare("DELETE FROM events WHERE install_id = ?1").bind(installId).run();
  await env.DB.prepare("DELETE FROM rate WHERE install_id = ?1").bind(installId).run();
  const rows = res.meta?.changes ?? 0;
  await env.DB.prepare("INSERT INTO deletions (day, source, rows) VALUES (?1, ?2, ?3)").bind(today(now), source, rows).run();
  return rows;
}

export async function countWeb(env, w, now = new Date()) {
  await env.DB.prepare("INSERT INTO web_daily (day, kind, page, referrer, campaign, os, is_test, count) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, 1) ON CONFLICT DO UPDATE SET count = count + 1")
    .bind(today(now), w.kind, w.page, w.referrer, w.campaign, w.os, w.is_test).run();
}

/** Retention purge + GitHub download snapshot. Runs daily from the cron trigger. */
export async function daily(env, now = new Date(), fetchImpl = fetch) {
  const keep = Number(env.RETENTION_DAYS || 395), keepWeb = Number(env.WEB_RETENTION_DAYS || 395);
  const cutoff = addDays(today(now), -keep), cutoffWeb = addDays(today(now), -keepWeb);
  const ev = await env.DB.prepare("DELETE FROM events WHERE day < ?1").bind(cutoff).run();
  const web = await env.DB.prepare("DELETE FROM web_daily WHERE day < ?1").bind(cutoffWeb).run();
  // Feedback text kept 2 years; contact addresses removed after 1 year.
  await env.DB.prepare("DELETE FROM feedback WHERE day < ?1").bind(addDays(today(now), -730)).run();
  await env.DB.prepare("UPDATE feedback SET email = NULL, contact_ok = 0 WHERE day < ?1 AND email IS NOT NULL").bind(addDays(today(now), -365)).run();
  await env.DB.prepare("DELETE FROM rate WHERE hour < ?1").bind(addDays(today(now), -2)).run();
  const purged = (ev.meta?.changes ?? 0) + (web.meta?.changes ?? 0);
  if (purged) await env.DB.prepare("INSERT INTO deletions (day, source, rows) VALUES (?1, 'retention', ?2)").bind(today(now), purged).run();
  let snapshot = 0;
  try {
    const res = await fetchImpl(`https://api.github.com/repos/${env.GITHUB_REPO || "florina787/Data-sets"}/releases?per_page=30`,
      { headers: { accept: "application/vnd.github+json", "user-agent": "veena-insights" } });
    if (res.ok) {
      const ext = { ".exe": "windows", ".dmg": "macos", ".AppImage": "linux" };
      const stmt = env.DB.prepare("INSERT OR REPLACE INTO release_downloads (day, release, os, file, downloads, is_test) VALUES (?1, ?2, ?3, ?4, ?5, 0)");
      const rows = [];
      for (const rel of await res.json()) {
        if (rel.draft || !/^veena-ai-v/.test(rel.tag_name || "")) continue;
        for (const a of rel.assets || []) {
          const os = Object.entries(ext).find(([e]) => a.name.endsWith(e))?.[1];
          if (os) rows.push(stmt.bind(today(now), rel.tag_name, os, a.name, a.download_count));
        }
      }
      if (rows.length) await env.DB.batch(rows);
      snapshot = rows.length;
    }
  } catch { /* GitHub unreachable: try again tomorrow */ }
  return { purged, snapshot };
}

// ---------- dashboard data ----------
const weekOf = (day) => { const d = new Date(day + "T00:00:00Z"); const dow = (d.getUTCDay() + 6) % 7; return addDays(day, -dow); }; // Monday

export async function summary(env, { days = 90, test = false } = {}, now = new Date()) {
  const T = test ? 1 : 0, end = today(now), start = addDays(end, -(days - 1)), d7 = addDays(end, -6), d30 = addDays(end, -29);
  const all = (sql, ...b) => env.DB.prepare(sql).bind(...b).all().then((r) => r.results);
  const one = (sql, ...b) => env.DB.prepare(sql).bind(...b).first();

  const [pv, clicks, refs, camps, pvDaily, clicksByOs] = await Promise.all([
    one("SELECT COALESCE(SUM(count),0) n FROM web_daily WHERE kind='pageview' AND is_test=?1 AND day>=?2", T, start),
    one("SELECT COALESCE(SUM(count),0) n FROM web_daily WHERE kind='download_click' AND is_test=?1 AND day>=?2", T, start),
    all("SELECT referrer, SUM(count) n FROM web_daily WHERE kind='pageview' AND referrer<>'' AND is_test=?1 AND day>=?2 GROUP BY referrer ORDER BY n DESC LIMIT 8", T, start),
    all("SELECT campaign, SUM(count) n FROM web_daily WHERE campaign<>'' AND is_test=?1 AND day>=?2 GROUP BY campaign ORDER BY n DESC LIMIT 8", T, start),
    all("SELECT day, SUM(CASE WHEN kind='pageview' THEN count ELSE 0 END) pv, SUM(CASE WHEN kind='download_click' THEN count ELSE 0 END) dl FROM web_daily WHERE is_test=?1 AND day>=?2 GROUP BY day ORDER BY day", T, start),
    all("SELECT os, SUM(count) n FROM web_daily WHERE kind='download_click' AND is_test=?1 AND day>=?2 GROUP BY os", T, start),
  ]);
  const gh = await all("SELECT r.release, r.os, r.file, r.downloads FROM release_downloads r JOIN (SELECT file, release, MAX(day) d FROM release_downloads WHERE is_test=?1 GROUP BY file, release) m ON r.file=m.file AND r.release=m.release AND r.day=m.d WHERE r.is_test=?1", T);
  const [dau, newInstalls, returning, ghDaily, fb, fbByFeature, fbNext, fbWeekly] = await Promise.all([
    one("SELECT COUNT(DISTINCT install_id) n FROM events WHERE event='active' AND is_test=?1 AND day=?2", T, end),
    one("SELECT COUNT(*) n FROM events WHERE event='first_launch' AND is_test=?1 AND day>=?2", T, d7),
    one("SELECT COUNT(DISTINCT a.install_id) n FROM events a WHERE a.event='active' AND a.is_test=?1 AND a.day>=?2 AND EXISTS (SELECT 1 FROM events f WHERE f.install_id=a.install_id AND f.event='first_launch' AND f.day<?2)", T, d7),
    all("SELECT day, SUM(downloads) n FROM release_downloads WHERE is_test=?1 AND day>=?2 GROUP BY day ORDER BY day", T, start),
    one("SELECT COUNT(*) total, AVG(rating) avg_rating, SUM(kind='bug') bugs, SUM(email IS NOT NULL AND contact_ok=1) contactable FROM feedback WHERE is_test=?1 AND day>=?2", T, start),
    all("SELECT feature, COUNT(*) n, AVG(rating) avg_rating FROM feedback WHERE is_test=?1 AND day>=?2 GROUP BY feature ORDER BY n DESC", T, start),
    all("SELECT next, day FROM feedback WHERE is_test=?1 AND day>=?2 AND next<>'' ORDER BY id DESC LIMIT 12", T, start),
    all("SELECT day, COUNT(*) n, AVG(rating) avg_rating FROM feedback WHERE is_test=?1 AND day>=?2 GROUP BY day ORDER BY day", T, start),
  ]);
  const [launches, firstAi, wau, mau, byOs, versions, featureUse, errors] = await Promise.all([
    one("SELECT COUNT(*) n FROM events WHERE event='first_launch' AND is_test=?1 AND day>=?2", T, start),
    one("SELECT COUNT(*) n FROM events WHERE event='ai_first_success' AND is_test=?1 AND day>=?2", T, start),
    one("SELECT COUNT(DISTINCT install_id) n FROM events WHERE event='active' AND is_test=?1 AND day>=?2", T, d7),
    one("SELECT COUNT(DISTINCT install_id) n FROM events WHERE event='active' AND is_test=?1 AND day>=?2", T, d30),
    all("SELECT os, COUNT(*) n FROM events WHERE event='first_launch' AND is_test=?1 AND day>=?2 GROUP BY os", T, start),
    all("SELECT app_version, COUNT(DISTINCT install_id) n FROM events WHERE event='active' AND is_test=?1 AND day>=?2 GROUP BY app_version ORDER BY n DESC", T, d30),
    all("SELECT feature, COUNT(DISTINCT install_id) n FROM events WHERE event='feature' AND is_test=?1 AND day>=?2 GROUP BY feature", T, d30),
    all("SELECT error_code, COUNT(*) n, COUNT(DISTINCT install_id) installs FROM events WHERE event='error' AND is_test=?1 AND day>=?2 GROUP BY error_code ORDER BY n DESC", T, d30),
  ]);
  // Weekly active installations and cohort retention (computed in the Worker from compact rows).
  const actives = await all("SELECT install_id, day FROM events WHERE event='active' AND is_test=?1 AND day>=?2", T, addDays(end, -7 * 16));
  const firsts = await all("SELECT install_id, day FROM events WHERE event='first_launch' AND is_test=?1 AND day>=?2", T, addDays(end, -7 * 12));
  const weeks = [];
  for (let i = 11; i >= 0; i--) weeks.push(weekOf(addDays(end, -7 * i)));
  const activeWeeks = new Map();
  for (const a of actives) { const w = weekOf(a.day); if (!activeWeeks.has(a.install_id)) activeWeeks.set(a.install_id, new Set()); activeWeeks.get(a.install_id).add(w); }
  const wauSeries = weeks.map((w) => ({ week: w, installs: [...activeWeeks.values()].filter((s) => s.has(w)).length }));
  const cohorts = new Map();
  for (const f of firsts) { const w = weekOf(f.day); if (!cohorts.has(w)) cohorts.set(w, []); cohorts.get(w).push(f.install_id); }
  const currentWeek = weekOf(end);
  const retention = [...cohorts.entries()].sort(([a], [b]) => a.localeCompare(b)).slice(-8).map(([w, ids]) => ({
    week: w, size: ids.length,
    weeks: [1, 2, 3, 4].map((k) => { const target = addDays(w, 7 * k); if (target > currentWeek) return null;
      return Math.round(100 * ids.filter((id) => activeWeeks.get(id)?.has(target)).length / ids.length); }),
  }));
  const ghTotal = gh.reduce((s, r) => s + r.downloads, 0);
  return {
    generated_at: now.toISOString(), window_days: days, test_data: test,
    definitions: {
      page_views: "Website page loads. No identifier is kept, so this is not a count of people.",
      download_clicks: "Clicks on a website download button.",
      github_downloads: "GitHub's own counter of completed installer downloads, all time. Includes repeat downloads; not people, not installs.",
      installations: "Installations that opted in to anonymous statistics. Each has a random id created on opt-in; one person can have several, and declined installs are never counted.",
      active: "Opted-in installations that opened VEENA in the period.",
    },
    web: { page_views: pv.n, download_clicks: clicks.n, referrers: refs, campaigns: camps, daily: pvDaily, clicks_by_os: clicksByOs },
    downloads: { total: ghTotal, files: gh },
    feedback: { total: fb.total, avg_rating: fb.avg_rating === null ? null : Math.round(fb.avg_rating * 10) / 10, bugs: fb.bugs || 0,
      contactable: fb.contactable || 0, anonymous: fb.total - (fb.contactable || 0), by_feature: fbByFeature, requests: fbNext, daily: fbWeekly },
    downloads_daily: ghDaily,
    installs: { active_1d: dau.n, new_7d: newInstalls.n, returning_7d: returning.n, first_launches: launches.n, first_ai_success: firstAi.n, active_7d: wau.n, active_30d: mau.n, by_os: byOs, versions },
    funnel: [
      { step: "Page views", n: pv.n, note: "website, not people" },
      { step: "Download clicks", n: clicks.n, note: "website" },
      { step: "GitHub downloads", n: ghTotal, note: "all time, includes repeats" },
      { step: "First launches", n: launches.n, note: "opted-in installs only" },
      { step: "First AI answer", n: firstAi.n, note: "opted-in installs only" },
      { step: "Active last 7 days", n: wau.n, note: "opted-in installs only" },
    ],
    features: FEATURES.map((f) => ({ feature: f, installs: featureUse.find((r) => r.feature === f)?.n || 0, pct: mau.n ? Math.round(100 * (featureUse.find((r) => r.feature === f)?.n || 0) / mau.n) : 0 })),
    errors, weekly_active: wauSeries, retention,
  };
}

export const TABLES = ["deletions", "events", "feedback", "rate", "release_downloads", "web_daily"];
export async function health(env) {
  const rows = (await env.DB.prepare("SELECT name FROM sqlite_master WHERE type='table'").all()).results.map((r) => r.name);
  const missing = TABLES.filter((t) => !rows.includes(t));
  return { ok: missing.length === 0, service: "veena-insights", schema: missing.length ? "missing: " + missing.join(",") : "ok",
    dashboard_token: (env.DASHBOARD_TOKEN || "").length >= 32 ? "set" : "missing", rate_salt: env.RATE_SALT ? "set" : "missing" };
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    try {
      if (request.method === "GET" && url.pathname === "/health") {
        const h = await health(env);
        return json(h, h.ok ? 200 : 503);
      }
      if (request.method === "OPTIONS" && url.pathname === "/v1/web") {
        const c = cors(request, env);
        return new Response(null, { status: c ? 204 : 403, headers: { ...(c || {}), "access-control-allow-methods": "POST", "access-control-allow-headers": "content-type", "access-control-max-age": "86400" } });
      }
      if (request.method === "POST" && url.pathname === "/v1/events") {
        const n = await ingest(env, validateBatch(await readJson(request)));
        return json({ accepted: n });
      }
      if (request.method === "POST" && url.pathname === "/v1/delete") {
        const body = await readJson(request);
        return json({ deleted: await deleteInstall(env, body.install_id, "app_withdrawal") });
      }
      if (request.method === "POST" && url.pathname === "/v1/web") {
        const c = cors(request, env);
        if (!c) return json({ error: "origin not allowed" }, 403);
        await countWeb(env, validateWeb(await readJson(request)));
        return new Response(null, { status: 204, headers: c });
      }
      if (request.method === "OPTIONS" && url.pathname === "/v1/feedback") {
        const c = cors(request, env);
        return new Response(null, { status: c ? 204 : 403, headers: { ...(c || {}), "access-control-allow-methods": "POST", "access-control-allow-headers": "content-type", "access-control-max-age": "86400" } });
      }
      if (request.method === "POST" && url.pathname === "/v1/feedback") {
        const c = cors(request, env);
        if (!c) return json({ error: "origin not allowed" }, 403);
        const client = request.headers.get("cf-connecting-ip") || "unknown";
        await saveFeedback(env, validateFeedback(await readJson(request)), client);
        return json({ received: true }, 200, c);
      }
      if (request.method === "GET" && url.pathname === "/dashboard") {
        return new Response(DASHBOARD_HTML, { headers: { "content-type": "text/html; charset=utf-8", "cache-control": "no-store",
          "content-security-policy": "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; connect-src 'self'; frame-ancestors 'none'",
          "x-robots-tag": "noindex", "referrer-policy": "no-referrer" } });
      }
      if (url.pathname.startsWith("/api/")) {
        if (!authorised(request, env)) return json({ error: "unauthorised" }, 401);
        if (request.method === "GET" && url.pathname === "/api/summary")
          return json(await summary(env, { days: Math.min(365, Math.max(7, Number(url.searchParams.get("days")) || 90)), test: url.searchParams.get("test") === "1" }));
        if (request.method === "POST" && url.pathname === "/api/delete") {
          const body = await readJson(request);
          return json({ deleted: await deleteInstall(env, body.install_id, "owner_request") });
        }
      }
      return json({ error: "not found" }, 404);
    } catch (e) {
      if (e instanceof HttpError) return json({ error: e.message }, e.status);
      return json({ error: "server error" }, 500);
    }
  },
  async scheduled(event, env, ctx) { ctx.waitUntil(daily(env)); },
};
