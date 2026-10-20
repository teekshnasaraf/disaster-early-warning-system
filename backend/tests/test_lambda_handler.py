from datetime import datetime, timezone
import json
import os
import unittest
from unittest.mock import patch

from disaster_fetcher import EarthquakeFeedError
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
