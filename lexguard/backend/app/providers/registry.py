"""Provider registry + gateway. The gateway, not the provider, enforces permissions."""

from __future__ import annotations

from app.providers.base import BaseLegalAIProvider, ProviderNotIntegrated, ProviderNotPermitted
from app.providers.harvey_adapter import HarveyAdapter
from app.providers.mock import MockLegalAIProvider

_IMPLEMENTATIONS: dict[str, type[BaseLegalAIProvider]] = {
    "P-MOCK-LEGAL-AI": MockLegalAIProvider,
    "P-HARVEY": HarveyAdapter,
}


class ProviderGateway:
    def __init__(self, matterguard_result, audit_fn) -> None:
        self.mg = matterguard_result
        self.audit = audit_fn
        self.invocations: list[dict] = []

    def invoke(self, provider_id: str, operation: str, *args, **kwargs) -> dict:
        if self.mg is None or self.mg.provider_id != provider_id or not self.mg.provider_permitted:
            self.audit("PROVIDER_BLOCKED", {"provider_id": provider_id, "operation": operation}, "WARNING")
            raise ProviderNotPermitted(f"Provider {provider_id} is not permitted for this request by MatterGuard.")
        if "external_provider_call" not in self.mg.allowed_tools:
            self.audit("PROVIDER_BLOCKED", {"provider_id": provider_id, "operation": operation, "reason": "tool blocked"}, "WARNING")
            raise ProviderNotPermitted("external_provider_call is not an allowed tool for this request.")
        impl = _IMPLEMENTATIONS.get(provider_id)
        if impl is None:
            raise ProviderNotIntegrated(f"No implementation registered for {provider_id}.")
        result = getattr(impl(), operation)(*args, **kwargs)
        self.invocations.append({"provider_id": provider_id, "operation": operation})
        self.audit("PROVIDER_INVOKED", {"provider_id": provider_id, "operation": operation,
                                        "simulated": result.get("simulated", False)}, "INFO")
        return result
