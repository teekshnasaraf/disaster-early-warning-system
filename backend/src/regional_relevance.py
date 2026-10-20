"""Deterministic, preliminary regional relevance assessment for Tamil Nadu."""

from __future__ import annotations

from dataclasses import dataclass
import math
from collections.abc import Mapping
from typing import Any

from impact_estimation import ImpactParameters, estimate_impact, haversine_distance_km

REGIONAL_RELEVANCE_STATUSES = (
    "inside_assessment_area",
    "within_heuristic_radius",
    "outside_heuristic_radius",
    "unknown",
)
ALERTABLE_REGIONAL_RELEVANCE_STATUSES = frozenset(REGIONAL_RELEVANCE_STATUSES[:2])


@dataclass(frozen=True)
class TamilNaduAssessmentArea:
    """Configurable rectangular assessment envelope, not an official boundary."""

    south: float = 8.0
    west: float = 76.2
    north: float = 13.6
    east: float = 80.4

    def __post_init__(self) -> None:
        for name in ("south", "west", "north", "east"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{name} must be a finite number")
            try:
                finite = math.isfinite(value)
            except OverflowError:
                finite = False
            if not finite:
                raise ValueError(f"{name} must be a finite number")
            object.__setattr__(self, name, float(value))

        if not -90 <= self.south < self.north <= 90:
            raise ValueError("assessment latitude bounds must be ordered within -90 to 90")
        if not -180 <= self.west < self.east <= 180:
            raise ValueError("assessment longitude bounds must be ordered within -180 to 180")


DEFAULT_TAMIL_NADU_AREA = TamilNaduAssessmentArea()


def _event_coordinates(event: Mapping[str, Any]) -> tuple[float, float]:
    coordinates = event.get("coordinates")
    if isinstance(coordinates, Mapping):
        point = {
            "latitude": coordinates.get("latitude"),
            "longitude": coordinates.get("longitude"),
        }
    else:
        point = {
            "latitude": event.get("latitude"),
            "longitude": event.get("longitude"),
        }
    haversine_distance_km(point, point)
    return float(point["latitude"]), float(point["longitude"])


def _distance_to_area(
    latitude: float,
    longitude: float,
    area: TamilNaduAssessmentArea,
) -> tuple[float, dict[str, float]]:
    if area.south <= latitude <= area.north and area.west <= longitude <= area.east:
        return 0.0, {"latitude": latitude, "longitude": longitude}

    candidates: list[dict[str, float]] = []
    clamped_longitude = min(area.east, max(area.west, longitude))
    for edge_latitude in (area.south, area.north):
        candidates.append(
            {"latitude": edge_latitude, "longitude": clamped_longitude}
        )

    latitude_radians = math.radians(latitude)
    for edge_longitude in (area.west, area.east):
        longitude_delta = math.radians(longitude - edge_longitude)
        nearest_latitude = math.degrees(
            math.atan2(
                math.sin(latitude_radians),
                math.cos(latitude_radians) * math.cos(longitude_delta),
            )
        )
        candidates.append(
            {
                "latitude": min(area.north, max(area.south, nearest_latitude)),
                "longitude": edge_longitude,
            }
        )

    event_point = {"latitude": latitude, "longitude": longitude}
    nearest_point = min(
        candidates,
        key=lambda candidate: haversine_distance_km(event_point, candidate),
    )
    return haversine_distance_km(event_point, nearest_point), nearest_point


def assess_tamil_nadu_relevance(
    event: Mapping[str, Any],
    impact_parameters: ImpactParameters,
    area: TamilNaduAssessmentArea = DEFAULT_TAMIL_NADU_AREA,
) -> dict[str, Any]:
    """Assess spatial relevance separately from magnitude-based risk labels.

    Events outside the configured rectangular envelope are compared with the
    existing heuristic radius. Missing or invalid inputs produce an explicit
    ``unknown`` result rather than a threat or risk classification.
    """
    if not isinstance(impact_parameters, ImpactParameters):
        raise ValueError("impact_parameters must be an ImpactParameters instance")
    if not isinstance(area, TamilNaduAssessmentArea):
        raise ValueError("area must be a TamilNaduAssessmentArea")
    if not isinstance(event, Mapping):
        return {
            "area": "tamil_nadu",
            "status": "unknown",
            "distance_km": None,
            "nearest_point": None,
            "impact_radius_km": None,
            "reason": "event must be a mapping",
        }

    try:
        latitude, longitude = _event_coordinates(event)
    except ValueError as error:
        return {
            "area": "tamil_nadu",
            "status": "unknown",
            "distance_km": None,
            "nearest_point": None,
            "impact_radius_km": None,
            "reason": f"coordinates are unavailable or invalid: {error}",
        }

    distance_km, nearest_point = _distance_to_area(latitude, longitude, area)
    try:
        radius_km = estimate_impact(event, impact_parameters)["radius_km"]
        radius_error = None
    except ValueError as error:
        radius_km = None
        radius_error = str(error)

    if distance_km == 0:
        status = "inside_assessment_area"
        reason = radius_error
    elif radius_km is None:
        status = "unknown"
        reason = radius_error or "heuristic radius is unavailable"
    elif distance_km <= radius_km:
        status = "within_heuristic_radius"
        reason = None
    else:
        status = "outside_heuristic_radius"
        reason = None

    return {
        "area": "tamil_nadu",
        "status": status,
        "distance_km": distance_km,
        "nearest_point": nearest_point,
        "impact_radius_km": radius_km,
        "reason": reason,
    }
