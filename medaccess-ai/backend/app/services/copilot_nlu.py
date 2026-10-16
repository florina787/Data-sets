"""Deterministic natural-language understanding for the Christina copilot.

Used when no LLM is configured, and always used to validate LLM-extracted fields:
an LLM may *propose* slot values, but only values that pass these validators are
accepted into workflow state.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta

from pydantic import BaseModel

from app.schemas.domain import RequisitionStatus, ServiceType
from app.services.gazetteer import CITY_CENTROIDS, SUPPORTED_RADII_KM, nearest_supported_radius

S = ServiceType
SERVICE_SYNONYMS: list[tuple[ServiceType, list[str]]] = [
    (S.MRI, [r"\bmri\b", r"magnetic resonance"]),
    (S.CT, [r"\bct\b", r"\bcat scan", r"computed tomography", r"ct scan"]),
    (S.MAMMOGRAPHY, [r"mammogra"]),
    (S.ULTRASOUND, [r"ultrasound", r"sonogra", r"\bus scan"]),
    (S.XRAY, [r"x[\s-]?ray", r"radiograph"]),
    (S.BLOOD_TEST, [r"blood (test|work)", r"bloodwork", r"blood draw", r"\bcbc\b"]),
    (S.URINE_TEST, [r"urine", r"urinalysis"]),
    (S.LAB_INVESTIGATION, [r"\blab(oratory)?\b", r"lab test"]),
    (S.SPECIALIST, [r"specialist", r"cardiolog", r"dermatolog", r"neurolog", r"orthop", r"consult"]),
    (S.FAMILY_PHYSICIAN, [r"family (doctor|physician)", r"\bgp\b", r"family practice", r"see a doctor",
                          r"doctor'?s appointment"]),
]


def classify_service(text: str) -> ServiceType | None:
    t = (text or "").lower()
    for svc, pats in SERVICE_SYNONYMS:
        if any(re.search(p, t) for p in pats):
            return svc
    return None


class Extracted(BaseModel):
    service: ServiceType | None = None
    location: str | None = None
    radius_km: int | None = None
    requisition_status: RequisitionStatus | None = None
    existing_appointment_days: int | None = None
    existing_appointment_date: str | None = None
    wants_booking: bool = False
    is_question: bool = False
    greeting: bool = False


_POSTAL = re.compile(r"\b([ABCEGHJ-NPRSTVXY]\d[ABCEGHJ-NPRSTV-Z])\s?(\d[ABCEGHJ-NPRSTV-Z]\d)?\b", re.I)


def extract(text: str, today: date | None = None) -> Extracted:
    t = (text or "").strip()
    low = t.lower()
    today = today or datetime.now().date()
    e = Extracted(service=classify_service(t))
    m = _POSTAL.search(t)
    if m:
        e.location = m.group(1).upper()
    else:
        for city in sorted(CITY_CENTROIDS, key=len, reverse=True):
            if re.search(rf"\b{re.escape(city)}\b", low):
                e.location = city.title()
                break
    rm = re.search(r"(\d{1,3})\s*(km|kilomet)", low)
    if rm:
        e.radius_km = nearest_supported_radius(int(rm.group(1)))
    if re.search(r"\b(no|don'?t have|do not have|haven'?t got|without)\b.{0,20}\b(requisition|referral)", low):
        e.requisition_status = RequisitionStatus.NO_REQUISITION
    elif re.search(r"\b(yes|i have|have a|got a|with a)\b.{0,20}\b(requisition|referral)", low) or \
            re.fullmatch(r"\s*(yes|yep|yeah|i do)\.?\s*", low):
        e.requisition_status = RequisitionStatus.HAS_REQUISITION
    am = re.search(r"(\d{1,3})\s*(day|week|month)s?\s*(away|from now|out|wait)", low) or \
        re.search(r"(?:in|wait(?:ing)? of|is)\s*(\d{1,3})\s*(day|week|month)s?", low)
    word_nums = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "eight": 8, "ten": 10, "twelve": 12}
    if not am:
        wm = re.search(r"\b(one|two|three|four|five|six|eight|ten|twelve)\s+(day|week|month)s?\b", low)
        if wm and re.search(r"appointment|wait|away|booked", low):
            e.existing_appointment_days = word_nums[wm.group(1)] * {"day": 1, "week": 7, "month": 30}[wm.group(2)]
    else:
        n = int(am.group(1))
        e.existing_appointment_days = n * {"day": 1, "week": 7, "month": 30}[am.group(2)]
    dm = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", t)
    if dm:
        try:
            d = date.fromisoformat(dm.group(1))
            e.existing_appointment_date = d.isoformat()
            e.existing_appointment_days = (d - today).days
        except ValueError:
            pass
    if e.existing_appointment_days is not None and not e.existing_appointment_date:
        e.existing_appointment_date = (today + timedelta(days=e.existing_appointment_days)).isoformat()
    e.wants_booking = bool(re.search(r"\b(book|reserve|schedule) (it|this|that|the|option|slot)", low))
    e.is_question = bool(re.search(r"\?$|^(what|how|do i|does|can i|is|where|when|which)\b", low)) and \
        e.service is None and e.location is None
    e.greeting = bool(re.fullmatch(r"\s*(hi|hello|hey|good (morning|afternoon|evening))[!. ]*", low))
    return e


RADII = SUPPORTED_RADII_KM
