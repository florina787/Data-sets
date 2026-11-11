"""Demo tenants. Every record created here is synthetic and flagged ``is_demo``; organisations are fictional."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from florome.connectors.sandbox import API, SandboxConnector, SandboxWorld
from florome.context import AppContext
from florome.governance.policy import DEFAULT_POLICY
from florome.models import (
    ActionExecution,
    Approval,
    AuditEvent,
    Connection,
    CostRecord,
    Dependency,
    Evidence,
    Hypothesis,
    Incident,
    MCPServerRecord,
    MCPToolRecord,
    RCAReport,
    RemediationPlan,
    Resource,
    Tenant,
    User,
    ValidationResult,
    utcnow,
)
from florome.security import audit

DEMO_TENANTS = {
    "t-meridian": ("Meridian Freight (synthetic demo)", ["viewer", "operator", "approver", "admin"]),
    "t-halcyon": ("Halcyon Retail (synthetic demo)", ["operator", "admin"]),
}

COSTS = [  # provider, account, business unit, application, AI component, outcome, monthly amount
    ("aws", "prod-data-000000000000", "Finance", "Revenue reporting", "ingest-orders (Lambda)", "Daily revenue report", 1840.0),
    ("aws", "prod-ai-000000000001", "Customer Service", "Customer portal", "support-copilot (Bedrock agent)", "Tickets deflected", 6120.0),
    ("aws", "prod-ai-000000000001", "Customer Service", "Customer portal", "support-kb (embeddings)", "Tickets deflected", 940.0),
    ("databricks", "workspace-demo", "Finance", "Revenue reporting", "orders-etl (Jobs compute)", "Daily revenue report", 3260.0),
    ("databricks", "workspace-demo", "Supply Chain", "Demand forecasting", "forecast-model (Model Serving)", "Forecast accuracy", 4410.0),
    ("azure", "sub-demo-revenue", "Finance", "Revenue reporting", "revenue-api (App Service)", "Daily revenue report", 1215.0),
    ("azure", "sub-demo-portal", "Customer Service", "Customer portal", "customer-portal (App Service)", "Tickets deflected", 980.0),
    ("azure", "sub-demo-ai", "Legal", "Contract review", "contract-summariser (Azure OpenAI)", "Review hours saved", 2730.0),
]
MONTH_FACTORS = {"2026-08": 0.92, "2026-09": 1.0, "2026-10": 1.11}


def token_for(tenant_id: str, role: str) -> str:
    return f"demo-{tenant_id.removeprefix('t-')}-{role}"


def wipe_tenant(db: Session, tenant_id: str) -> None:
    for model in (ValidationResult, ActionExecution, Approval, RemediationPlan, Hypothesis, RCAReport, Evidence, Incident,
                  MCPToolRecord, MCPServerRecord, Dependency, Resource, Connection, CostRecord, AuditEvent, User):
        db.execute(delete(model).where(model.tenant_id == tenant_id))
    db.execute(delete(Tenant).where(Tenant.id == tenant_id))


async def seed_demo(db: Session, ctx: AppContext, tenant_id: str) -> None:
    name, roles = DEMO_TENANTS[tenant_id]
    wipe_tenant(db, tenant_id)
    db.flush()
    db.add(Tenant(id=tenant_id, name=name, mode="demo", policy=dict(DEFAULT_POLICY)))
    db.flush()
    for role in roles:
        uid = f"u-{tenant_id.removeprefix('t-')}-{role}"
        db.add(User(id=uid, tenant_id=tenant_id, name=f"Demo {role.title()}", roles=[role]))
        if ctx.settings.enable_demo_tokens:
            ctx.demo_tokens[token_for(tenant_id, role)] = uid
    db.flush()

    world = SandboxWorld()
    connector = SandboxConnector(world)
    conn = Connection(tenant_id=tenant_id, platform="sandbox", connector_type="sandbox", display_name="Multi-cloud sandbox (simulated)",
                      is_demo=True, capabilities=sorted(c.value for c in connector.capabilities()))
    db.add(conn)
    db.flush()
    health = await connector.health()
    conn.status, conn.verified_at = ("verified", utcnow()) if health.ok else ("failed", None)
    ctx.registry.register(conn.id, connector)

    ref_to_id = {}
    for i, r in enumerate(await connector.discover_resources()):
        rid = f"res-{tenant_id.removeprefix('t-')}-{i:02d}"
        ref_to_id[r.source_ref] = rid
        db.add(Resource(id=rid, tenant_id=tenant_id, connection_id=conn.id, platform=r.platform, kind=r.kind, name=r.name,
                        environment=r.environment, source_ref=r.source_ref, attributes=r.attributes, is_demo=True))
    db.flush()
    from florome.connectors.sandbox import DEPENDENCIES
    for s, t, kind in DEPENDENCIES:
        db.add(Dependency(tenant_id=tenant_id, source_id=ref_to_id[s], target_id=ref_to_id[t], kind=kind, provenance="declared"))
    db.add(Incident(tenant_id=tenant_id, title="Revenue API returning HTTP 500; daily revenue report blocked", severity="sev2",
                    primary_resource_id=ref_to_id[API], detected_at=world.anchor, is_demo=True, source_system="sandbox",
                    symptoms=["HTTP 5xx rate 23.4% on revenue-api", "Daily revenue report blocked"]))
    for period, factor in MONTH_FACTORS.items():
        for prov, acct, bu, app, comp, outcome, amt in COSTS:
            db.add(CostRecord(tenant_id=tenant_id, period=period, provider=prov, account=acct, business_unit=bu, application=app,
                              ai_component=comp, outcome=outcome, amount=round(amt * factor, 2), source_system="sandbox", is_demo=True))
    if db.scalars(select(MCPServerRecord).where(MCPServerRecord.tenant_id == tenant_id)).first() is None:
        db.add(MCPServerRecord(tenant_id=tenant_id, name="sandbox-ops"))
    audit.record(db, tenant_id, "system", "demo.seed", tenant_id, "success", {"synthetic": True})
    db.flush()
