-- VEENA Billing (Cloudflare D1 / SQLite). Test mode until the owner approves live payments.
-- Stores no card data (Stripe holds it) and no user content (only feature names and minutes).

CREATE TABLE IF NOT EXISTS accounts (
  id                 TEXT PRIMARY KEY,          -- random UUID
  email              TEXT NOT NULL UNIQUE,      -- lower-cased, verified by a one-time code
  verified_at        TEXT,
  stripe_customer_id TEXT UNIQUE,
  trial_blocked      INTEGER NOT NULL DEFAULT 0, -- set by the repeat-registration rule (appealable)
  created_at         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS email_codes (
  email      TEXT PRIMARY KEY,
  code_hash  TEXT NOT NULL,                     -- SHA-256(pepper + code); the code itself is never stored
  expires_at TEXT NOT NULL,
  attempts   INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY,                  -- SHA-256 of the bearer token
  account_id TEXT NOT NULL,
  install_id TEXT NOT NULL,
  expires_at TEXT NOT NULL
);

-- Random installation ids (created by the app; no hardware data) and which accounts used them.
CREATE TABLE IF NOT EXISTS account_installs (
  account_id TEXT NOT NULL,
  install_id TEXT NOT NULL,
  linked_at  TEXT NOT NULL,
  PRIMARY KEY (account_id, install_id)
);

-- Free trial: successful uses per feature, counted for BOTH the account and the installation.
-- Remaining = 3 - max(account uses, installation uses), so a new email on a known installation
-- does not reset the trial, and a reinstall does not reset it for a known account.
CREATE TABLE IF NOT EXISTS trial_usage (
  subject TEXT NOT NULL,                        -- 'a:<account_id>' or 'i:<install_id>'
  feature TEXT NOT NULL,
  used    INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (subject, feature)
);

-- Operations: authorise before running, commit only after success, release on failure.
CREATE TABLE IF NOT EXISTS operations (
  op_id      TEXT PRIMARY KEY,                  -- UUID from the app; makes retries idempotent
  account_id TEXT NOT NULL,
  install_id TEXT NOT NULL,
  feature    TEXT NOT NULL,
  kind       TEXT NOT NULL,                     -- trial | credits | unlimited
  minutes    INTEGER NOT NULL DEFAULT 0,        -- reserved minutes (credits)
  status     TEXT NOT NULL,                     -- reserved | committed | released
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

-- Credits: append-only ledger in minutes. Balance = SUM(delta). `ref` is unique, so the same
-- Stripe payment or the same operation can never be counted twice.
CREATE TABLE IF NOT EXISTS credit_ledger (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  account_id TEXT NOT NULL,
  delta      INTEGER NOT NULL,                  -- minutes: + purchase, - usage, - refund reversal
  reason     TEXT NOT NULL,                     -- purchase | usage | refund | adjustment
  ref        TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ledger_account ON credit_ledger (account_id);

CREATE TABLE IF NOT EXISTS subscriptions (
  account_id             TEXT PRIMARY KEY,
  stripe_subscription_id TEXT UNIQUE,
  plan                   TEXT NOT NULL,         -- monthly | annual
  status                 TEXT NOT NULL,         -- active | past_due | canceled | incomplete
  current_period_end     TEXT,
  cancel_at_period_end   INTEGER NOT NULL DEFAULT 0,
  updated_at             TEXT NOT NULL
);

-- Billing history shown to the customer (amounts in cents, USD).
CREATE TABLE IF NOT EXISTS payments (
  id            TEXT PRIMARY KEY,               -- Stripe object id (checkout session, invoice or refund)
  account_id    TEXT NOT NULL,
  kind          TEXT NOT NULL,                  -- credits | subscription | refund
  description   TEXT NOT NULL,
  amount_cents  INTEGER NOT NULL,
  currency      TEXT NOT NULL,
  status        TEXT NOT NULL,                  -- paid | failed | refunded
  created_at    TEXT NOT NULL
);

-- Webhook idempotency: every Stripe event id is processed at most once.
CREATE TABLE IF NOT EXISTS stripe_events (
  id          TEXT PRIMARY KEY,
  type        TEXT NOT NULL,
  received_at TEXT NOT NULL
);

-- Abuse prevention counters (code requests per email/installation per day).
CREATE TABLE IF NOT EXISTS rate (
  key   TEXT NOT NULL,
  day   TEXT NOT NULL,
  n     INTEGER NOT NULL,
  PRIMARY KEY (key, day)
);

-- Appeals ("my trial was blocked by mistake", account recovery).
CREATE TABLE IF NOT EXISTS appeals (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  account_id TEXT NOT NULL,
  reason     TEXT NOT NULL,                     -- free text written by the user for the owner to read
  status     TEXT NOT NULL DEFAULT 'open',
  created_at TEXT NOT NULL
);
