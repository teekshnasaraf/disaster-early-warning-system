from datetime import datetime, timezone
import json
import os
import unittest
from unittest.mock import patch

from disaster_fetcher import EarthquakeFeedError, parse_earthquake_feed
from lambda_handler import LambdaConfig, LambdaFeedError, handler


def current_observation():
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    return {
        "id": "usgs-lambda-test",
        "source": "USGS",
        "source_id": "usgs-lambda-test",
        "magnitude": 0,
        "timestamp_ms": now_ms,
        "updated_ms": now_ms,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "coordinates": {"longitude": -70.0, "latitude": -20.0},
        "depth_km": 5.0,
    }


def feed_observation(source_id, magnitude):
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    payload = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": source_id,
                "properties": {
                    "mag": magnitude,
                    "place": "Test location",
                    "time": now_ms,
                },
                "geometry": {
                    "type": "Point",
                    "coordinates": [-70.0, -20.0, 5.0],
                },
            }
        ],
    }
    return parse_earthquake_feed(payload)[0]


class LambdaHandlerTests(unittest.TestCase):
    def test_success_uses_server_configuration_and_returns_json_summary(self):
        event = {"feed_url": "https://attacker.example/feed.geojson"}
        with (
            patch.dict(
                os.environ,
                {
                    "USGS_FEED_URL": "https://configured.example/feed.geojson",
                    "USGS_TIMEOUT_SECONDS": "4.5",
                },
                clear=True,
            ),
            patch("lambda_handler.fetch_earthquakes", return_value=[current_observation()]) as fetch,
            self.assertLogs("lambda_handler", level="INFO") as captured,
        ):
            result = handler(event, object())

        fetch.assert_called_once_with(
            feed_url="https://configured.example/feed.geojson",
            timeout=4.5,
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["summary"]["received"], 1)
        self.assertEqual(result["summary"]["accepted"], 1)
        self.assertEqual(json.loads(json.dumps(result))["status"], "ok")
        self.assertEqual(len(captured.records), 1)
        self.assertNotIn("attacker.example", captured.output[0])
        self.assertNotIn("usgs-lambda-test", captured.output[0])

    def test_negative_feed_record_does_not_abort_valid_lambda_processing(self):
        observations = [
            feed_observation("negative", -0.4),
            current_observation(),
        ]
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("lambda_handler.fetch_earthquakes", return_value=observations),
            self.assertLogs("lambda_handler", level="INFO"),
        ):
            result = handler({}, None)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["summary"]["received"], 2)
        self.assertEqual(result["summary"]["accepted"], 1)
        self.assertEqual(result["summary"]["rejected"], 1)
        json.dumps(result, allow_nan=False)

    def test_all_negative_feed_records_return_zero_accepted_and_rejected_count(self):
        observations = [
            feed_observation("negative-one", -0.1),
            feed_observation("negative-two", -1.0),
        ]
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("lambda_handler.fetch_earthquakes", return_value=observations),
            self.assertLogs("lambda_handler", level="INFO"),
        ):
            result = handler({}, None)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["summary"]["received"], 2)
        self.assertEqual(result["summary"]["accepted"], 0)
        self.assertEqual(result["summary"]["rejected"], 2)
        json.dumps(result, allow_nan=False)

    def test_feed_failure_raises_controlled_error_instead_of_success(self):
        with (
            patch.dict(os.environ, {}, clear=True),
            patch(
                "lambda_handler.fetch_earthquakes",
                side_effect=EarthquakeFeedError("upstream unavailable"),
            ),
        ):
            with self.assertRaisesRegex(LambdaFeedError, "upstream unavailable"):
                handler({}, None)

    def test_environment_configuration_requires_valid_timeout_and_url(self):
        for environ in (
            {"USGS_TIMEOUT_SECONDS": "nan"},
            {"USGS_TIMEOUT_SECONDS": "0"},
            {"USGS_FEED_URL": "  "},
        ):
            with self.subTest(environ=environ), self.assertRaises(ValueError):
                LambdaConfig.from_environment(environ)


if __name__ == "__main__":
    unittest.main()
