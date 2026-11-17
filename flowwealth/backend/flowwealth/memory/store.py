"""Prediction Memory: append-only, hash-chained forecast ledger.

* A prediction can only be recorded while its outcome is still unknown
  (``now < target_time``) and only from inputs that existed (``input_cutoff <= now``).
* Rows can never be updated or deleted: SQLite triggers abort any attempt, and
  each row's hash chains to the previous one so tampering with the file is
  detectable by ``verify_chain``.
* Outcomes live in a separate table, written once, only after ``target_time``.

SQLite keeps this free and local; the schema maps 1:1 onto PostgreSQL
(see ARCHITECTURE_TARGET.md) where the same triggers become rules + REVOKE UPDATE.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Callable

from flowwealth.contracts import PredictionIn, utcnow

SCHEMA = """
CREATE TABLE IF NOT EXISTS predictions (
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  prediction_id TEXT UNIQUE NOT NULL,
  created_at TEXT NOT NULL,
  model_version TEXT NOT NULL,
  strategy_id TEXT NOT NULL,
  ticker TEXT NOT NULL,
  horizon TEXT NOT NULL,
  target_time TEXT NOT NULL,
  payload TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  prev_hash TEXT NOT NULL,
  chain_hash TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_pred_target ON predictions(target_time);
CREATE INDEX IF NOT EXISTS ix_pred_model ON predictions(model_version);
CREATE TRIGGER IF NOT EXISTS predictions_no_update BEFORE UPDATE ON predictions
BEGIN SELECT RAISE(ABORT, 'predictions are immutable'); END;
CREATE TRIGGER IF NOT EXISTS predictions_no_delete BEFORE DELETE ON predictions
BEGIN SELECT RAISE(ABORT, 'predictions are immutable'); END;

CREATE TABLE IF NOT EXISTS outcomes (
  prediction_id TEXT PRIMARY KEY REFERENCES predictions(prediction_id),
  evaluated_at TEXT NOT NULL,
  actual_return REAL,
  benchmark_return REAL,
  direction_correct INTEGER,
  abs_error REAL,
  max_drawdown REAL,
  outcome_source TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS outcomes_no_update BEFORE UPDATE ON outcomes
BEGIN SELECT RAISE(ABORT, 'outcomes are immutable'); END;
CREATE TRIGGER IF NOT EXISTS outcomes_no_delete BEFORE DELETE ON outcomes
BEGIN SELECT RAISE(ABORT, 'outcomes are immutable'); END;
"""

GENESIS = "0" * 64


class RecordingError(ValueError):
    pass


class PredictionMemory:
    def __init__(self, path: str | Path = ":memory:", clock: Callable[[], datetime] = utcnow):
        self.db = sqlite3.connect(str(path), isolation_level=None, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        self.clock = clock

    # ---- write path -------------------------------------------------
    def record(self, p: PredictionIn) -> str:
        now = self.clock()
        if p.input_cutoff > now:
            raise RecordingError("input_cutoff is in the future: inputs cannot postdate the forecast")
        if p.target_time <= now:
            raise RecordingError("target_time has passed: forecasts must be recorded before the outcome is knowable")
        pid = str(uuid.uuid4())
        payload = p.model_dump(mode="json")
        body = json.dumps(payload, sort_keys=True)
        psha = hashlib.sha256(body.encode()).hexdigest()
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self.db.execute("SELECT chain_hash FROM predictions ORDER BY seq DESC LIMIT 1").fetchone()
            prev = row[0] if row else GENESIS
            chain = hashlib.sha256(f"{prev}|{pid}|{now.isoformat()}|{psha}".encode()).hexdigest()
            self.db.execute(
                "INSERT INTO predictions (prediction_id, created_at, model_version, strategy_id, ticker, horizon,"
                " target_time, payload, payload_sha256, prev_hash, chain_hash) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (pid, now.isoformat(), p.model_version, p.strategy_id, p.ticker, p.horizon.value,
                 p.target_time.isoformat(), body, psha, prev, chain))
            self.db.execute("COMMIT")
        except Exception:
            self.db.execute("ROLLBACK")
            raise
        return pid

    def resolve_due(self, price_lookup: Callable[[str, datetime, datetime], dict | None], source: str) -> int:
        """Score every prediction whose target_time has passed and has no outcome yet.

        ``price_lookup(ticker, start, end)`` returns {"return", "benchmark_return", "max_drawdown"}
        using data *available* by now, or None if the outcome is not yet observable.
        """
        now = self.clock()
        due = self.db.execute(
            "SELECT p.* FROM predictions p LEFT JOIN outcomes o USING(prediction_id)"
            " WHERE o.prediction_id IS NULL AND p.target_time <= ?", (now.isoformat(),)).fetchall()
        n = 0
        for r in due:
            payload = json.loads(r["payload"])
            res = price_lookup(r["ticker"], datetime.fromisoformat(payload["input_cutoff"]),
                               datetime.fromisoformat(r["target_time"]))
            if res is None:
                continue
            actual = res["return"]
            fr = payload.get("forecast_return")
            pu = payload.get("prob_up")
            pred_dir = (fr if fr is not None else (pu - 0.5 if pu is not None else None))
            correct = None if pred_dir is None or actual == 0 else int((pred_dir > 0) == (actual > 0))
            self.db.execute("INSERT INTO outcomes VALUES (?,?,?,?,?,?,?,?)", (
                r["prediction_id"], now.isoformat(), actual, res.get("benchmark_return"), correct,
                abs(fr - actual) if fr is not None else None, res.get("max_drawdown"), source))
            n += 1
        return n

    # ---- read path --------------------------------------------------
    def get(self, prediction_id: str) -> dict:
        r = self.db.execute("SELECT * FROM predictions WHERE prediction_id=?", (prediction_id,)).fetchone()
        return {**dict(r), "payload": json.loads(r["payload"])} if r else {}

    def joined(self, model_version: str | None = None) -> list[dict]:
        q = ("SELECT p.prediction_id, p.created_at, p.model_version, p.ticker, p.horizon, p.target_time, p.payload,"
             " o.evaluated_at, o.actual_return, o.benchmark_return, o.direction_correct, o.abs_error"
             " FROM predictions p LEFT JOIN outcomes o USING(prediction_id)")
        args: tuple = ()
        if model_version:
            q += " WHERE p.model_version=?"
            args = (model_version,)
        out = []
        for r in self.db.execute(q + " ORDER BY p.seq", args):
            d = dict(r)
            d["payload"] = json.loads(d["payload"])
            out.append(d)
        return out

    def verify_chain(self) -> tuple[bool, int | None]:
        prev = GENESIS
        for r in self.db.execute("SELECT * FROM predictions ORDER BY seq"):
            psha = hashlib.sha256(r["payload"].encode()).hexdigest()
            expect = hashlib.sha256(f"{prev}|{r['prediction_id']}|{r['created_at']}|{psha}".encode()).hexdigest()
            if psha != r["payload_sha256"] or r["prev_hash"] != prev or r["chain_hash"] != expect:
                return False, r["seq"]
            prev = r["chain_hash"]
        return True, None
