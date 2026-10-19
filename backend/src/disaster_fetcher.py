"""Fetch and normalize earthquake events from a USGS GeoJSON feed."""

from __future__ import annotations

import json
import math
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_FEED_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson"
DEFAULT_TIMEOUT_SECONDS = 10.0


class EarthquakeFeedError(Exception):
    """Raised when the earthquake feed cannot be fetched or parsed."""


def _normalize_event(feature: Any) -> dict[str, Any]:
    if not isinstance(feature, dict):
        raise EarthquakeFeedError("Feed feature must be an object")

    properties = feature.get("properties")
    geometry = feature.get("geometry")
    if not isinstance(properties, dict) or not isinstance(geometry, dict):
        raise EarthquakeFeedError("Feed feature is missing properties or geometry")

    event_id = feature.get("id")
    if not isinstance(event_id, str) or not event_id.strip():
        raise EarthquakeFeedError("Earthquake event is missing a valid id")

    magnitude = properties.get("mag")
    if (
        isinstance(magnitude, bool)
        or not isinstance(magnitude, (int, float))
        or not math.isfinite(magnitude)
    ):
        raise EarthquakeFeedError(f"Earthquake event {event_id} has an invalid magnitude")

    timestamp = properties.get("time")
    if (
        isinstance(timestamp, bool)
        or not isinstance(timestamp, (int, float))
        or not math.isfinite(timestamp)
    ):
        raise EarthquakeFeedError(f"Earthquake event {event_id} has an invalid timestamp")

    coordinates = geometry.get("coordinates")
    if not isinstance(coordinates, list) or len(coordinates) < 2:
        raise EarthquakeFeedError(f"Earthquake event {event_id} has invalid coordinates")
    longitude, latitude = coordinates[:2]
    if any(
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        for value in (longitude, latitude)
    ):
        raise EarthquakeFeedError(f"Earthquake event {event_id} has invalid coordinates")
    if not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
        raise EarthquakeFeedError(f"Earthquake event {event_id} has out-of-range coordinates")

    place = properties.get("place")
    if not isinstance(place, str):
        place = "Unknown location"

    return {
        "id": event_id.strip(),
        "magnitude": float(magnitude),
        "place": place,
        "timestamp_ms": int(timestamp),
        "coordinates": {"longitude": float(longitude), "latitude": float(latitude)},
    }


def parse_earthquake_feed(payload: Any) -> list[dict[str, Any]]:
    """Validate a USGS FeatureCollection and return normalized events."""
    if not isinstance(payload, dict) or payload.get("type") != "FeatureCollection":
        raise EarthquakeFeedError("Feed response must be a GeoJSON FeatureCollection")

    features = payload.get("features")
    if not isinstance(features, list):
        raise EarthquakeFeedError("Feed FeatureCollection must contain a features list")

    return [_normalize_event(feature) for feature in features]


def fetch_earthquakes(
    feed_url: str | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> list[dict[str, Any]]:
    """Fetch and normalize events; the URL defaults to USGS all-day feed or USGS_FEED_URL."""
    selected_url = feed_url or os.environ.get("USGS_FEED_URL", DEFAULT_FEED_URL)
    if not isinstance(selected_url, str) or not selected_url.startswith(("https://", "http://")):
        raise ValueError("feed_url must be an HTTP or HTTPS URL")
    if not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be greater than zero")

    request = Request(selected_url, headers={"Accept": "application/geo+json, application/json"})
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError) as error:
        raise EarthquakeFeedError(f"Unable to retrieve earthquake feed: {error}") from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise EarthquakeFeedError("Earthquake feed did not contain valid UTF-8 JSON") from error

    return parse_earthquake_feed(payload)