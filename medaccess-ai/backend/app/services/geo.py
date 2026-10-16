"""Deterministic geospatial calculations.

Driving and transit figures are *estimates* derived from straight-line distance;
they are not live routing results and are labelled as such everywhere.
"""

from __future__ import annotations

import math

from app.schemas.domain import Facility, GeoResult

EARTH_RADIUS_KM = 6371.0088
ROAD_FACTOR = 1.3  # typical urban circuity factor (estimate)
AVG_URBAN_DRIVE_KMH = 32.0
AVG_TRANSIT_KMH = 18.0
TRANSIT_ACCESS_THRESHOLD = 60


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    for lat in (lat1, lat2):
        if not -90 <= lat <= 90:
            raise ValueError(f"invalid latitude {lat}")
    for lon in (lon1, lon2):
        if not -180 <= lon <= 180:
            raise ValueError(f"invalid longitude {lon}")
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def geo_for(facility: Facility, lat: float, lon: float) -> GeoResult:
    km = haversine_km(lat, lon, facility.latitude, facility.longitude)
    drive_km = km * ROAD_FACTOR
    transit_ok = facility.transit_score >= TRANSIT_ACCESS_THRESHOLD
    return GeoResult(
        facility_id=facility.id,
        straight_km=round(km, 2),
        est_driving_km=round(drive_km, 2),
        est_driving_minutes=max(1, round(drive_km / AVG_URBAN_DRIVE_KMH * 60)),
        est_transit_minutes=max(5, round(drive_km / AVG_TRANSIT_KMH * 60) + 8) if transit_ok else None,
        transit_accessible=transit_ok,
    )


def within_radius(facilities: list[Facility], lat: float, lon: float, radius_km: float) -> list[tuple[Facility, GeoResult]]:
    """Facilities whose straight-line distance is <= radius_km (boundary inclusive), nearest first."""
    out = []
    for f in facilities:
        if haversine_km(lat, lon, f.latitude, f.longitude) <= radius_km + 1e-9:
            out.append((f, geo_for(f, lat, lon)))
    out.sort(key=lambda fg: (fg[1].straight_km, fg[0].id))
    return out
