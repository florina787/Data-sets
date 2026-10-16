"""Requisition / referral eligibility rules (Agent 9) - deterministic.

These rules describe the *synthetic* facilities' documented requirements. They
never guarantee provincial (OHIP) coverage; coverage notes always instruct the
patient to confirm with the provider.
"""

from __future__ import annotations

from pydantic import BaseModel

from app.schemas.domain import (
    IMAGING,
    LAB,
    EligibilityResult,
    EligibilityStatus,
    Facility,
    RequisitionStatus,
    ServiceType,
)

E = EligibilityStatus


class PatientCriteria(BaseModel):
    requisition_status: RequisitionStatus = RequisitionStatus.UNKNOWN
    requisition_format: str | None = None  # e.g. standard_imaging_requisition, network_form:<network>
    include_private_pay: bool = False
    needs_wheelchair_access: bool = False


def requisition_required(service: ServiceType) -> bool:
    return service in IMAGING or service in LAB


def default_format(service: ServiceType) -> str | None:
    if service in IMAGING:
        return "standard_imaging_requisition"
    if service in LAB:
        return "standard_lab_requisition"
    if service == ServiceType.SPECIALIST:
        return "specialist_referral_letter"
    return None


def evaluate(facility: Facility, service: ServiceType, p: PatientCriteria) -> EligibilityResult:
    reasons: list[str] = []
    actions: list[str] = []
    status = E.ELIGIBLE
    req_needed = requisition_required(service)
    referral_needed = service in facility.referral_required_for

    def downgrade(new: EligibilityStatus) -> None:
        nonlocal status
        order = [E.ELIGIBLE, E.ELIGIBLE_WITH_CONDITIONS, E.NEEDS_REVIEW, E.INELIGIBLE]
        if order.index(new) > order.index(status):
            status = new

    if service not in facility.services:
        return EligibilityResult(facility_id=facility.id, service=service, status=E.INELIGIBLE,
                                 requisition_required=req_needed, referral_required=referral_needed,
                                 coverage_note="", reasons=["Facility does not offer this service."], actions=[])

    if req_needed or referral_needed:
        doc = "referral" if referral_needed and not req_needed else "requisition"
        if p.requisition_status == RequisitionStatus.NO_REQUISITION:
            downgrade(E.NEEDS_REVIEW)
            reasons.append(f"A physician {doc} is required for this service.")
            actions.append(f"Contact your referring clinician to obtain a {doc}.")
        elif p.requisition_status == RequisitionStatus.UNKNOWN:
            downgrade(E.ELIGIBLE_WITH_CONDITIONS)
            reasons.append(f"A {doc} is required; requisition status not yet confirmed.")
            actions.append(f"Confirm you have a valid {doc} before contacting the provider.")
        fmt = p.requisition_format or default_format(service)
        if p.requisition_status != RequisitionStatus.NO_REQUISITION and fmt:
            if fmt not in facility.accepted_requisition_formats:
                downgrade(E.INELIGIBLE)
                pretty = fmt.replace("network_form:", "network-specific form for ").replace("_", " ")
                reasons.append(f"Facility does not accept a {pretty}.")
                actions.append("Ask your referring clinician whether a new requisition can be issued for this facility.")
            else:
                reasons.append("Facility documents acceptance of this requisition format.")

    if facility.funding == "private_pay_demo":
        coverage = "Private-pay facility: fees may apply. Not publicly funded."
        if not p.include_private_pay:
            downgrade(E.INELIGIBLE)
            reasons.append("Private-pay facility excluded by your preferences.")
        else:
            downgrade(E.ELIGIBLE_WITH_CONDITIONS)
            reasons.append("Private-pay facility - fees may apply.")
    else:
        coverage = ("Service may be eligible for provincial coverage. Coverage is not guaranteed - "
                    "confirm with the provider.")

    if p.needs_wheelchair_access and not facility.wheelchair_accessible:
        downgrade(E.INELIGIBLE)
        reasons.append("Facility is not listed as wheelchair accessible.")

    return EligibilityResult(facility_id=facility.id, service=service, status=status,
                             requisition_required=req_needed, referral_required=referral_needed,
                             coverage_note=coverage, reasons=reasons, actions=actions)
