from datetime import datetime, timedelta, timezone
import json
import unittest

from earthquake_processing import ProcessingConfig, process_observations


NOW = datetime(2026, 1, 2, 12, 0, tzinfo=timezone.utc)


def observation(source_id, *, magnitude=3.0, timestamp=NOW, updated=None, coordinates=True):
    timestamp_ms = int(timestamp.timestamp() * 1000)
    event = {
        "id": source_id,
        "source": "USGS",
        "source_id": source_id,
        "magnitude": magnitude,
        "timestamp_ms": timestamp_ms,
        "updated_ms": int((updated or timestamp).timestamp() * 1000),
        "timestamp_utc": timestamp.isoformat().replace("+00:00", "Z"),
    }
    if coordinates:
        event["coordinates"] = {"longitude": -70.0, "latitude": -20.0}
        event["depth_km"] = 8.0
    return event


class EarthquakeProcessingTests(unittest.TestCase):
    def test_quality_filters_precede_risk_and_impact_with_accurate_counts(self):
        original = observation("duplicate", magnitude=4.5)
        newer = observation(
            "duplicate",
            magnitude=4.5,
            updated=NOW + timedelta(minutes=1),
        )
        records = [
            observation("zero", magnitude=0),
            observation("unknown", magnitude=None, coordinates=False),
            observation("stale", timestamp=NOW - timedelta(days=2)),
            original,
            newer,
            {"source": "USGS", "timestamp_ms": int(NOW.timestamp() * 1000)},
            observation("negative", magnitude=-0.1),
        ]

        result = process_observations(records, now=NOW)

        self.assertEqual(
            result["summary"],
            {
                "received": 7,
                "accepted": 3,
                "stale": 1,
                "duplicates": 1,
                "rejected": 2,
                "risk_counts": {"low": 1, "moderate": 1, "high": 0, "unknown": 1},
                "impact_available": 2,
                "impact_unavailable": 1,
            },
        )
        accepted_ids = [record["event"]["source_id"] for record in result["accepted"]]
        self.assertEqual(accepted_ids, ["zero", "unknown", "duplicate"])
        self.assertEqual(result["accepted"][0]["risk"]["level"], "low")
        self.assertEqual(result["accepted"][1]["risk"]["level"], "unknown")
        self.assertIsNone(result["accepted"][1]["impact"])
        self.assertEqual(len(result["rejected"]), 2)
        json.dumps(result, allow_nan=False)

    def test_negative_magnitude_is_rejected_without_crashing_processing(self):
        result = process_observations(
            [observation("negative", magnitude=-1.0)],
            config=ProcessingConfig(),
            now=NOW,
        )

        self.assertEqual(result["summary"]["accepted"], 0)
        self.assertEqual(result["summary"]["rejected"], 1)
        self.assertIn("must not be negative", result["rejected"][0]["reason"])

    def test_zero_and_positive_magnitudes_are_processed(self):
        result = process_observations(
            [
                observation("zero", magnitude=0),
                observation("positive", magnitude=2.5),
            ],
            now=NOW,
        )

        self.assertEqual(result["summary"]["accepted"], 2)
        self.assertEqual(result["summary"]["rejected"], 0)
        self.assertEqual(
            [record["risk"]["level"] for record in result["accepted"]],
            ["low", "low"],
        )

    def test_invalid_individual_mapping_is_reported_without_hiding_valid_records(self):
        valid = observation("valid")
        result = process_observations(
            [valid, {"source": "USGS", "source_id": "bad", "timestamp_ms": float("nan")}],
            now=NOW,
        )

        self.assertEqual(result["summary"]["accepted"], 1)
        self.assertEqual(result["summary"]["rejected"], 1)
        json.dumps(result, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
