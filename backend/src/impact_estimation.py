"""Configurable, preliminary earthquake impact-radius estimation.

This module contains only local geometry and project heuristic logic. Its output
is not a scientific impact prediction, damage boundary, or safety guidance.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping

EARTH_RADIUS_KM = 6371.0088


@dataclass(frozen=True)
class ImpactParameters:
    """Caller-supplied illustrative coefficients for the project heuristic.

    The radius formula is ``(base + magnitude_scale * max(magnitude, 0)) /
    (1 + depth_km / depth_scale)``. Coefficients are not validated scientific
    thresholds and must be chosen for the intended demonstration.
    """

    base_radius_km: float
    magnitude_scale_km: float
    depth_scale_km: float

    def __post_init__(self) -> None:
        values = (self.base_radius_km, self.magnitude_scale_km, self.depth_scale_km)
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) for value in values):
            raise ValueError("impact parameters must be finite numbers")
        if self.base_radius_km < 0 or self.magnitude_scale_km < 0:
            raise ValueError("radius coefficients must not be negative")
        if self.depth_scale_km <= 0:
            raise ValueError("depth_scale_km must be greater than zero")
        if self.base_radius_km == 0 and self.magnitude_scale_km == 0:
            raise ValueError("at least one radius coefficient must be greater than zero")


def _finite_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    return float(value)


def _validate_coordinates(latitude: Any, longitude: Any, label: str) -> tuple[float, float]:
    lat = _finite_number(latitude, f"{label} latitude")
    lon = _finite_number(longitude, f"{label} longitude")
    if not -90 <= lat <= 90:
        raise ValueError(f"{label} latitude must be between -90 and 90")
    if not -180 <= lon <= 180:
        raise ValueError(f"{label} longitude must be between -180 and 180")
    return lat, lon


def _event_coordinates(event: Mapping[str, Any]) -> tuple[float, float]:
    coordinates = event.get("coordinates")
    if isinstance(coordinates, Mapping):
        latitude, longitude = coordinates.get("latitude"), coordinates.get("longitude")
    else:
        latitude, longitude = event.get("latitude"), event.get("longitude")
    return _validate_coordinates(latitude, longitude, "event")


def _location_coordinates(location: Mapping[str, Any]) -> tuple[float, float]:
    coordinates = location.get("coordinates")
    if isinstance(coordinates, Mapping):
        latitude, longitude = coordinates.get("latitude"), coordinates.get("longitude")
    else:
        latitude, longitude = location.get("latitude"), location.get("longitude")
    return _validate_coordinates(latitude, longitude, "location")


def _bounding_box(latitude: float, longitude: float, radius_km: float) -> dict[str, float | bool]:
    angular_radius = radius_km / EARTH_RADIUS_KM
    if angular_radius >= math.pi:
        return {
            "south": -90.0,
            "west": -180.0,
            "north": 90.0,
            "east": 180.0,
            "crosses_antimeridian": False,
        }

    latitude_radians = math.radians(latitude)
    latitude_delta = math.degrees(angular_radius)
    south = max(-90.0, latitude - latitude_delta)
    north = min(90.0, latitude + latitude_delta)

    if south <= -90.0 or north >= 90.0:
        west, east, crosses_antimeridian = -180.0, 180.0, False
    else:
        longitude_cosine = (
            math.cos(angular_radius) - math.sin(latitude_radians) ** 2
        ) / math.cos(latitude_radians) ** 2
        longitude_delta = math.degrees(math.acos(max(-1.0, min(1.0, longitude_cosine))))
        raw_west = longitude - longitude_delta
        raw_east = longitude + longitude_delta
        west = ((raw_west + 180.0) % 360.0) - 180.0
        east = ((raw_east + 180.0) % 360.0) - 180.0
        crosses_antimeridian = raw_west < -180.0 or raw_east > 180.0

    return {
        "south": south,
        "west": west,
        "north": north,
        "east": east,
        "crosses_antimeridian": crosses_antimeridian,
    }


def estimate_impact(event: Mapping[str, Any], parameters: ImpactParameters) -> dict[str, Any]:
    """Return a preliminary radius and geographic bounding box for an event.

    Events may use the fetcher's ``coordinates`` mapping or top-level
    ``latitude``/``longitude`` fields. ``depth_km`` is optional and defaults to
    zero when absent. The returned estimate is a configurable project heuristic,
    not a validated prediction or a damage boundary.
    """
    if not isinstance(event, Mapping):
        raise ValueError("event must be a mapping")
    if not isinstance(parameters, ImpactParameters):
        raise ValueError("parameters must be an ImpactParameters instance")

    latitude, longitude = _event_coordinates(event)
    magnitude = _finite_number(event.get("magnitude"), "magnitude")
    if magnitude < 0:
        raise ValueError("magnitude must not be negative")
    raw_depth = event.get("depth_km", 0.0)
    depth_km = _finite_number(raw_depth, "depth_km")
    if depth_km < 0:
        raise ValueError("depth_km must not be negative")

    radius_km = (
        parameters.base_radius_km + parameters.magnitude_scale_km * magnitude
    ) / (1.0 + depth_km / parameters.depth_scale_km)
    if not math.isfinite(radius_km) or radius_km <= 0:
        raise ValueError("configured parameters must produce a finite positive radius")

    return {
        "center": {"latitude": latitude, "longitude": longitude},
        "radius_km": radius_km,
        "bounding_box": _bounding_box(latitude, longitude, radius_km),
    }


def haversine_distance_km(origin: Mapping[str, Any], destination: Mapping[str, Any]) -> float:
    """Calculate great-circle distance between two latitude/longitude mappings."""
    if not isinstance(origin, Mapping) or not isinstance(destination, Mapping):
        raise ValueError("origin and destination must be coordinate mappings")
    origin_lat, origin_lon = _location_coordinates(origin)
    destination_lat, destination_lon = _location_coordinates(destination)

    origin_lat_radians = math.radians(origin_lat)
    destination_lat_radians = math.radians(destination_lat)
    latitude_delta = destination_lat_radians - origin_lat_radians
    longitude_delta = math.radians(destination_lon - origin_lon)
    haversine = (
        math.sin(latitude_delta / 2.0) ** 2
        + math.cos(origin_lat_radians)
        * math.cos(destination_lat_radians)
        * math.sin(longitude_delta / 2.0) ** 2
    )
    central_angle = 2.0 * math.asin(math.sqrt(min(1.0, haversine)))
    return EARTH_RADIUS_KM * central_angle


def is_location_within_impact(candidate: Mapping[str, Any], estimate: Mapping[str, Any]) -> bool:
    """Return whether a candidate is within a previously calculated estimate."""
    if not isinstance(estimate, Mapping):
        raise ValueError("estimate must be a mapping")
    center = estimate.get("center")
    if not isinstance(center, Mapping):
        raise ValueError("estimate must contain a center mapping")
    radius_km = _finite_number(estimate.get("radius_km"), "radius_km")
    if radius_km <= 0:
        raise ValueError("radius_km must be greater than zero")
    return haversine_distance_km(center, candidate) <= radius_km