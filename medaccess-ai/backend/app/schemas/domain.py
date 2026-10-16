"""Core domain schemas shared by agents, tools, API and persistence."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ServiceType(str, Enum):
    MRI = "MRI"
    CT = "CT"
    ULTRASOUND = "ULTRASOUND"
    XRAY = "XRAY"
    MAMMOGRAPHY = "MAMMOGRAPHY"
    BLOOD_TEST = "BLOOD_TEST"
    URINE_TEST = "URINE_TEST"
    LAB_INVESTIGATION = "LAB_INVESTIGATION"
    FAMILY_PHYSICIAN = "FAMILY_PHYSICIAN"
    SPECIALIST = "SPECIALIST"


SERVICE_LABELS: dict[ServiceType, str] = {
    ServiceType.MRI: "MRI",
    ServiceType.CT: "CT scan",
    ServiceType.ULTRASOUND: "Ultrasound",
    ServiceType.XRAY: "X-ray",
    ServiceType.MAMMOGRAPHY: "Mammography",
    ServiceType.BLOOD_TEST: "Blood test",
    ServiceType.URINE_TEST: "Urine test",
    ServiceType.LAB_INVESTIGATION: "Laboratory investigation",
    ServiceType.FAMILY_PHYSICIAN: "Family physician appointment",
    ServiceType.SPECIALIST: "Specialist consultation",
}

IMAGING = {ServiceType.MRI, ServiceType.CT, ServiceType.ULTRASOUND, ServiceType.XRAY, ServiceType.MAMMOGRAPHY}
LAB = {ServiceType.BLOOD_TEST, ServiceType.URINE_TEST, ServiceType.LAB_INVESTIGATION}


class AvailabilityStatus(str, Enum):
    VERIFIED_AVAILABLE = "VERIFIED_AVAILABLE"
    ADVERTISED_UNVERIFIED = "ADVERTISED_UNVERIFIED"
    CONTACT_REQUIRED = "CONTACT_REQUIRED"
    UNAVAILABLE = "UNAVAILABLE"
    UNKNOWN = "UNKNOWN"
    DEMO_SIMULATED = "DEMO_SIMULATED"


class SourceSlotStatus(str, Enum):
    """Raw status as reported by an availability source, before verification."""

    CONFIRMED_BY_FEED = "confirmed_by_provider_feed"
    ADVERTISED = "advertised"
    CALL_TO_CONFIRM = "call_to_confirm"
    BOOKED = "booked"
    CANCELLED = "cancelled"


class DataMode(str, Enum):
    SYNTHETIC = "SYNTHETIC"
    PUBLIC_DISCOVERY = "PUBLIC_DISCOVERY"
    AUTHORIZED_LIVE = "AUTHORIZED_LIVE"


class RequisitionStatus(str, Enum):
    HAS_REQUISITION = "HAS_REQUISITION"
    NO_REQUISITION = "NO_REQUISITION"
    UNKNOWN = "UNKNOWN"


class EligibilityStatus(str, Enum):
    ELIGIBLE = "ELIGIBLE"
    ELIGIBLE_WITH_CONDITIONS = "ELIGIBLE_WITH_CONDITIONS"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    INELIGIBLE = "INELIGIBLE"


class BookingStatus(str, Enum):
    NOT_REQUESTED = "NOT_REQUESTED"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    REJECTED = "REJECTED"
    HANDOFF_PREPARED = "HANDOFF_PREPARED"
    PATIENT_REPORTED_BOOKED = "PATIENT_REPORTED_BOOKED"
    PROVIDER_CONFIRMED = "PROVIDER_CONFIRMED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class FacilityType(str, Enum):
    IMAGING_CENTRE = "IMAGING_CENTRE"
    HOSPITAL = "HOSPITAL"
    LABORATORY = "LABORATORY"
    FAMILY_CLINIC = "FAMILY_CLINIC"
    SPECIALIST_CLINIC = "SPECIALIST_CLINIC"


class Facility(BaseModel):
    model_config = ConfigDict(frozen=False)

    id: str
    name: str
    facility_type: FacilityType
    network: str
    city: str
    neighbourhood: str
    address: str
    postal_code: str
    latitude: float
    longitude: float
    timezone: str = "America/Toronto"
    phone: str
    booking_url: str | None = None
    booking_capability: str  # online_handoff | phone_only | none
    services: list[ServiceType]
    wheelchair_accessible: bool
    transit_score: int = Field(ge=0, le=100)  # synthetic transit accessibility indicator
    parking: bool
    hours: dict[str, str]
    funding: str  # public_demo | private_pay_demo
    accepted_requisition_formats: list[str]
    referral_required_for: list[ServiceType]
    integration_id: str
    data_mode: DataMode = DataMode.SYNTHETIC
    is_synthetic: bool = True


class ProviderIntegration(BaseModel):
    id: str
    name: str
    adapter_type: str  # synthetic_demo | provider_api | fhir | partner | public_feed
    reliability: float = Field(ge=0, le=1)
    data_mode: DataMode = DataMode.SYNTHETIC
    authorized: bool = True
    notes: str = ""


class RawSlot(BaseModel):
    slot_id: str
    facility_id: str
    service: ServiceType
    start_utc: datetime | None
    duration_minutes: int = 30
    source_status: SourceSlotStatus
    source_id: str
    last_verified_at: datetime | None
    is_synthetic: bool = True


class VerifiedSlot(BaseModel):
    slot_id: str
    facility_id: str
    service: ServiceType
    start_utc: datetime | None
    start_local: str | None
    source_id: str
    source_status: SourceSlotStatus
    verification_status: AvailabilityStatus
    display_status: AvailabilityStatus
    verification_reasons: list[str]
    last_verified_at: datetime | None
    data_age_hours: float | None
    is_synthetic: bool


class EligibilityResult(BaseModel):
    facility_id: str
    service: ServiceType
    status: EligibilityStatus
    requisition_required: bool
    referral_required: bool
    coverage_note: str
    reasons: list[str]
    actions: list[str]


class GeoResult(BaseModel):
    facility_id: str
    straight_km: float
    est_driving_km: float
    est_driving_minutes: int
    est_transit_minutes: int | None
    transit_accessible: bool
    method: str = "haversine + road-factor estimate (not live routing)"


class Recommendation(BaseModel):
    rank: int
    tier: str  # CONFIRMED_ALTERNATIVE | UNVERIFIED_POSSIBILITY
    facility_id: str
    facility_name: str
    slot_id: str
    service: ServiceType
    start_local: str | None
    start_utc: datetime | None
    days_until: int | None
    days_saved: int | None
    straight_km: float
    est_driving_minutes: int
    verification_status: AvailabilityStatus
    display_status: AvailabilityStatus
    eligibility_status: EligibilityStatus
    score: float
    reasons: list[str]
    source_id: str
    last_verified_at: datetime | None
    is_synthetic: bool
    booking_capability: str


class SourceReference(BaseModel):
    source_id: str
    kind: str
    title: str
    retrieved_at: datetime | None = None
    url: str | None = None
