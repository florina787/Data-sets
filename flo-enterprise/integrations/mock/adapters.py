"""Mock adapters over the synthetic store. Every adapter is tenant-scoped at construction time."""
from __future__ import annotations

import time
from datetime import date

from integrations.base import (CRM, ERP, AdapterInfo, AdvisorAnalytics, DataWarehouse, DocumentRepository, EventBus,
                               MarketData, PortfolioAccounting, PortfolioSystem)
from integrations.mock.store import SyntheticStore

MOCK = dict(mode="mock-synthetic", connected_to_production=False)


class _Base:
    def __init__(self, store: SyntheticStore, tenant_id: str):
        self.st, self.tenant = store, tenant_id

    def describe(self) -> dict:
        return self.info.__dict__  # type: ignore[attr-defined]


class MockPortfolioSystem(_Base, PortfolioSystem):
    info = AdapterInfo("Synthetic Portfolio Management System", "portfolio_management", **MOCK,
                       data_classification="confidential", freshness="month-end", auth="scoped service identity (mock)")

    def portfolios(self) -> list[dict]:
        return [p for p in self.st.tables["portfolios"] if p["tenant_id"] == self.tenant]

    def portfolio(self, portfolio_id: str) -> dict | None:
        p = self.st.idx["portfolio"].get(portfolio_id)
        return p if p and p["tenant_id"] == self.tenant else None

    def holdings(self, portfolio_id: str) -> list[dict]:
        return self.st.idx["portfolio_holdings_by"].get(portfolio_id, []) if self.portfolio(portfolio_id) else []

    def valuations(self, portfolio_id: str) -> list[dict]:
        return self.st.idx["portfolio_monthly_by"].get(portfolio_id, []) if self.portfolio(portfolio_id) else []

    def transactions(self, portfolio_id: str) -> list[dict]:
        return self.st.idx["transactions_by"].get(portfolio_id, []) if self.portfolio(portfolio_id) else []


class MockPortfolioAccounting(_Base, PortfolioAccounting):
    info = AdapterInfo("Synthetic Fund Accounting & Valuation", "portfolio_accounting", **MOCK,
                       data_classification="internal", freshness="month-end", auth="scoped service identity (mock)")

    def products(self) -> list[dict]:
        return [p for p in self.st.tables["products"] if p["tenant_id"] == self.tenant]

    def product_monthly(self) -> list[dict]:
        ids = {p["id"] for p in self.products()}
        return [r for r in self.st.tables["product_monthly"] if r["product_id"] in ids]

    def product_holdings(self, product_id: str) -> list[dict]:
        p = self.st.idx["product"].get(product_id)
        return self.st.idx["product_holdings_by"].get(product_id, []) if p and p["tenant_id"] == self.tenant else []


class MockCRM(_Base, CRM):
    info = AdapterInfo("Synthetic CRM / Advisor Relationship Management", "crm", **MOCK,
                       data_classification="restricted", freshness="near-real-time (simulated)",
                       auth="scoped service identity (mock)")

    def clients(self, advisor_id: str | None = None) -> list[dict]:
        return [c for c in self.st.tables["clients"]
                if c["tenant_id"] == self.tenant and (advisor_id is None or c["advisor_id"] == advisor_id)]

    def client(self, client_id: str) -> dict | None:
        c = self.st.idx["client"].get(client_id)
        return c if c and c["tenant_id"] == self.tenant else None

    def goals(self, client_id: str) -> list[dict]:
        return self.st.idx["client_goals_by"].get(client_id, []) if self.client(client_id) else []

    def interactions(self, client_id: str | None = None) -> list[dict]:
        if client_id is None:
            return [i for i in self.st.tables["service_interactions"] if i["tenant_id"] == self.tenant]
        return self.st.idx["service_interactions_by"].get(client_id, []) if self.client(client_id) else []

    def positions(self, client_id: str) -> list[dict]:
        return self.st.idx["client_positions_by"].get(client_id, []) if self.client(client_id) else []

    def advisors(self) -> list[dict]:
        return [a for a in self.st.tables["advisors"] if a["tenant_id"] == self.tenant]

    def portfolios_for(self, client_id: str) -> list[dict]:
        return [p for p in self.st.tables["portfolios"] if p["client_id"] == client_id and p["tenant_id"] == self.tenant]


class MockERP(_Base, ERP):
    info = AdapterInfo("Synthetic Financial ERP / General Ledger", "erp", **MOCK, data_classification="confidential",
                       freshness="monthly close", auth="scoped service identity (mock)")

    def finance_monthly(self) -> list[dict]:
        return list(self.st.tables["finance_monthly"]) if self.tenant == "t-flo" else []


class MarketDataUnavailable(RuntimeError):
    pass


class MockMarketData(_Base, MarketData):
    """Supports fault injection (FAULTS) so failure handling, retries and circuit breakers can be demonstrated."""
    info = AdapterInfo("Synthetic Market Data Provider", "market_data", **MOCK, data_classification="licensed-internal",
                       freshness="month-end", auth="API key from secret manager (mock)")
    FAULTS: dict[str, float | str] = {"mode": "none", "latency_s": 0.0}

    def _check(self) -> None:
        mode = self.FAULTS.get("mode")
        if self.FAULTS.get("latency_s"):
            time.sleep(float(self.FAULTS["latency_s"]))
        if mode == "down":
            raise MarketDataUnavailable("synthetic market data provider unavailable (fault injection)")

    def securities(self) -> list[dict]:
        self._check()
        return self.st.tables["securities"]

    def security_returns(self) -> dict[str, list[float]]:
        self._check()
        return self.st.idx["sec_ret"]

    def benchmarks(self) -> list[dict]:
        return self.st.tables["benchmarks"]

    def benchmark_returns(self, benchmark_id: str) -> list[float]:
        self._check()
        return self.st.idx["bm_ret"][benchmark_id]

    def months(self) -> list[date]:
        return self.st.idx["months"]


class MockAdvisorAnalytics(_Base, AdvisorAnalytics):
    info = AdapterInfo("Synthetic Advisor Analytics", "advisor_analytics", **MOCK, data_classification="confidential",
                       freshness="daily (simulated)", auth="scoped service identity (mock)")

    def book_summary(self, advisor_id: str) -> dict:
        crm = MockCRM(self.st, self.tenant)
        clients = [c for c in crm.clients(advisor_id) if c["status"] == "active"]
        aum = 0
        for c in clients:
            aum += sum(p["market_value_cents"] for p in crm.positions(c["id"]))
            for pf in crm.portfolios_for(c["id"]):
                v = self.st.idx["portfolio_monthly_by"][pf["id"]]
                aum += v[-1]["mv_close_cents"]
        return {"advisor_id": advisor_id, "active_clients": len(clients), "book_aum_cents": aum}


class MockDocumentRepository(_Base, DocumentRepository):
    info = AdapterInfo("Synthetic Document Management", "document_management", **MOCK,
                       data_classification="mixed (per-document)", freshness="on ingest", auth="scoped service identity (mock)")

    def list_documents(self) -> list[dict]:
        from backend.db import models as m
        from backend.db.session import session_scope
        from sqlalchemy import select
        with session_scope() as s:
            return [dict(id=d.id, title=d.title, classification=d.classification, tenant_id=d.tenant_id)
                    for d in s.scalars(select(m.Document).where(m.Document.tenant_id == self.tenant))]


class MockDataWarehouse(_Base, DataWarehouse):
    info = AdapterInfo("Synthetic Enterprise Lakehouse", "data_warehouse", **MOCK, data_classification="mixed",
                       freshness="T+1 (simulated)", auth="scoped service identity (mock)")
    TENANT_SCOPED = {"clients", "portfolios", "transactions", "service_interactions", "compliance_events", "decisions",
                     "initiatives", "advisors", "products"}
    FIRM_TABLES = {"finance_monthly", "risk_register", "controls", "securities", "benchmarks"}

    def table(self, name: str) -> list[dict]:
        if name in self.TENANT_SCOPED:
            return [r for r in self.st.tables[name] if r.get("tenant_id") == self.tenant]
        if name in self.FIRM_TABLES:
            return self.st.tables[name] if self.tenant == "t-flo" else []
        raise KeyError(f"table {name} is not exposed by the warehouse adapter")


class InMemoryEventBus(EventBus):
    info = AdapterInfo("In-memory event bus (Kafka/EventBridge/Service Bus stand-in)", "event_messaging", **MOCK,
                       data_classification="internal", freshness="real-time", auth="n/a (in-process)")
    _events: list[dict] = []

    def publish(self, topic: str, event: dict) -> None:
        self._events.append({"topic": topic, **event})
        del self._events[:-5000]

    def events(self, topic: str | None = None) -> list[dict]:
        return [e for e in self._events if topic is None or e["topic"] == topic]


class Adapters:
    """Per-request adapter bundle bound to one tenant."""

    def __init__(self, store: SyntheticStore, tenant_id: str):
        self.tenant_id = tenant_id
        self.portfolio = MockPortfolioSystem(store, tenant_id)
        self.accounting = MockPortfolioAccounting(store, tenant_id)
        self.crm = MockCRM(store, tenant_id)
        self.erp = MockERP(store, tenant_id)
        self.market = MockMarketData(store, tenant_id)
        self.advisor_analytics = MockAdvisorAnalytics(store, tenant_id)
        self.documents = MockDocumentRepository(store, tenant_id)
        self.warehouse = MockDataWarehouse(store, tenant_id)
        self.events = InMemoryEventBus()
        self.store = store

    def catalog(self) -> list[dict]:
        return [a.describe() for a in (self.portfolio, self.accounting, self.crm, self.erp, self.market,
                                       self.advisor_analytics, self.documents, self.warehouse, self.events)]
