import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from disaster_fetcher import EarthquakeFeedError, fetch_earthquakes, parse_earthquake_feed


def representative_feed():
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": "us-test-123",
                "properties": {"mag": 5.2, "place": "10 km north of Example", "time": 1_760_000_000_000, "updated": 1_760_000_100_000},
                "geometry": {"type": "Point", "coordinates": [-122.5, 37.7, 8.1]},
            }
        ],
    }


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.body


class DisasterFetcherTests(unittest.TestCase):
    def test_parse_normalizes_representative_feed(self):
        events = parse_earthquake_feed(representative_feed())

        self.assertEqual(
            events,
            [
                {
                    "id": "us-test-123",
                    "source": "USGS",
                    "source_id": "us-test-123",
                    "magnitude": 5.2,
                    "place": "10 km north of Example",
                    "timestamp_ms": 1_760_000_000_000,
                    "timestamp_utc": "2025-10-09T08:53:20Z",
                    "updated_ms": 1_760_000_100_000,
                    "updated_utc": "2025-10-09T08:55:00Z",
                    "depth_km": 8.1,
                    "coordinates": {"longitude": -122.5, "latitude": 37.7},
                }
            ],
        )

    def test_missing_optional_place_uses_fallback(self):
        feed = representative_feed()
        del feed["features"][0]["properties"]["place"]

        self.assertEqual(parse_earthquake_feed(feed)[0]["place"], "Unknown location")

    def test_rejects_unexpected_feed_structure(self):
        with self.assertRaises(EarthquakeFeedError):
            parse_earthquake_feed({"type": "FeatureCollection", "features": {}})

    def test_rejects_invalid_required_coordinates(self):
        feed = representative_feed()
        feed["features"][0]["geometry"]["coordinates"] = [200, 91]

        with self.assertRaises(EarthquakeFeedError):
            parse_earthquake_feed(feed)

    def test_rejects_non_finite_feed_values(self):
        feed = representative_feed()
        feed["features"][0]["properties"]["mag"] = float("nan")

        with self.assertRaises(EarthquakeFeedError):
            parse_earthquake_feed(feed)

    def test_rejects_non_finite_and_oversized_coordinates(self):
        for longitude in (float("inf"), 10**10000):
            feed = representative_feed()
            feed["features"][0]["geometry"]["coordinates"] = [longitude, 37.7]
            with self.subTest(longitude_type=type(longitude).__name__), self.assertRaises(EarthquakeFeedError):
                parse_earthquake_feed(feed)

    def test_preserves_missing_magnitude_and_optional_depth(self):
        feed = representative_feed()
        feed["features"][0]["properties"]["mag"] = None
        feed["features"][0]["geometry"]["coordinates"] = [-122.5, 37.7]

        event = parse_earthquake_feed(feed)[0]

        self.assertIsNone(event["magnitude"])
        self.assertIsNone(event["depth_km"])

    def test_rejects_invalid_or_fractional_event_timestamps(self):
        for timestamp in (float("nan"), float("inf"), 1_760_000_000_000.5, 10**30):
            feed = representative_feed()
            feed["features"][0]["properties"]["time"] = timestamp
            with self.subTest(timestamp=timestamp), self.assertRaises(EarthquakeFeedError):
                parse_earthquake_feed(feed)

    def test_rejects_invalid_update_timestamp(self):
        feed = representative_feed()
        feed["features"][0]["properties"]["updated"] = "yesterday"

        with self.assertRaises(EarthquakeFeedError):
            parse_earthquake_feed(feed)

    def test_missing_update_timestamp_falls_back_to_event_time(self):
        feed = representative_feed()
        del feed["features"][0]["properties"]["updated"]

        event = parse_earthquake_feed(feed)[0]

        self.assertEqual(event["updated_ms"], event["timestamp_ms"])
        self.assertEqual(event["updated_utc"], event["timestamp_utc"])

    def test_rejects_non_finite_coordinates(self):
        feed = representative_feed()
        feed["features"][0]["geometry"]["coordinates"] = [float("inf"), 37.7]
        with self.assertRaises(EarthquakeFeedError):
            parse_earthquake_feed(feed)

    @patch("disaster_fetcher.urlopen")
    def test_fetches_configured_url_with_timeout_and_parses_json(self, mock_urlopen):
        mock_urlopen.return_value = FakeResponse(json.dumps(representative_feed()).encode())

        events = fetch_earthquakes("https://example.test/feed.geojson", timeout=3.0)

        self.assertEqual(events[0]["id"], "us-test-123")
        request = mock_urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "https://example.test/feed.geojson")
        self.assertEqual(mock_urlopen.call_args.kwargs["timeout"], 3.0)

    @patch("disaster_fetcher.urlopen", side_effect=HTTPError("https://example.test", 503, "Unavailable", {}, None))
    def test_http_errors_are_wrapped(self, _mock_urlopen):
        with self.assertRaises(EarthquakeFeedError):
            fetch_earthquakes("https://example.test/feed.geojson")

    @patch("disaster_fetcher.urlopen", side_effect=URLError("offline"))
    def test_network_errors_are_wrapped(self, _mock_urlopen):
        with self.assertRaises(EarthquakeFeedError):
            fetch_earthquakes("https://example.test/feed.geojson")

    @patch("disaster_fetcher.urlopen", return_value=FakeResponse(b"not json"))
    def test_invalid_json_is_wrapped(self, _mock_urlopen):
        with self.assertRaises(EarthquakeFeedError):
            fetch_earthquakes("https://example.test/feed.geojson")


if __name__ == "__main__":
    unittest.main()