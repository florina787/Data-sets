"""Enterprise integration adapter interfaces (NOT CONNECTED).

These Protocols document how ClaimForge would integrate with enterprise systems. Only the
in-memory MOCKED implementations below exist in this repository; no external system
(Jira, Confluence, GitHub, Splunk, ServiceNow, Kafka, FHIR servers, claims platforms, …)
is connected.
"""

from __future__ import annotations

from typing import Protocol

from app.models.domain import Defect


class IssueTracker(Protocol):  # Jira / Azure DevOps / ServiceNow
    def create_defect(self, defect: Defect) -> str: ...


class DocumentSource(Protocol):  # Confluence / SharePoint / enterprise policy repository
    def fetch_policy_documents(self) -> list[tuple[str, str]]: ...


class SourceControl(Protocol):  # GitHub / GitLab / Bitbucket — proposals only, never auto-merge
    def open_change_proposal(self, title: str, diff: str) -> str: ...


class CiPipeline(Protocol):  # Jenkins / Azure DevOps / GitHub Actions / SonarQube
    def latest_quality_gate(self, component: str) -> dict: ...


class ObservabilitySource(Protocol):  # Splunk / Datadog / Kafka claims.adjudicated consumer
    def claim_events(self, since: str) -> list[dict]: ...


class FhirClient(Protocol):  # FHIR R4 Claim / ExplanationOfBenefit (mapping only; not implemented)
    def explanation_of_benefit(self, claim_id: str) -> dict: ...


class InMemoryIssueTracker:
    """MOCKED tracker used by the demo."""

    def __init__(self) -> None:
        self.items: dict[str, Defect] = {}

    def create_defect(self, defect: Defect) -> str:
        self.items[defect.key] = defect
        return defect.key


INTEGRATION_STATUS = {
    name: "NOT CONNECTED (interface only)" for name in (
        "Jira", "Confluence", "SharePoint", "GitHub", "GitLab", "Bitbucket", "Jenkins", "Azure DevOps", "SonarQube",
        "Postman", "Splunk", "Datadog", "ServiceNow", "Kubernetes", "Kafka", "Enterprise policy repositories",
        "FHIR servers", "Claims platforms")
}
