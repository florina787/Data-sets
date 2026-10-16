"""Approximate centroids for GTA municipalities and a subset of Toronto FSAs.

These are approximate public geographic centroids used only to anchor a search
radius. They are not addresses and are labelled as approximate in the UI.
"""

from __future__ import annotations

import re

from pydantic import BaseModel

CITY_CENTROIDS: dict[str, tuple[float, float]] = {
    "toronto": (43.6532, -79.3832),
    "downtown toronto": (43.6532, -79.3832),
    "north york": (43.7615, -79.4111),
    "scarborough": (43.7731, -79.2578),
    "etobicoke": (43.6205, -79.5132),
    "east york": (43.6910, -79.3280),
    "york": (43.6896, -79.4870),
    "mississauga": (43.5890, -79.6441),
    "brampton": (43.7315, -79.7624),
    "markham": (43.8561, -79.3370),
    "vaughan": (43.8372, -79.5083),
    "richmond hill": (43.8828, -79.4403),
    "oakville": (43.4675, -79.6877),
    "burlington": (43.3255, -79.7990),
    "milton": (43.5183, -79.8774),
    "pickering": (43.8384, -79.0868),
    "ajax": (43.8509, -79.0204),
    "whitby": (43.8975, -78.9429),
    "oshawa": (43.8971, -78.8658),
    "newmarket": (44.0592, -79.4613),
    "aurora": (44.0065, -79.4504),
    "hamilton": (43.2557, -79.8711),
    "barrie": (44.3894, -79.6903),
    "guelph": (43.5448, -80.2482),
}

# Forward sortation areas (first three characters of a Canadian postal code).
FSA_CENTROIDS: dict[str, tuple[float, float]] = {
    "M5V": (43.6426, -79.3971), "M5H": (43.6503, -79.3843), "M5G": (43.6579, -79.3873),
    "M5S": (43.6629, -79.3987), "M5T": (43.6532, -79.4000), "M4W": (43.6796, -79.3775),
    "M4Y": (43.6658, -79.3831), "M4K": (43.6795, -79.3524), "M4M": (43.6595, -79.3409),
    "M4E": (43.6764, -79.2930), "M6G": (43.6690, -79.4225), "M6K": (43.6369, -79.4282),
    "M6P": (43.6616, -79.4648), "M6S": (43.6515, -79.4844), "M2N": (43.7701, -79.4085),
    "M3H": (43.7543, -79.4423), "M2J": (43.7785, -79.3466), "M1P": (43.7574, -79.2731),
    "M1B": (43.8067, -79.1944), "M9W": (43.7067, -79.5940), "M9B": (43.6509, -79.5547),
    "M8V": (43.6056, -79.5013), "L5B": (43.5866, -79.6454), "L6T": (43.7187, -79.7254),
    "L3R": (43.8487, -79.3375), "L4J": (43.8102, -79.4527), "L1V": (43.8239, -79.0860),
    "L6H": (43.4767, -79.7214),
}

SUPPORTED_RADII_KM = (2, 3, 5, 10, 25, 50, 100)

_POSTAL_RE = re.compile(r"^\s*([A-Za-z]\d[A-Za-z])\s*(\d[A-Za-z]\d)?\s*$")


class ResolvedLocation(BaseModel):
    query: str
    label: str
    latitude: float
    longitude: float
    precision: str  # city_centroid | fsa_centroid | coordinates
    approximate: bool = True


def resolve_location(query: str) -> ResolvedLocation | None:
    """Resolve a city name, postal code/FSA or "lat,lon" string. Returns None if unknown."""
    q = (query or "").strip()
    if not q:
        return None
    coord = re.match(r"^\s*(-?\d{1,2}\.\d+)\s*,\s*(-?\d{1,3}\.\d+)\s*$", q)
    if coord:
        lat, lon = float(coord.group(1)), float(coord.group(2))
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            return ResolvedLocation(query=q, label=f"{lat:.4f}, {lon:.4f}", latitude=lat, longitude=lon,
                                    precision="coordinates", approximate=False)
        return None
    m = _POSTAL_RE.match(q)
    if m:
        fsa = m.group(1).upper()
        if fsa in FSA_CENTROIDS:
            lat, lon = FSA_CENTROIDS[fsa]
            # Only the FSA is retained; the full postal code is not stored.
            return ResolvedLocation(query=fsa, label=f"{fsa} (postal area, approximate)", latitude=lat,
                                    longitude=lon, precision="fsa_centroid")
        return None
    key = re.sub(r"\s+", " ", q.lower().replace(",", " ").replace(" on", "").replace(" ontario", "")).strip()
    if key in CITY_CENTROIDS:
        lat, lon = CITY_CENTROIDS[key]
        return ResolvedLocation(query=q, label=f"{key.title()} (city centre, approximate)", latitude=lat,
                                longitude=lon, precision="city_centroid")
    return None


def nearest_supported_radius(km: float) -> int:
    for r in SUPPORTED_RADII_KM:
        if km <= r:
            return r
    return SUPPORTED_RADII_KM[-1]
