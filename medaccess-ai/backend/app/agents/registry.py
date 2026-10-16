"""Agent catalogue: 20 patient-workflow agents + AI-SDLC engineering agents."""

from __future__ import annotations

from app.harness.core import AGENTS, AgentSpec, register_agent

PATIENT_AGENTS = [
    AgentSpec("supervisor", "Supervisor Agent", "Routes intent, controls graph execution, budgets and checkpoints.",
              "patient", uses_llm=True, prompt_version="supervisor-v1"),
    AgentSpec("intake", "Patient Intake Agent", "Collects only the minimum search parameters.", "patient",
              {"geo.resolve_location"}),
    AgentSpec("clinical_safety", "Clinical Safety Agent", "Screens for urgent-symptom language; never diagnoses.",
              "patient"),
    AgentSpec("service_classification", "Service Classification Agent", "Maps requests to supported services.",
              "patient", uses_llm=True, prompt_version="classify-v1"),
    AgentSpec("facility_discovery", "Facility Discovery Agent", "Finds directory facilities offering the service.",
              "patient", {"directory.search_facilities"}),
    AgentSpec("geospatial", "Geospatial Intelligence Agent", "Distance, travel estimates and radius filtering.",
              "patient", {"geo.filter_by_radius"}),
    AgentSpec("availability_search", "Appointment Availability Agent", "Queries authorized availability sources.",
              "patient", {"availability.fetch_slots"}, max_retries=2),
    AgentSpec("availability_verification", "Availability Verification Agent",
              "Verifies timestamp, identity, service, freshness and source reliability.", "patient",
              {"availability.verify_slots"}),
    AgentSpec("eligibility", "Requisition Eligibility Agent", "Applies documented requisition/referral rules.",
              "patient", {"requisition.evaluate"}),
    AgentSpec("wait_time", "Wait-Time Intelligence Agent", "Deterministic wait and days-saved calculations.",
              "patient"),
    AgentSpec("recommendation", "Recommendation Agent", "Ranks verified alternatives separately from possibilities.",
              "patient", uses_llm=True, prompt_version="explain-v1"),
    AgentSpec("booking_assistance", "Booking Assistance Agent", "Prepares booking handoffs; never fabricates bookings.",
              "patient", {"booking.prepare_handoff"}),
    AgentSpec("notification", "Notification Agent", "Sends authorized, minimal-content reminders.", "patient",
              {"notification.send"}),
    AgentSpec("rag_knowledge", "RAG Knowledge Agent", "Answers administrative questions with citations.", "patient",
              {"knowledge.search"}, uses_llm=True, prompt_version="rag-v1"),
    AgentSpec("data_quality", "Data Quality Agent", "Detects duplicates, stale, invalid and unattributed records.",
              "patient"),
    AgentSpec("privacy_security", "Privacy and Security Agent", "Data minimisation, injection and access checks.",
              "patient"),
    AgentSpec("human_approval", "Human Approval Agent", "Pauses workflows before sensitive actions.", "patient"),
    AgentSpec("audit", "Audit Agent", "Hash-chained audit trail of all workflow activity.", "patient"),
    AgentSpec("monitoring", "Monitoring Agent", "Observes failures, latency, freshness and cost.", "patient"),
    AgentSpec("recovery", "Recovery Agent", "Bounded retries, circuit breakers and graceful fallback.", "patient",
              {"availability.fetch_slots"}, max_retries=1),
]

SDLC_AGENTS = [
    AgentSpec("sdlc_requirements", "Requirements Agent", "User stories, acceptance criteria, ambiguity detection.",
              "sdlc", uses_llm=True, prompt_version="requirements-v1"),
    AgentSpec("sdlc_architecture", "Architecture Agent", "Mermaid architecture, sequence and data-flow diagrams.",
              "sdlc"),
    AgentSpec("sdlc_development", "Development Agent", "Implementation plans and proposed code changes.", "sdlc"),
    AgentSpec("sdlc_qa", "QA Agent", "Generates and executes scenario and regression tests.", "sdlc"),
    AgentSpec("sdlc_security", "Security Agent", "Secret, dependency, authorization and injection checks.", "sdlc"),
    AgentSpec("sdlc_release", "Release Agent", "Release checklist, manifest, rollback plan, approval request.", "sdlc"),
    AgentSpec("sdlc_monitoring", "Production Monitoring Agent", "Watches health metrics and detects anomalies.",
              "sdlc"),
    AgentSpec("sdlc_rca", "Root Cause Analysis Agent", "Evidence-based hypotheses; never asserts without evidence.",
              "sdlc"),
]


def register_all() -> None:
    if AGENTS:
        return
    for a in PATIENT_AGENTS + SDLC_AGENTS:
        register_agent(a)
