-- Feedback table (added for the public beta).
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
