from datetime import datetime, timedelta, timezone
import unittest

from event_quality import FreshnessPolicy, process_events
from disaster_fetcher import parse_earthquake_feed


NOW = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)
NOW_MS = int(NOW.timestamp() * 1000)


def observed(source_id="event-1", timestamp_ms=NOW_MS, updated_ms=None, **extra):
    event = {
        "source": "USGS",
        "source_id": source_id,
        "timestamp_ms": timestamp_ms,
        "magnitude": 2.0,
    }
    if updated_ms is not None:
        event["updated_ms"] = updated_ms
    event.update(extra)
    return event


class EventQualityTests(unittest.TestCase):
    def test_accepts_fresh_record(self):
        result = process_events([observed()], now=NOW)

        self.assertEqual(result["accepted"], [observed()])
        self.assertEqual(result["stale"], [])
        self.assertEqual(result["rejected"], [])

    def test_accepts_normalized_fetcher_event_shape(self):
        payload = {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "id": "usgs-example",
                "properties": {"mag": None, "time": NOW_MS, "updated": NOW_MS},
                "geometry": {"type": "Point", "coordinates": [-120, 40, 8]},
            }],
        }
        normalized = parse_earthquake_feed(payload)

        result = process_events(normalized, now=NOW)

        self.assertEqual(result["accepted"], normalized)

    def test_marks_record_older_than_configured_limit_stale(self):
        old_event = observed(timestamp_ms=NOW_MS - 3_600_000)
        result = process_events(
            [old_event],
            policy=FreshnessPolicy(max_age=timedelta(minutes=30)),
            now=NOW,
        )

        self.assertEqual(result["accepted"], [])
        self.assertEqual(result["stale"][0]["source_id"], "event-1")

    def test_recent_update_does_not_make_old_event_fresh(self):
        event = observed(timestamp_ms=NOW_MS - 86_400_000, updated_ms=NOW_MS)

        result = process_events(
            [event],
            policy=FreshnessPolicy(max_age=timedelta(minutes=30)),
            now=NOW,
        )

        self.assertEqual(result["accepted"], [])
        self.assertEqual(result["stale"][0]["source_id"], "event-1")

    def test_duplicate_identifier_keeps_newest_update(self):
        original = observed(updated_ms=NOW_MS - 10_000, version="old")
        updated = observed(updated_ms=NOW_MS, version="new")

        result = process_events([original, updated], now=NOW)

        self.assertEqual(result["accepted"], [updated])
        self.assertEqual(result["duplicates"][0]["action"], "replaced_by_newer_record")

    def test_invalid_future_duplicate_cannot_shadow_valid_record(self):
        invalid_future = observed(timestamp_ms=NOW_MS + 600_000, version="invalid")
        valid = observed(timestamp_ms=NOW_MS, version="valid")

        result = process_events(
            [invalid_future, valid],
            policy=FreshnessPolicy(future_tolerance=timedelta(minutes=2)),
            now=NOW,
        )

        self.assertEqual(result["accepted"], [valid])
        self.assertEqual(len(result["rejected"]), 1)
        self.assertEqual(result["duplicates"], [])

    def test_invalid_future_update_cannot_shadow_valid_record(self):
        invalid_update = observed(updated_ms=NOW_MS + 600_000, version="invalid")
        valid = observed(version="valid")

        result = process_events(
            [invalid_update, valid],
            policy=FreshnessPolicy(future_tolerance=timedelta(minutes=2)),
            now=NOW,
        )

        self.assertEqual(result["accepted"], [valid])
        self.assertEqual(len(result["rejected"]), 1)
        self.assertEqual(result["duplicates"], [])

    def test_invalid_timestamp_duplicate_cannot_shadow_valid_record(self):
        invalid_timestamp = observed(timestamp_ms=float("nan"), version="invalid")
        valid = observed(version="valid")

        result = process_events([invalid_timestamp, valid], now=NOW)

        self.assertEqual(result["accepted"], [valid])
        self.assertEqual(len(result["rejected"]), 1)
        self.assertEqual(result["duplicates"], [])

    def test_duplicate_tie_keeps_first_record(self):
        first = observed(version="first")
        second = observed(version="second")

        result = process_events([first, second], now=NOW)

        self.assertEqual(result["accepted"], [first])
        self.assertEqual(result["duplicates"][0]["action"], "discarded_duplicate")

    def test_same_identifier_from_distinct_sources_is_not_duplicate(self):
        usgs = observed()
        other = observed(source_id="event-1", source="OtherFeed")

        result = process_events([usgs, other], now=NOW)

        self.assertEqual(len(result["accepted"]), 2)
        self.assertEqual(result["duplicates"], [])

    def test_rejects_missing_identity_or_timestamp(self):
        missing_source = observed()
        del missing_source["source"]
        missing_id = observed()
        del missing_id["source_id"]
        missing_time = observed()
        del missing_time["timestamp_ms"]

        result = process_events([missing_source, missing_id, missing_time], now=NOW)

        self.assertEqual(result["accepted"], [])
        self.assertEqual(len(result["rejected"]), 3)

    def test_rejects_non_finite_fractional_and_unrepresentable_timestamps(self):
        invalid = [
            observed(timestamp_ms=float("nan")),
            observed(timestamp_ms=float("inf")),
            observed(timestamp_ms=NOW_MS + 0.5),
            observed(timestamp_ms=10**30),
            observed(timestamp_ms=10**10000),
            observed(timestamp_ms=NOW_MS, updated_ms=10**10000),
        ]

        result = process_events(invalid, now=NOW)

        self.assertEqual(result["accepted"], [])
        self.assertEqual(len(result["rejected"]), len(invalid))

    def test_rejects_future_event_beyond_configured_clock_skew(self):
        result = process_events(
            [observed(timestamp_ms=NOW_MS + 600_000)],
            policy=FreshnessPolicy(future_tolerance=timedelta(minutes=2)),
            now=NOW,
        )

        self.assertEqual(result["accepted"], [])
        self.assertIn("future", result["rejected"][0]["reason"])

    def test_old_event_revision_remains_stale_based_on_origin_time(self):
        result = process_events(
            [observed(timestamp_ms=NOW_MS - 3_600_000, updated_ms=NOW_MS)],
            policy=FreshnessPolicy(
                max_age=timedelta(minutes=30),
                future_tolerance=timedelta(minutes=5),
            ),
            now=NOW,
        )

        self.assertEqual(result["accepted"], [])
        self.assertEqual(result["stale"][0]["source_id"], "event-1")

    def test_rejects_update_timestamp_in_future_beyond_clock_tolerance(self):
        result = process_events(
            [observed(updated_ms=NOW_MS + 600_000)],
            policy=FreshnessPolicy(future_tolerance=timedelta(minutes=2)),
            now=NOW,
        )

        self.assertEqual(result["accepted"], [])
        self.assertIn("update timestamp", result["rejected"][0]["reason"])

    def test_requires_timezone_aware_current_time(self):
        with self.assertRaises(ValueError):
            process_events([], now=datetime(2026, 10, 19))

    def test_validates_freshness_policy(self):
        with self.assertRaises(ValueError):
            FreshnessPolicy(max_age=timedelta(0))
        with self.assertRaises(ValueError):
            FreshnessPolicy(future_tolerance=timedelta(seconds=-1))


if __name__ == "__main__":
    unittest.main()