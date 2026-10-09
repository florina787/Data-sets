"""HarveyAdapter - INTERFACE ONLY. Not integrated.

No Harvey API is implemented or assumed here. An actual integration depends on available enterprise APIs,
supported integrations, authentication, permissions and contractual configuration agreed with the vendor.
Every method raises ProviderNotIntegrated. See docs/HARVEY_INTEGRATION.md.
"""

from __future__ import annotations

from app.providers.base import BaseLegalAIProvider, ProviderNotIntegrated

_MSG = ("HarveyAdapter is an interface placeholder. No verified Harvey integration is implemented; "
        "see docs/HARVEY_INTEGRATION.md.")


class HarveyAdapter(BaseLegalAIProvider):
    provider_id = "P-HARVEY"
    external = True

    def analyze_documents(self, documents, instructions):
        raise ProviderNotIntegrated(_MSG)

    def research(self, question, context):
        raise ProviderNotIntegrated(_MSG)

    def draft(self, draft_type, context):
        raise ProviderNotIntegrated(_MSG)

    def compare(self, a, b):
        raise ProviderNotIntegrated(_MSG)

    def summarize(self, document):
        raise ProviderNotIntegrated(_MSG)
