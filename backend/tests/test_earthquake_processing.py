from datetime import datetime, timedelta, timezone
import json
import unittest

from disaster_fetcher import parse_earthquake_feed
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
                "regional_relevance_counts": {
                    "inside_assessment_area": 0,
                    "within_heuristic_radius": 0,
                    "outside_heuristic_radius": 2,
                    "unknown": 1,
                },
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

    def test_negative_record_from_feed_is_rejected_alongside_valid_records(self):
        timestamp_ms = int(NOW.timestamp() * 1000)
        payload = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "id": source_id,
                    "properties": {
                        "mag": magnitude,
                        "place": "Test location",
                        "time": timestamp_ms,
                    },
                    "geometry": {
                        "type": "Point",
                        "coordinates": [-70.0, -20.0, 8.0],
                    },
                }
                for source_id, magnitude in (("negative", -0.4), ("valid", 4.2))
            ],
        }

        result = process_observations(parse_earthquake_feed(payload), now=NOW)

        self.assertEqual(result["summary"]["received"], 2)
        self.assertEqual(result["summary"]["accepted"], 1)
        self.assertEqual(result["summary"]["rejected"], 1)
        self.assertEqual(result["accepted"][0]["event"]["source_id"], "valid")
        self.assertEqual(result["accepted"][0]["risk"]["level"], "moderate")
        self.assertEqual(result["rejected"][0]["source_id"], "negative")
        self.assertIn("must not be negative", result["rejected"][0]["reason"])
        json.dumps(result, allow_nan=False)

    def test_all_negative_records_are_rejected_with_serializable_summary(self):
        result = process_observations(
            [
                observation("negative-one", magnitude=-0.1),
                observation("negative-two", magnitude=-1.0),
            ],
            now=NOW,
        )

        self.assertEqual(result["summary"]["received"], 2)
        self.assertEqual(result["summary"]["accepted"], 0)
        self.assertEqual(result["summary"]["rejected"], 2)
        self.assertEqual(len(result["rejected"]), 2)
        json.dumps(result, allow_nan=False)

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

    def test_regional_relevance_is_separate_from_risk_classification(self):
        event = observation("near-tamil-nadu", magnitude=3.0)
        event["coordinates"] = {"latitude": 10.0, "longitude": 80.5}

        result = process_observations([event], now=NOW)
        accepted = result["accepted"][0]

        self.assertEqual(accepted["risk"]["level"], "low")
        self.assertEqual(
            accepted["regional_relevance"]["status"],
            "within_heuristic_radius",
        )
        self.assertNotIn("tamil_nadu", accepted["risk"])

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
