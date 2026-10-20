from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import io
import json
import os
import tempfile
import unittest
from unittest.mock import patch

import demo


class DemoTests(unittest.TestCase):
    def test_displays_processed_event_with_heuristic_labels(self):
        event = {
            "id": "usgs-demo",
            "source": "USGS",
            "source_id": "usgs-demo",
            "magnitude": 5.2,
            "place": "Example region",
            "timestamp_utc": "2026-10-19T12:00:00Z",
            "coordinates": {"longitude": -122.5, "latitude": 37.7},
            "depth_km": 8.0,
        }
        output = io.StringIO()
        with (
            patch.object(demo, "fetch_earthquakes", return_value=[event]),
            patch.object(
                demo,
                "process_events",
                return_value={"accepted": [event], "stale": [], "duplicates": [], "rejected": []},
            ),
            redirect_stdout(output),
        ):
            status = demo.main([])

        self.assertEqual(status, 0)
        self.assertIn("1 accepted", output.getvalue())
        self.assertIn("Heuristic risk: moderate", output.getvalue())
        self.assertIn("Heuristic impact radius:", output.getvalue())
        self.assertIn("not validated predictions", output.getvalue())
        self.assertIn("No notifications", output.getvalue())

    def test_handles_missing_magnitude_without_claiming_low_risk(self):
        event = {
            "id": "usgs-unknown",
            "source": "USGS",
            "source_id": "usgs-unknown",
            "magnitude": None,
            "place": "Unknown region",
            "timestamp_utc": "2026-10-19T12:00:00Z",
            "coordinates": {"longitude": 1, "latitude": 2},
            "depth_km": None,
        }
        output = io.StringIO()
        with (
            patch.object(demo, "fetch_earthquakes", return_value=[event]),
            patch.object(
                demo,
                "process_events",
                return_value={"accepted": [event], "stale": [], "duplicates": [], "rejected": []},
            ),
            redirect_stdout(output),
        ):
            status = demo.main([])

        self.assertEqual(status, 0)
        self.assertIn("Heuristic risk: unknown", output.getvalue())
        self.assertIn("impact radius: unavailable", output.getvalue())

    def test_reports_network_failure_without_traceback(self):
        output = io.StringIO()
        error_output = io.StringIO()
        with (
            patch.object(demo, "fetch_earthquakes", side_effect=demo.EarthquakeFeedError("offline")),
            redirect_stdout(output),
            redirect_stderr(error_output),
        ):
            status = demo.main([])

        self.assertEqual(status, 1)
        self.assertEqual(output.getvalue(), "")
        self.assertIn("Unable to fetch or validate", error_output.getvalue())
        self.assertIn("offline", error_output.getvalue())

    def test_invalid_freshness_options_are_rejected(self):
        with self.assertRaises(SystemExit) as raised:
            demo.main(["--max-age-hours", "0"])

        self.assertEqual(raised.exception.code, 2)

    def test_sample_data_mode_runs_offline_without_network(self):
        output = io.StringIO()
        with (
            patch.object(demo, "fetch_earthquakes") as mock_fetch,
            redirect_stdout(output),
        ):
            status = demo.main(["--sample-data"])

        mock_fetch.assert_not_called()
        self.assertEqual(status, 0)
        content = output.getvalue()
        self.assertIn("Built-in representative sample data", content)
        self.assertIn("4 accepted", content)
        self.assertIn("sample-event-1", content)
        self.assertIn("sample-event-4", content)
        self.assertIn("Heuristic risk: unknown", content)

    def test_fixture_file_mode_loads_and_processes_geojson(self):
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        payload = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "id": "fixture-1",
                    "properties": {
                        "mag": 4.5,
                        "place": "Fixture Bay",
                        "time": now_ms - 60000,
                        "updated": now_ms,
                    },
                    "geometry": {
                        "type": "Point",
                        "coordinates": [-122.0, 37.0, 5.0],
                    },
                }
            ],
        }
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".geojson") as temp_file:
            json.dump(payload, temp_file)
            temp_path = temp_file.name

        try:
            output = io.StringIO()
            with (
                patch.object(demo, "fetch_earthquakes") as mock_fetch,
                redirect_stdout(output),
            ):
                status = demo.main(["--fixture-file", temp_path])

            mock_fetch.assert_not_called()
            self.assertEqual(status, 0)
            self.assertIn("fixture-1", output.getvalue())
            self.assertIn("Fixture Bay", output.getvalue())
            self.assertIn("1 accepted", output.getvalue())
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_fixture_file_missing_reports_clean_error(self):
        error_output = io.StringIO()
        with redirect_stderr(error_output):
            status = demo.main(["--fixture-file", "nonexistent_fixture_path_12345.geojson"])

        self.assertEqual(status, 1)
        self.assertIn("Unable to read or parse fixture file", error_output.getvalue())

    def test_fixture_file_invalid_utf8_reports_clean_error(self):
        with tempfile.NamedTemporaryFile("wb", delete=False, suffix=".geojson") as temp_file:
            temp_file.write(b"\xff")
            temp_path = temp_file.name

        try:
            error_output = io.StringIO()
            with redirect_stderr(error_output):
                status = demo.main(["--fixture-file", temp_path])
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

        self.assertEqual(status, 1)
        self.assertIn("Unable to read or parse fixture file", error_output.getvalue())
        self.assertIn("utf-8", error_output.getvalue())

    def test_conflicting_source_options_are_rejected(self):
        with self.assertRaises(SystemExit) as raised1:
            demo.main(["--sample-data", "--fixture-file", "sample.geojson"])
        self.assertEqual(raised1.exception.code, 2)

        with self.assertRaises(SystemExit) as raised2:
            demo.main(["--sample-data", "--feed-url", "https://example.com/feed.geojson"])
        self.assertEqual(raised2.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
