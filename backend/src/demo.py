"""Run a local, read-only demonstration of earthquake feed processing."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import sys
from typing import Any, Sequence

from disaster_fetcher import EarthquakeFeedError, fetch_earthquakes, parse_earthquake_feed
from earthquake_processing import ProcessingConfig, process_observations
from event_quality import FreshnessPolicy
from impact_estimation import ImpactParameters


def representative_sample_events(reference_time: datetime | None = None) -> list[dict[str, Any]]:
    """Return representative normalized events for offline pipeline demonstration."""
    now = reference_time or datetime.now(timezone.utc)
    now_ms = int(now.timestamp() * 1000)
    return [
        {
            "id": "sample-event-1",
            "source": "USGS",
            "source_id": "sample-event-1",
            "magnitude": 5.4,
            "place": "12 km NW of Sample City, CA",
            "timestamp_ms": now_ms - 15 * 60 * 1000,
            "timestamp_utc": (now - timedelta(minutes=15)).isoformat().replace("+00:00", "Z"),
            "updated_ms": now_ms - 5 * 60 * 1000,
            "updated_utc": (now - timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
            "depth_km": 10.0,
            "coordinates": {"longitude": -121.8, "latitude": 36.8},
        },
        {
            "id": "sample-event-2",
            "source": "USGS",
            "source_id": "sample-event-2",
            "magnitude": 2.3,
            "place": "5 km ESE of Example Town, NV",
            "timestamp_ms": now_ms - 45 * 60 * 1000,
            "timestamp_utc": (now - timedelta(minutes=45)).isoformat().replace("+00:00", "Z"),
            "updated_ms": now_ms - 40 * 60 * 1000,
            "updated_utc": (now - timedelta(minutes=40)).isoformat().replace("+00:00", "Z"),
            "depth_km": 6.5,
            "coordinates": {"longitude": -118.2, "latitude": 38.5},
        },
        {
            "id": "sample-event-3",
            "source": "USGS",
            "source_id": "sample-event-3",
            "magnitude": 6.8,
            "place": "Offshore Northern Region",
            "timestamp_ms": now_ms - 2 * 3600 * 1000,
            "timestamp_utc": (now - timedelta(hours=2)).isoformat().replace("+00:00", "Z"),
            "updated_ms": now_ms - 1 * 3600 * 1000,
            "updated_utc": (now - timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
            "depth_km": 15.0,
            "coordinates": {"longitude": -125.0, "latitude": 40.2},
        },
        {
            "id": "sample-event-4",
            "source": "USGS",
            "source_id": "sample-event-4",
            "magnitude": None,
            "place": "Uninstrumented Region",
            "timestamp_ms": now_ms - 30 * 60 * 1000,
            "timestamp_utc": (now - timedelta(minutes=30)).isoformat().replace("+00:00", "Z"),
            "updated_ms": now_ms - 25 * 60 * 1000,
            "updated_utc": (now - timedelta(minutes=25)).isoformat().replace("+00:00", "Z"),
            "depth_km": None,
            "coordinates": {"longitude": 0.0, "latitude": 0.0},
        },
    ]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch and summarize USGS earthquakes locally; no AWS or alerts are used."
    )
    parser.add_argument("--feed-url", help="USGS GeoJSON feed URL (defaults to USGS_FEED_URL or the all-day feed)")
    parser.add_argument("--max-age-hours", type=float, default=24.0, help="Maximum event age to accept (default: 24)")
    parser.add_argument("--future-tolerance-minutes", type=float, default=5.0, help="Allowed timestamp clock skew (default: 5)")
    parser.add_argument("--base-radius-km", type=float, default=10.0, help="Demo-only heuristic base radius coefficient")
    parser.add_argument("--magnitude-scale-km", type=float, default=5.0, help="Demo-only heuristic magnitude coefficient")
    parser.add_argument("--depth-scale-km", type=float, default=10.0, help="Demo-only heuristic depth coefficient")
    parser.add_argument("--limit", type=int, default=10, help="Maximum accepted events to display (default: 10)")
    parser.add_argument(
        "--sample-data",
        action="store_true",
        help="Use built-in representative sample events instead of fetching from the network",
    )
    parser.add_argument(
        "--fixture-file",
        help="Path to a local GeoJSON file to parse instead of fetching from the network",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.max_age_hours <= 0 or args.future_tolerance_minutes < 0:
        parser.error("freshness limits must be positive (future tolerance may be zero)")
    if args.limit < 1:
        parser.error("--limit must be at least 1")
    if args.sample_data and args.fixture_file:
        parser.error("cannot specify both --sample-data and --fixture-file")
    if (args.sample_data or args.fixture_file) and args.feed_url:
        parser.error("cannot specify --feed-url together with --sample-data or --fixture-file")

    try:
        freshness_policy = FreshnessPolicy(
            max_age=timedelta(hours=args.max_age_hours),
            future_tolerance=timedelta(minutes=args.future_tolerance_minutes),
        )
        impact_parameters = ImpactParameters(
            base_radius_km=args.base_radius_km,
            magnitude_scale_km=args.magnitude_scale_km,
            depth_scale_km=args.depth_scale_km,
        )
    except (OverflowError, ValueError) as error:
        parser.error(str(error))

    if args.sample_data:
        observations = representative_sample_events()
        source_description = "Built-in representative sample data (offline demo; no live network fetch was performed)"
    elif args.fixture_file:
        try:
            with open(args.fixture_file, "r", encoding="utf-8") as file:
                payload = json.load(file)
            observations = parse_earthquake_feed(payload)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, EarthquakeFeedError) as error:
            print(f"Unable to read or parse fixture file: {error}", file=sys.stderr)
            return 1
        source_description = f"Local fixture file '{args.fixture_file}' (offline demo; no live network fetch was performed)"
    else:
        try:
            observations = fetch_earthquakes(feed_url=args.feed_url)
        except (EarthquakeFeedError, ValueError) as error:
            print(f"Unable to fetch or validate earthquake feed: {error}", file=sys.stderr)
            print("Hint: Run with --sample-data to test the processing pipeline offline without network access.", file=sys.stderr)
            return 1
        source_description = f"Live USGS feed ({args.feed_url or 'default past-day all-earthquakes'})"

    result = process_observations(
        observations,
        config=ProcessingConfig(
            freshness_policy=freshness_policy,
            impact_parameters=impact_parameters,
        ),
    )
    print("Local USGS earthquake processing demo")
    print("Risk labels and impact radii below are project heuristics, not validated predictions.")
    print("No notifications, AWS resources, destinations, or evacuation routes are involved.")
    print(f"Data source: {source_description}")
    print(
        "Records: "
        f"{result['summary']['accepted']} accepted, {result['summary']['stale']} stale, "
        f"{result['summary']['duplicates']} duplicates, {result['summary']['rejected']} rejected"
    )

    if not result["accepted"]:
        print("No fresh accepted events to display.")
        return 0

    display_events = result["accepted"][:args.limit]
    for record in display_events:
        event = record["event"]
        magnitude = event.get("magnitude")
        magnitude_text = f"{magnitude:.1f}" if isinstance(magnitude, (int, float)) else "unknown"
        risk = record["risk"]
        place = event.get("place", "Unknown location")
        event_time = event.get("timestamp_utc", "timestamp unavailable")
        print(f"\n{event.get('source_id', event.get('id', 'unknown-id'))}: {place}")
        print(f"  Observed: {event_time}; magnitude: {magnitude_text}")
        print(f"  Heuristic risk: {risk['level']} ({risk['reason']})")

        estimate = record["impact"]
        if estimate is None:
            print(f"  Heuristic impact radius: unavailable ({record['impact_error']})")
        else:
            print(f"  Heuristic impact radius: approximately {estimate['radius_km']:.1f} km")

    if len(result["accepted"]) > len(display_events):
        print(f"\nDisplayed {len(display_events)} of {len(result['accepted'])} accepted events; use --limit to change this.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
