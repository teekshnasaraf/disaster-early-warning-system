"""Validated destination records for future evacuation-support workflows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import math
from types import MappingProxyType
from typing import Iterable, Mapping


class DestinationType(str, Enum):
    """Supported categories for a designated destination."""

    SHELTER = "shelter"
    ASSEMBLY_POINT = "assembly_point"
    MEDICAL_FACILITY = "medical_facility"
    OTHER = "other"


@dataclass(frozen=True)
class Coordinates:
    """A validated geographic point in decimal degrees."""

    latitude: float
    longitude: float

    def __post_init__(self) -> None:
        for name, value, lower, upper in (
            ("latitude", self.latitude, -90, 90),
            ("longitude", self.longitude, -180, 180),
        ):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{name} must be a finite number")
            try:
                is_finite = math.isfinite(value)
            except OverflowError:
                is_finite = False
            if not is_finite:
                raise ValueError(f"{name} must be a finite number")
            if not lower <= value <= upper:
                raise ValueError(f"{name} must be between {lower} and {upper}")
            object.__setattr__(self, name, float(value))


@dataclass(frozen=True)
class Destination:
    """A destination record; ``None`` capacity/availability means unknown.

    Data source ``"unknown"`` and ``last_updated=None`` explicitly indicate
    missing provenance or freshness information rather than verified status.
    """

    identifier: str
    name: str
    coordinates: Coordinates
    destination_type: DestinationType
    data_source: str = "unknown"
    last_updated: datetime | None = None
    capacity: int | None = None
    available: bool | None = None

    def __post_init__(self) -> None:
        for field_name in ("identifier", "name", "data_source"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be a non-empty string")
        if not isinstance(self.coordinates, Coordinates):
            raise ValueError("coordinates must be a Coordinates instance")
        if not isinstance(self.destination_type, DestinationType):
            raise ValueError("destination_type must be a DestinationType")
        if self.capacity is not None and (
            isinstance(self.capacity, bool)
            or not isinstance(self.capacity, int)
            or self.capacity < 0
        ):
            raise ValueError("capacity must be a non-negative integer or None")
        if self.available is not None and not isinstance(self.available, bool):
            raise ValueError("available must be a boolean or None")
        if self.last_updated is not None and (
            not isinstance(self.last_updated, datetime)
            or self.last_updated.tzinfo is None
            or self.last_updated.utcoffset() is None
        ):
            raise ValueError("last_updated must be a timezone-aware datetime or None")


class DuplicateDestinationError(ValueError):
    """Raised when a catalog contains duplicate destination identifiers."""


class DestinationCatalog:
    """An immutable snapshot of destinations indexed by unique identifier."""

    def __init__(self, destinations: Iterable[Destination]) -> None:
        by_identifier: dict[str, Destination] = {}
        for destination in destinations:
            if not isinstance(destination, Destination):
                raise ValueError("all catalog entries must be Destination instances")
            if destination.identifier in by_identifier:
                raise DuplicateDestinationError(
                    f"duplicate destination identifier: {destination.identifier}"
                )
            by_identifier[destination.identifier] = destination
        self._by_identifier: Mapping[str, Destination] = MappingProxyType(by_identifier)
        self._destinations = tuple(by_identifier.values())

    @property
    def destinations(self) -> tuple[Destination, ...]:
        """Return catalog entries in their supplied order."""
        return self._destinations

    def get(self, identifier: str) -> Destination | None:
        """Return a destination by identifier, or ``None`` when not found."""
        return self._by_identifier.get(identifier)
