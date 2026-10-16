"""FHIR slot mapping (Mode C interface) and MCP/LangChain tool exposure."""

from datetime import UTC, datetime

import pytest

from app.integrations.availability import FhirSlotAdapter, IntegrationNotConfigured, ProviderApiAdapter
from app.mcp.servers import SERVERS, langchain_tools, mcp_catalog
from app.schemas.domain import ServiceType, SourceSlotStatus

BUNDLE = {"resourceType": "Bundle", "entry": [
    {"resource": {"resourceType": "Slot", "id": "s1", "status": "free", "start": "2026-11-01T14:00:00Z",
                  "schedule": {"reference": "Schedule/sch-1"}, "meta": {"lastUpdated": "2026-10-16T13:00:00Z"},
                  "serviceType": [{"coding": [{"code": "MRI-CODE"}]}]}},
    {"resource": {"resourceType": "Slot", "id": "s2", "status": "busy-tentative", "start": "2026-11-02T14:00:00Z",
                  "schedule": {"reference": "Schedule/sch-1"}, "serviceType": [{"coding": [{"code": "MRI-CODE"}]}]}},
    {"resource": {"resourceType": "Slot", "id": "s3", "status": "entered-in-error", "start": "2026-11-02T14:00:00Z",
                  "schedule": {"reference": "Schedule/sch-1"}}},
    {"resource": {"resourceType": "Slot", "id": "s4", "status": "free", "start": "2026-11-02T14:00:00Z",
                  "schedule": {"reference": "Schedule/unknown"}, "serviceType": [{"coding": [{"code": "MRI-CODE"}]}]}},
]}


def test_fhir_mapping():
    a = FhirSlotAdapter("INT-FHIR", {"sch-1": "FAC-001"}, {"MRI-CODE": ServiceType.MRI})
    out = a.map_bundle(BUNDLE, datetime(2026, 10, 16, tzinfo=UTC))
    assert [s.slot_id for s in out] == ["FHIR-s1", "FHIR-s2"]
    assert out[0].source_status == SourceSlotStatus.CONFIRMED_BY_FEED and not out[0].is_synthetic
    assert out[1].source_status == SourceSlotStatus.ADVERTISED


def test_unconfigured_live_adapters_refuse():
    with pytest.raises(IntegrationNotConfigured):
        FhirSlotAdapter("X", {}, {}).fetch(["FAC-001"], ServiceType.MRI)
    with pytest.raises(IntegrationNotConfigured):
        ProviderApiAdapter("X").fetch([], ServiceType.MRI)


def test_mcp_catalog_contracts():
    cat = {s["id"]: s for s in mcp_catalog()}
    assert set(cat) == set(SERVERS) and len(cat) == 9
    fd = cat["facility_directory"]["tools"][0]
    assert fd["input_schema"]["properties"]["service"] and fd["output_schema"]
    assert "APPROVAL_REQUIRED" in cat["geolocation"]["error_contract"]


def test_langchain_tools_execute_through_harness():
    tools = {t.name: t for t in langchain_tools("geolocation")}
    out = tools["geo_resolve_location"].invoke({"query": "Markham"})
    assert out["found"] and out["location"]["precision"] == "city_centroid"


def test_fastmcp_server_builds():
    app = build = None
    from app.mcp.servers import build_fastmcp_server

    build = build_fastmcp_server
    app = build("geolocation")
    assert app is not None
