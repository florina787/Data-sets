"""In-memory read model of the synthetic dataset, loaded once from the database and partitioned by tenant.

Data access through this store is always tenant-scoped (defense in depth below the policy engine)."""
from __future__ import annotations

import threading
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from backend.db import models as m


def _rows(s: Session, model) -> list[dict]:
    cols = [c.key for c in inspect(model).mapper.column_attrs]
    return [{c: getattr(o, c) for c in cols} for o in s.scalars(select(model))]


@dataclass
class SyntheticStore:
    version: str
    tables: dict[str, list[dict]] = field(default_factory=dict)
    idx: dict[str, dict] = field(default_factory=dict)

    @classmethod
    def load(cls, s: Session) -> "SyntheticStore":
        man = s.get(m.SeedManifest, "dataset")
        if man is None:
            raise RuntimeError("database is not seeded; run `python -m backend.db.seed`")
        st = cls(version=man.value["tables"]["product_monthly"]["sha256"][:12])
        for name, model in [("tenants", m.Tenant), ("users", m.User), ("advisors", m.Advisor), ("clients", m.Client),
                            ("client_goals", m.ClientGoal), ("securities", m.Security), ("benchmarks", m.Benchmark),
                            ("products", m.Product), ("product_holdings", m.ProductHolding),
                            ("product_monthly", m.ProductMonthly), ("finance_monthly", m.FinanceMonthly),
                            ("portfolios", m.Portfolio), ("portfolio_holdings", m.PortfolioHolding),
                            ("portfolio_monthly", m.PortfolioMonthly), ("client_positions", m.ClientPosition),
                            ("transactions", m.Transaction), ("service_interactions", m.ServiceInteraction),
                            ("controls", m.Control), ("compliance_events", m.ComplianceEvent),
                            ("risk_register", m.RiskRegisterItem), ("initiatives", m.Initiative),
                            ("decisions", m.Decision)]:
            st.tables[name] = _rows(s, model)
        sec_ret: dict[str, list[tuple[date, float]]] = defaultdict(list)
        for r in s.execute(select(m.SecurityReturn.security_id, m.SecurityReturn.month, m.SecurityReturn.ret)):
            sec_ret[r[0]].append((r[1], r[2]))
        bm_ret: dict[str, list[tuple[date, float]]] = defaultdict(list)
        for r in s.execute(select(m.BenchmarkReturn.benchmark_id, m.BenchmarkReturn.month, m.BenchmarkReturn.ret)):
            bm_ret[r[0]].append((r[1], r[2]))
        st.idx["months"] = sorted({d for v in bm_ret.values() for d, _ in v})
        st.idx["sec_ret"] = {k: [x for _, x in sorted(v)] for k, v in sec_ret.items()}
        st.idx["bm_ret"] = {k: [x for _, x in sorted(v)] for k, v in bm_ret.items()}
        st._index()
        return st

    def _index(self) -> None:
        by = lambda rows, key: {r[key]: r for r in rows}  # noqa: E731
        self.idx["client"] = by(self.tables["clients"], "id")
        self.idx["portfolio"] = by(self.tables["portfolios"], "id")
        self.idx["product"] = by(self.tables["products"], "id")
        self.idx["security"] = by(self.tables["securities"], "id")
        self.idx["advisor"] = by(self.tables["advisors"], "id")
        self.idx["user"] = by(self.tables["users"], "id")
        for name, key in [("portfolio_holdings", "portfolio_id"), ("portfolio_monthly", "portfolio_id"),
                          ("client_goals", "client_id"), ("client_positions", "client_id"),
                          ("service_interactions", "client_id"), ("product_holdings", "product_id"),
                          ("transactions", "portfolio_id")]:
            g: dict[str, list[dict]] = defaultdict(list)
            for r in self.tables[name]:
                g[r[key]].append(r)
            self.idx[f"{name}_by"] = g
        for v in self.idx["portfolio_monthly_by"].values():
            v.sort(key=lambda r: r["month"])


_lock = threading.Lock()
_store: SyntheticStore | None = None
_store_key: str | None = None


def get_store(s: Session) -> SyntheticStore:
    global _store, _store_key
    key = str(s.get_bind().url)
    man = s.get(m.SeedManifest, "dataset")
    version = man.value["tables"]["product_monthly"]["sha256"][:12] if man else None
    with _lock:
        if _store is None or _store_key != key or _store.version != version:
            _store = SyntheticStore.load(s)
            _store_key = key
        return _store


def invalidate() -> None:
    global _store
    with _lock:
        _store = None
