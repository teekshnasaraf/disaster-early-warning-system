from datetime import datetime, timezone
import json
import os
import unittest
from unittest.mock import patch

from disaster_fetcher import EarthquakeFeedError, parse_earthquake_feed
from lambda_handler import LambdaConfig, LambdaFeedError, handler


def current_observation(
    magnitude=0,
    latitude=-20.0,
    longitude=-70.0,
    source_id="usgs-lambda-test",
):
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    return {
        "id": source_id,
        "source": "USGS",
        "source_id": source_id,
        "magnitude": magnitude,
        "timestamp_ms": now_ms,
        "updated_ms": now_ms,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "coordinates": {"longitude": longitude, "latitude": latitude},
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
        self.assertEqual(
            result["summary"]["regional_relevance_counts"],
            {
                "inside_assessment_area": 0,
                "within_heuristic_radius": 0,
                "outside_heuristic_radius": 1,
                "unknown": 0,
            },
        )
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

    def test_alerts_are_disabled_by_default(self):
        with (
            patch.dict(os.environ, {}, clear=True),
            patch(
                "lambda_handler.fetch_earthquakes",
                return_value=[
                    current_observation(magnitude=7.0, latitude=10.0, longitude=78.0)
                ],
            ),
            patch("lambda_handler._publish_sns") as publish,
            self.assertLogs("lambda_handler", level="INFO"),
        ):
            result = handler({}, None)

        self.assertFalse(LambdaConfig.from_environment().alerts_enabled)
        self.assertEqual(result["status"], "ok")
        publish.assert_not_called()

    def test_enabled_alert_requires_topic_configuration(self):
        with (
            patch.dict(os.environ, {"ALERTS_ENABLED": "true"}, clear=True),
            patch("lambda_handler.fetch_earthquakes") as fetch,
        ):
            with self.assertRaisesRegex(ValueError, "SNS_TOPIC_ARN is required"):
                handler({}, None)

        fetch.assert_not_called()

    def test_alert_eligibility_requires_configured_magnitude_and_region(self):
        observations = [
            current_observation(
                magnitude=5.9,
                latitude=10.0,
                longitude=78.0,
                source_id="below-threshold",
            ),
            current_observation(
                magnitude=7.0,
                latitude=-20.0,
                longitude=-70.0,
                source_id="outside-region",
            ),
            current_observation(
                magnitude=6.0,
                latitude=10.0,
                longitude=78.0,
                source_id="eligible",
            ),
        ]
        environment = {
            "ALERTS_ENABLED": "true",
            "SNS_TOPIC_ARN": "arn:aws:sns:ap-south-1:123456789012:alerts",
            "ALERT_MIN_MAGNITUDE": "6.0",
            "ALERT_RELEVANCE_STATUSES": "inside_assessment_area",
        }
        with (
            patch.dict(os.environ, environment, clear=True),
            patch("lambda_handler.fetch_earthquakes", return_value=observations),
            patch("lambda_handler._publish_sns") as publish,
            self.assertLogs("lambda_handler", level="INFO"),
        ):
            result = handler({}, None)

        self.assertEqual(result["summary"]["accepted"], 3)
        publish.assert_called_once()
        topic_arn, subject, message = publish.call_args.args
        self.assertEqual(topic_arn, environment["SNS_TOPIC_ARN"])
        self.assertEqual(
            subject,
            "Academic Demo: Tamil Nadu earthquake relevance",
        )
        payload = json.loads(message)
        self.assertEqual(payload["alert_type"], "academic_demonstration")
        self.assertIn("NOT AN OFFICIAL EMERGENCY WARNING", payload["disclaimer"])
        self.assertEqual(payload["magnitude"], 6.0)

    def test_sns_publishing_failure_is_surfaced(self):
        environment = {
            "ALERTS_ENABLED": "true",
            "SNS_TOPIC_ARN": "arn:aws:sns:ap-south-1:123456789012:alerts",
        }
        with (
            patch.dict(os.environ, environment, clear=True),
            patch(
                "lambda_handler.fetch_earthquakes",
                return_value=[
                    current_observation(magnitude=6.0, latitude=10.0, longitude=78.0)
                ],
            ),
            patch(
                "lambda_handler._publish_sns",
                side_effect=RuntimeError("SNS unavailable"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "SNS unavailable"):
                handler({}, None)


if __name__ == "__main__":
    unittest.main()
