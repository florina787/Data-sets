"""Privacy Shield: server-side classification, data minimisation and redaction.

Every record that leaves the server — to the browser, the local LLM, MCP clients, exports,
logs, traces or conversation memory — goes through :func:`apply` (structured rows) or
:func:`scrub` (free text). Enforcement is deterministic code, never the LLM, and never CSS.

Classification levels (lowest → highest): public, internal, confidential, highly_restricted.

* **Tenant isolation (row level):** rows from another tenant are removed before anything else.
* **Column level:** each field has a classification. ``internal`` fields are returned to signed-in
  users of the same tenant; ``confidential`` fields are returned only to roles granted that
  dataset for an allowed *purpose*, otherwise replaced by a band/summary; ``highly_restricted``
  fields (personal data, bank details, secrets) never leave the server — no role, lens or purpose
  unlocks them, including the CTO lens.
* **Purpose:** ``llm``, ``export``, ``mcp``, ``memory`` and ``log`` never receive confidential
  values, even for a granted role (data minimisation).
* Every application is audited with counts only — never values.

The demo fixtures contain deliberately sensitive "canary" values so tests can prove they never
appear in any output (see tests/test_privacy.py).
"""

from __future__ import annotations

import hashlib
import random
import re
from dataclasses import dataclass, field

from app.db import rows, session

LEVELS = ("public", "internal", "confidential", "highly_restricted")
DEFAULT_TENANT = "fbfc"
# Tenant per user. Demo accounts all belong to the fictional company; tests add others.
USER_TENANT: dict[str, str] = {}

CLASSIFICATION: dict[str, dict[str, str]] = {
    "suppliers": {
        "id": "internal",
        "tenant": "internal",
        "name": "internal",
        "country": "internal",
        "category": "internal",
        "on_time_pct": "internal",
        "quality_pass_pct": "internal",
        "open_incidents": "internal",
        "annual_spend_cents": "confidential",
        "contract_terms": "confidential",
        "negotiated_price_cents_per_tonne": "confidential",
        "account_manager_name": "highly_restricted",
        "account_manager_email": "highly_restricted",
        "account_manager_phone": "highly_restricted",
        "bank_account": "highly_restricted",
        "api_key": "highly_restricted",
    },
    "employees": {
        "id": "internal",
        "tenant": "internal",
        "site": "internal",
        "job_title": "internal",
        "full_name": "highly_restricted",
        "email": "highly_restricted",
        "phone": "highly_restricted",
        "salary_cents": "highly_restricted",
        "national_id": "highly_restricted",
    },
}
# Confidential grants: dataset -> roles allowed to see confidential values in the UI.
# None of the five demo roles is a procurement role, so commercial terms stay banded for all of them.
CONFIDENTIAL_GRANTS: dict[str, set[str]] = {"suppliers": {"procurement"}, "employees": set()}
MINIMISED_PURPOSES = {"llm", "export", "mcp", "memory", "log"}
PURPOSES = {"ui", *MINIMISED_PURPOSES}

FIELD_LABEL = {
    "annual_spend_cents": "annual spend",
    "contract_terms": "contract terms",
    "negotiated_price_cents_per_tonne": "negotiated price",
    "account_manager_name": "contact person",
    "account_manager_email": "contact email",
    "account_manager_phone": "contact phone",
    "bank_account": "bank details",
    "api_key": "credentials",
    "full_name": "employee names",
    "email": "email addresses",
    "phone": "phone numbers",
    "salary_cents": "salaries",
    "national_id": "national IDs",
}


@dataclass(frozen=True)
class Principal:
    username: str
    role: str
    tenant: str = DEFAULT_TENANT


def principal_for(user) -> Principal:
    return Principal(user.username, user.role, USER_TENANT.get(user.username, DEFAULT_TENANT))


@dataclass
class PolicyReport:
    dataset: str
    purpose: str
    applied: bool = True
    rows_in: int = 0
    rows_out: int = 0
    other_tenant_rows_removed: int = 0
    excluded_fields: list[str] = field(default_factory=list)
    aggregated_fields: list[str] = field(default_factory=list)
    export_allowed: bool = True

    def as_dict(self) -> dict:
        return {
            "policy_applied": self.applied,
            "dataset": self.dataset,
            "purpose": self.purpose,
            "rows": self.rows_out,
            "excluded": sorted({FIELD_LABEL.get(f, f) for f in self.excluded_fields}),
            "aggregated": sorted({FIELD_LABEL.get(f, f) for f in self.aggregated_fields}),
            "tenant_isolated": True,
            "export_allowed": self.export_allowed,
            "note": "Policy applied on the server before this data reached you, Jerry or any export.",
        }


def _band(cents: int) -> str:
    v = cents / 100
    for lo, hi, label in (
        (0, 250_000, "under CAD 0.25M"),
        (250_000, 1_000_000, "CAD 0.25–1M"),
        (1_000_000, 5_000_000, "CAD 1–5M"),
        (5_000_000, 25_000_000, "CAD 5–25M"),
    ):
        if lo <= v < hi:
            return label
    return "over CAD 25M"


def _summary(field_name: str, value) -> str | None:
    if field_name == "annual_spend_cents" and isinstance(value, int):
        return _band(value)
    if field_name == "negotiated_price_cents_per_tonne":
        return "within the category price band (exact price restricted)"
    if field_name == "contract_terms":
        return "contract on file (terms restricted)"
    return None


def apply(dataset: str, records: list[dict], principal: Principal, purpose: str) -> tuple[list[dict], PolicyReport]:
    """Return records minimised for ``principal`` and ``purpose``, plus a value-free policy report."""
    if purpose not in PURPOSES:
        raise ValueError(f"unknown purpose {purpose}")
    cls = CLASSIFICATION[dataset]
    rep = PolicyReport(dataset, purpose, rows_in=len(records))
    same = [r for r in records if r.get("tenant", DEFAULT_TENANT) == principal.tenant]
    rep.other_tenant_rows_removed = len(records) - len(same)
    granted = principal.role in CONFIDENTIAL_GRANTS.get(dataset, set()) and purpose not in MINIMISED_PURPOSES
    out = []
    for r in same:
        o = {}
        for k, v in r.items():
            level = cls.get(k, "highly_restricted")  # unclassified fields fail closed
            if level in ("public", "internal"):
                o[k] = v
            elif level == "confidential" and granted:
                o[k] = v
            elif level == "confidential":
                s = _summary(k, v)
                if s is not None:
                    o[k] = s
                rep.aggregated_fields.append(k)
            else:
                rep.excluded_fields.append(k)
        o.pop("tenant", None)
        out.append(o)
    rep.rows_out = len(out)
    rep.export_allowed = True  # exports receive the same minimised rows, never more
    _audit(principal, rep)
    return out, rep


def _audit(principal: Principal, rep: PolicyReport) -> None:
    try:
        from app.records import audit

        audit(
            principal.username,
            "privacy.policy_applied",
            outcome="ok",
            entity_type="dataset",
            entity_id=rep.dataset,
            purpose=rep.purpose,
            rows=rep.rows_out,
            other_tenant_rows_removed=rep.other_tenant_rows_removed,
            excluded_fields=len(set(rep.excluded_fields)),
            aggregated_fields=len(set(rep.aggregated_fields)),
        )
    except Exception:  # noqa: BLE001 - auditing must not break minimisation
        pass


# Free-text scrubber for logs, traces, memory and model prompts (defence in depth).
_SECRET_PATTERNS = [
    (re.compile(r"\b(sk|pk|rk)_(live|test)_[A-Za-z0-9]{8,}\b"), "[secret removed]"),
    (re.compile(r"\b(?:api[_-]?key|token|password|secret)\s*[:=]\s*\S+", re.I), "[secret removed]"),
    (re.compile(r"\bBearer\s+[A-Za-z0-9._~+/-]{12,}=*", re.I), "Bearer [token removed]"),
    (re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"), "[email removed]"),
    (re.compile(r"\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){3,7}\b"), "[account removed]"),
    (re.compile(r"\+\d[\d\s().-]{8,}\d(?!\d)"), "[phone removed]"),
]


def scrub(text: str) -> str:
    for rx, repl in _SECRET_PATTERNS:
        text = rx.sub(repl, text)
    return text


def scrub_obj(obj):
    if isinstance(obj, Principal):  # traces record who and which tenant, as plain data
        return {"role": obj.role, "tenant": obj.tenant}
    if isinstance(obj, str):
        return scrub(obj)
    if isinstance(obj, dict):
        return {k: scrub_obj(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [scrub_obj(v) for v in obj]
    return obj


# --- sensitive demo fixtures --------------------------------------------------------------

DDL = """
CREATE TABLE IF NOT EXISTS ent_suppliers (
    id TEXT PRIMARY KEY, tenant TEXT NOT NULL, name TEXT NOT NULL, country TEXT, category TEXT,
    on_time_pct REAL, quality_pass_pct REAL, open_incidents INTEGER, annual_spend_cents INTEGER,
    contract_terms TEXT, negotiated_price_cents_per_tonne INTEGER, account_manager_name TEXT,
    account_manager_email TEXT, account_manager_phone TEXT, bank_account TEXT, api_key TEXT
);
CREATE TABLE IF NOT EXISTS ent_employees (
    id TEXT PRIMARY KEY, tenant TEXT NOT NULL, site TEXT, job_title TEXT, full_name TEXT, email TEXT,
    phone TEXT, salary_cents INTEGER, national_id TEXT
);
"""


def canary(kind: str, i: int) -> str:
    """Deterministic, unmistakable sensitive values. Tests search every output for them."""
    h = hashlib.sha256(f"{kind}-{i}".encode()).hexdigest()[:10].upper()
    return {
        "contract": f"CANARY-CONTRACT-{h}: Net-120, 3-year exclusivity, rebate 4.5%",
        "name": f"Canary Person {h}",
        "email": f"canary.{h.lower()}@supplier.example",
        "phone": f"+1 416 555 {int(h[:4], 16) % 10000:04d}",
        "bank": f"GB82 WEST 1234 5698 7654 {int(h[4:8], 16) % 100:02d}",
        "key": f"sk_live_CANARY{h}",
        "nid": f"CANARY-NID-{h}",
    }[kind]


def seed() -> None:
    """(Re)create the supplier and employee fixtures, linked to the synthetic global network."""
    from app import geo

    net = geo.network()
    rng = random.Random(2026)
    sups = [n for n in net["nodes"] if n["tier"] == "supplier"]
    inc = {}
    for i in net["incidents"]:
        inc[i["node_id"]] = inc.get(i["node_id"], 0) + 1
    with session() as conn:
        conn.executescript(DDL)
        conn.execute("DELETE FROM ent_suppliers")
        conn.execute("DELETE FROM ent_employees")
        for i, s in enumerate(sups):
            conn.execute(
                "INSERT INTO ent_suppliers VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    s["id"],
                    DEFAULT_TENANT,
                    s["name"],
                    s["country_name"],
                    rng.choice(["Potatoes", "Packaging", "Oils"]),
                    s["performance"]["on_time_pct"],
                    s["performance"]["quality_pass_pct"],
                    inc.get(s["id"], 0),
                    rng.randint(20_000_000, 900_000_000),
                    canary("contract", i),
                    rng.randint(18_000, 42_000),
                    canary("name", i),
                    canary("email", i),
                    canary("phone", i),
                    canary("bank", i),
                    canary("key", i),
                ),
            )
        # Another tenant's supplier: must never be visible to this company's users.
        conn.execute(
            "INSERT INTO ent_suppliers VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "OTHER-SUP-01",
                "other-co",
                "CANARY-OTHER-TENANT Supplier",
                "Nowhere",
                "Potatoes",
                50.0,
                50.0,
                9,
                999_000_000,
                canary("contract", 999),
                99_999,
                canary("name", 999),
                canary("email", 999),
                canary("phone", 999),
                canary("bank", 999),
                canary("key", 999),
            ),
        )
        for i, site in enumerate(["Toronto plant", "Montreal DC", "Vancouver DC", "Toronto plant"]):
            conn.execute(
                "INSERT INTO ent_employees VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    f"EMP-{i + 1:03d}",
                    DEFAULT_TENANT,
                    site,
                    ["Line lead", "QA inspector", "Planner", "Shift manager"][i],
                    canary("name", 100 + i),
                    canary("email", 100 + i),
                    canary("phone", 100 + i),
                    rng.randint(6_000_000, 14_000_000),
                    canary("nid", 100 + i),
                ),
            )


def suppliers(principal: Principal, purpose: str) -> tuple[list[dict], PolicyReport]:
    raw = rows("SELECT * FROM ent_suppliers ORDER BY quality_pass_pct, on_time_pct")
    return apply("suppliers", raw, principal, purpose)


def employees_summary(principal: Principal, purpose: str) -> tuple[list[dict], PolicyReport]:
    raw = rows("SELECT * FROM ent_employees")
    recs, rep = apply("employees", raw, principal, purpose)
    by_site: dict[str, int] = {}
    for r in recs:
        by_site[r["site"]] = by_site.get(r["site"], 0) + 1
    rep.aggregated_fields.append("headcount")
    return [{"site": k, "headcount": v} for k, v in sorted(by_site.items())], rep
