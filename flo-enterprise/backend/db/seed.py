"""Apply migrations and load the deterministic synthetic dataset (idempotent).

Usage: python -m backend.db.seed [--reset]
"""
from __future__ import annotations

import argparse
import logging
import time

from alembic import command
from alembic.config import Config
from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from backend.config import ROOT, get_settings
from backend.db import models as m
from backend.db.session import session_scope
from data.synthetic.generator import generate, manifest

log = logging.getLogger("flo.seed")

# insertion order respects foreign keys
TABLES: list[tuple[str, type[m.Base]]] = [
    ("tenants", m.Tenant), ("users", m.User), ("advisors", m.Advisor), ("clients", m.Client),
    ("client_goals", m.ClientGoal), ("securities", m.Security), ("security_returns", m.SecurityReturn),
    ("benchmarks", m.Benchmark), ("benchmark_returns", m.BenchmarkReturn), ("products", m.Product),
    ("product_holdings", m.ProductHolding), ("product_monthly", m.ProductMonthly), ("finance_monthly", m.FinanceMonthly),
    ("portfolios", m.Portfolio), ("portfolio_holdings", m.PortfolioHolding), ("portfolio_monthly", m.PortfolioMonthly),
    ("client_positions", m.ClientPosition), ("transactions", m.Transaction),
    ("service_interactions", m.ServiceInteraction), ("controls", m.Control), ("compliance_events", m.ComplianceEvent),
    ("risk_register", m.RiskRegisterItem), ("initiatives", m.Initiative), ("decisions", m.Decision),
    ("agent_traces", m.AgentTrace),
]


def migrate(url: str | None = None) -> None:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "backend" / "db" / "migrations"))
    cfg.attributes["url"] = url or get_settings().database_url
    command.upgrade(cfg, "head")


def is_seeded(s: Session) -> bool:
    return s.get(m.SeedManifest, "dataset") is not None


def load(s: Session) -> dict:
    data = generate()
    man = manifest(data)
    for name, model in TABLES:
        rows = data[name]
        for i in range(0, len(rows), 2000):
            s.execute(insert(model), rows[i:i + 2000])
    s.add(m.SeedManifest(key="dataset", value=man))
    return man


def reset(s: Session) -> None:
    for model in [m.ConversationMessage, m.Conversation, m.DocChunk, m.Document, m.Outbox, m.Job, m.VaultEntry, m.Approval, m.AuditEvent, m.SeedManifest]:
        s.execute(delete(model))
    for _, model in reversed(TABLES):
        s.execute(delete(model))


def reconcile_users(s: Session) -> int:
    """Add synthetic identities introduced after a database was seeded (e.g. the prospect persona); never modifies existing rows."""
    have = set(s.scalars(select(m.User.id)))
    new = [u for u in generate()["users"] if u["id"] not in have]
    if new:
        s.execute(insert(m.User), new)
    return len(new)


def seed(force_reset: bool = False, with_documents: bool = True) -> dict:
    migrate()
    t0 = time.time()
    with session_scope() as s:
        if force_reset:
            reset(s)
        if is_seeded(s):
            man = s.get(m.SeedManifest, "dataset").value
            added = reconcile_users(s)
            log.info("dataset already seeded%s", f"; added {added} new synthetic user(s)" if added else "")
        else:
            man = load(s)
    if with_documents:
        from retrieval.ingest import ingest_corpus
        with session_scope() as s:
            if s.scalar(select(m.Document.id).limit(1)) is None:
                ingest_corpus(s)
    log.info("seed complete in %.1fs", time.time() - t0)

    return man


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    p = argparse.ArgumentParser()
    p.add_argument("--reset", action="store_true")
    p.add_argument("--no-documents", action="store_true")
    a = p.parse_args()
    out = seed(a.reset, not a.no_documents)
    print({k: v["rows"] for k, v in out["tables"].items()})
