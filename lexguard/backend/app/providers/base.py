"""Provider-neutral interface for legal-AI execution providers.

LexGuard treats external legal-AI platforms as governed execution providers. Providers are only ever
invoked through `ProviderGateway`, after MatterGuard has approved the provider for the request.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class ProviderNotIntegrated(RuntimeError):
    pass


class ProviderNotPermitted(PermissionError):
    pass


class BaseLegalAIProvider(ABC):
    provider_id: str
    external: bool

    @abstractmethod
    def analyze_documents(self, documents: list[dict], instructions: str) -> dict: ...

    @abstractmethod
    def research(self, question: str, context: list[dict]) -> dict: ...

    @abstractmethod
    def draft(self, draft_type: str, context: list[dict]) -> dict: ...

    @abstractmethod
    def compare(self, a: dict, b: dict) -> dict: ...

    @abstractmethod
    def summarize(self, document: dict) -> dict: ...
