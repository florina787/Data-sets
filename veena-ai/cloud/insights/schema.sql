-- VEENA Insights: privacy-first product analytics (Cloudflare D1 / SQLite).
-- No IP addresses, user agents, prompts, documents, audio, transcripts or file names are ever stored.
-- `is_test` = 1 marks synthetic data from the test harness; the dashboard hides it unless asked.

-- Desktop events from installations that OPTED IN. install_id is a random UUID created on opt-in
-- and deleted on withdrawal: it identifies an installation, not a person.
CREATE TABLE IF NOT EXISTS events (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  install_id  TEXT    NOT NULL,
  event       TEXT    NOT NULL,          -- first_launch | ai_first_success | active | feature | error
  feature     TEXT,                      -- chat | documents | screen | meeting | interview | agents (event = feature)
  error_code  TEXT,                      -- short allow-listed code (event = error), never a message
  os          TEXT    NOT NULL,          -- windows | macos | linux
  app_version TEXT    NOT NULL,
  day         TEXT    NOT NULL,          -- UTC date YYYY-MM-DD (no time of day is kept)
  is_test     INTEGER NOT NULL DEFAULT 0,
  received_at TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS events_install ON events (install_id);
CREATE INDEX IF NOT EXISTS events_day ON events (day, event);
-- One first_launch / ai_first_success per installation; one active/feature row per installation per day.
CREATE UNIQUE INDEX IF NOT EXISTS events_dedup ON events (install_id, event, IFNULL(feature, ''), IFNULL(error_code, ''), day)
  WHERE event IN ('first_launch', 'ai_first_success', 'active', 'feature');

-- Website: aggregate counters only. No identifier of any kind, so these are page views, not people.
CREATE TABLE IF NOT EXISTS web_daily (
  day      TEXT NOT NULL,
  kind     TEXT NOT NULL,                -- pageview | download_click
  page     TEXT NOT NULL DEFAULT '',     -- /, /features.html, ... (pageview)
  referrer TEXT NOT NULL DEFAULT '',     -- referring host only, e.g. linkedin.com
  campaign TEXT NOT NULL DEFAULT '',     -- utm_campaign label
  os       TEXT NOT NULL DEFAULT '',     -- download_click: windows | macos | linux
  is_test  INTEGER NOT NULL DEFAULT 0,
  count    INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (day, kind, page, referrer, campaign, os, is_test)
);

-- Daily snapshot of GitHub's own per-file download counters (cumulative).
CREATE TABLE IF NOT EXISTS release_downloads (
  day       TEXT NOT NULL,
  release   TEXT NOT NULL,
  os        TEXT NOT NULL,
  file      TEXT NOT NULL,
  downloads INTEGER NOT NULL,
  is_test   INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (day, release, file, is_test)
);

-- Abuse prevention: events accepted per installation per hour (rows older than 2 days are purged).
CREATE TABLE IF NOT EXISTS rate (
  install_id TEXT NOT NULL,
  hour       TEXT NOT NULL,
  n          INTEGER NOT NULL,
  PRIMARY KEY (install_id, hour)
);

-- Deletion log: proves a deletion request was carried out, without keeping the deleted id.
CREATE TABLE IF NOT EXISTS deletions (
  day     TEXT NOT NULL,
  source  TEXT NOT NULL,                 -- app_withdrawal | owner_request | retention
  rows    INTEGER NOT NULL
);

-- Feedback from the website form (no sign-in). Free text is what the person chose to write; nothing
-- is collected automatically. The address is stored only if given, and only for follow-up.
CREATE TABLE IF NOT EXISTS feedback (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  day         TEXT    NOT NULL,
  kind        TEXT    NOT NULL,              -- feedback | bug
  rating      INTEGER,                       -- 1..5 (feedback)
  feature     TEXT    NOT NULL,              -- chat | documents | screen | meeting | interview | agents | setup | other
  worked      TEXT    NOT NULL DEFAULT '',
  didnt       TEXT    NOT NULL DEFAULT '',
  next        TEXT    NOT NULL DEFAULT '',
  email       TEXT,                          -- optional, for follow-up
  contact_ok  INTEGER NOT NULL DEFAULT 0,
  app_version TEXT    NOT NULL DEFAULT '',
  os          TEXT    NOT NULL DEFAULT '',
  is_test     INTEGER NOT NULL DEFAULT 0,
  created_at  TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS feedback_day ON feedback (day);
