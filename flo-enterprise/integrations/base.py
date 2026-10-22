"""Provider-neutral integration interfaces.

Each enterprise system category is an interface. FLO ships ONLY mock adapters backed by synthetic data
(`mode = "mock-synthetic"`, `connected_to_production = False`). A real adapter would implement the same
interface with a scoped service identity, short-lived credentials from a secret manager, request validation,
rate limiting and audit logging (see docs/INTEGRATIONS.md). Nothing here is connected to any production system.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class AdapterInfo:
    system: str
    category: str
    mode: str
    connected_to_production: bool
    data_classification: str
    freshness: str
    auth: str


class Adapter(ABC):
    info: AdapterInfo

    def describe(self) -> dict:
        return self.info.__dict__


class PortfolioSystem(Adapter):
    @abstractmethod
    def portfolios(self) -> list[dict]: ...
    @abstractmethod
    def portfolio(self, portfolio_id: str) -> dict | None: ...
    @abstractmethod
    def holdings(self, portfolio_id: str) -> list[dict]: ...
    @abstractmethod
    def valuations(self, portfolio_id: str) -> list[dict]: ...


class PortfolioAccounting(Adapter):
    @abstractmethod
    def products(self) -> list[dict]: ...
    @abstractmethod
    def product_monthly(self) -> list[dict]: ...
    @abstractmethod
    def product_holdings(self, product_id: str) -> list[dict]: ...


class CRM(Adapter):
    @abstractmethod
    def clients(self, advisor_id: str | None = None) -> list[dict]: ...
    @abstractmethod
    def client(self, client_id: str) -> dict | None: ...
    @abstractmethod
    def goals(self, client_id: str) -> list[dict]: ...
    @abstractmethod
    def interactions(self, client_id: str | None = None) -> list[dict]: ...
    @abstractmethod
    def positions(self, client_id: str) -> list[dict]: ...
    @abstractmethod
    def advisors(self) -> list[dict]: ...


class ERP(Adapter):
    @abstractmethod
    def finance_monthly(self) -> list[dict]: ...


class MarketData(Adapter):
    @abstractmethod
    def securities(self) -> list[dict]: ...
    @abstractmethod
    def security_returns(self) -> dict[str, list[float]]: ...
    @abstractmethod
    def benchmarks(self) -> list[dict]: ...
    @abstractmethod
    def benchmark_returns(self, benchmark_id: str) -> list[float]: ...
    @abstractmethod
    def months(self) -> list[date]: ...


class AdvisorAnalytics(Adapter):
    @abstractmethod
    def book_summary(self, advisor_id: str) -> dict: ...


class DocumentRepository(Adapter):
    @abstractmethod
    def list_documents(self) -> list[dict]: ...


class DataWarehouse(Adapter):
    @abstractmethod
    def table(self, name: str) -> list[dict]: ...


class EventBus(Adapter):
    @abstractmethod
    def publish(self, topic: str, event: dict) -> None: ...
    @abstractmethod
    def events(self, topic: str | None = None) -> list[dict]: ...
