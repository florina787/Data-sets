"""Canonical models for the read-only part availability adapter (generated, synthetic)."""
from datetime import date

from pydantic import BaseModel, Field

PART_PATTERN = r"^P-[0-9A-Z]{3,8}$"


class StockLocation(BaseModel):
    location: str
    quantity_on_hand: int = Field(ge=0)
    lot: str
    last_counted: date
    verified: bool
    note: str = ""


class PartAvailability(BaseModel):
    part_number: str = Field(pattern=PART_PATTERN)
    description: str
    total_verified: int = Field(ge=0)
    locations: list[StockLocation]
    source: str = "V_PART_AVAILABILITY (synthetic snapshot)"
    synthetic: bool = True


class Page(BaseModel):
    items: list[PartAvailability]
    limit: int
    offset: int
    total: int


class Problem(BaseModel):
    code: str
    message: str
