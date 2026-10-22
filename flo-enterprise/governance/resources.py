"""Resolve resource references to policy Resources using authoritative (tenant-unfiltered) data, so that policy - not a
missing lookup - produces the decision. Unknown ids resolve to a sentinel tenant and are denied exactly like
cross-tenant ids (no existence oracle)."""
from __future__ import annotations

from governance.policy import Resource
from integrations.mock.store import SyntheticStore

UNKNOWN_TENANT = "__unknown__"


def client(store: SyntheticStore, client_id: str) -> Resource:
    c = store.idx["client"].get(client_id)
    if c is None:
        return Resource("client", client_id, UNKNOWN_TENANT, {})
    return Resource("client", client_id, c["tenant_id"], {"advisor_id": c["advisor_id"], "classification": "confidential",
                                                          "business_unit": c["business_unit"]})


def portfolio(store: SyntheticStore, portfolio_id: str) -> Resource:
    p = store.idx["portfolio"].get(portfolio_id)
    if p is None:
        return Resource("portfolio", portfolio_id, UNKNOWN_TENANT, {})
    c = store.idx["client"][p["client_id"]]
    return Resource("portfolio", portfolio_id, p["tenant_id"], {"advisor_id": c["advisor_id"], "client_id": c["id"],
                                                                "classification": "confidential", "business_unit": "private_wealth"})


def from_ref(store: SyntheticStore, tenant_id: str, ref: str) -> Resource | None:
    kind, _, rid = ref.partition(":")
    if kind == "client":
        return client(store, rid)
    if kind == "portfolio":
        return portfolio(store, rid)
    if kind in ("board_report", "export", "ledger", "firm"):
        return Resource(kind, rid, tenant_id, {"classification": "confidential"})
    return Resource(kind, rid, UNKNOWN_TENANT, {})
