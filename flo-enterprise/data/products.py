"""Governed data-product catalog: schema, owner, classification, lineage, quality checks, version, freshness SLA and
access policy for each FLO data product."""
from __future__ import annotations

from sqlalchemy import inspect

from backend.db import models as m

PRODUCTS = [
    {"id": "investment", "name": "Investment Data Product", "owner": "Office of the CIO (synthetic)", "classification": "confidential",
     "entities": [m.Product, m.ProductHolding, m.Portfolio, m.PortfolioHolding, m.PortfolioMonthly, m.Benchmark, m.BenchmarkReturn, m.Security, m.SecurityReturn],
     "lineage": ["Portfolio management system (mock)", "Fund accounting & valuation (mock)", "Market data provider (mock)"],
     "quality_checks": ["DQ-INV-001", "DQ-INV-002", "DQ-INV-003", "DQ-INV-004"], "freshness_sla": "month-end + 5 business days",
     "access_policy": "investment:read / investment:read_aggregate; portfolio:read with ABAC-PORTFOLIO-ACCESS"},
    {"id": "wealth", "name": "Wealth Data Product", "owner": "Head of Private Wealth (synthetic)", "classification": "confidential (client PI: restricted fields)",
     "entities": [m.Client, m.ClientGoal, m.ClientPosition, m.Advisor, m.ServiceInteraction, m.Transaction],
     "lineage": ["CRM (mock)", "Portfolio management system (mock)"], "quality_checks": ["DQ-WLT-001", "DQ-WLT-002", "DQ-WLT-003", "DQ-WLT-004", "DQ-WLT-005"],
     "freshness_sla": "daily (simulated)", "access_policy": "client:read with ABAC-CLIENT-ASSIGNMENT; external advisors never (ABAC-PRIVATE-WEALTH-SEGREGATION)"},
    {"id": "finance", "name": "Finance Data Product", "owner": "CFO (synthetic)", "classification": "confidential",
     "entities": [m.ProductMonthly, m.FinanceMonthly], "lineage": ["Fund accounting (mock)", "ERP / general ledger (mock)", "FLO semantic layer"],
     "quality_checks": ["DQ-FIN-001", "DQ-FIN-002"], "freshness_sla": "monthly close + 7 business days", "access_policy": "finance:read / exec:read"},
    {"id": "risk", "name": "Risk Data Product", "owner": "CRO (synthetic)", "classification": "confidential",
     "entities": [m.RiskRegisterItem, m.ComplianceEvent, m.Control], "lineage": ["Risk register (mock)", "Compliance case management (mock)"],
     "quality_checks": ["DQ-RSK-001"], "freshness_sla": "weekly", "access_policy": "risk:read_aggregate / compliance:read"},
    {"id": "strategy", "name": "Strategy Data Product", "owner": "Strategy Office (synthetic)", "classification": "confidential",
     "entities": [m.Decision, m.Initiative], "lineage": ["Executive committee minutes (synthetic)", "PMO tracker (synthetic)"],
     "quality_checks": ["DQ-STR-001"], "freshness_sla": "monthly", "access_policy": "decisions:read / decisions:write"},
]


def catalog(store) -> dict:
    out = []
    for p in PRODUCTS:
        schema = []
        for ent in p["entities"]:
            cols = [{"name": c.key, "type": str(c.columns[0].type)} for c in inspect(ent).mapper.column_attrs]
            schema.append({"entity": ent.__tablename__, "rows": len(store.tables.get(ent.__tablename__, [])) or None, "columns": cols})
        out.append({**{k: v for k, v in p.items() if k != "entities"}, "version": store.version, "schema": schema, "synthetic": True})
    return {"data_products": out}
