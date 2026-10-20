from datetime import datetime, timezone
import unittest

from evacuation_destinations import (
    Coordinates,
    Destination,
    DestinationCatalog,
    DestinationType,
    DuplicateDestinationError,
)
from routing import RoutingProviderUnavailableError, request_candidate_route


def fictional_destination(**overrides):
    """Return a clearly fictional test fixture, not a real evacuation site."""
    values = {
        "identifier": "fictional-test-site-1",
        "name": "Fictional Test Site (not a real destination)",
        "coordinates": Coordinates(latitude=37.5, longitude=-122.2),
        "destination_type": DestinationType.SHELTER,
        "last_updated": None,
        "capacity": None,
        "available": None,
    }
    values.update(overrides)
    return Destination(**values)


class DestinationModelTests(unittest.TestCase):
    def test_accepts_valid_destination_with_supplied_provenance(self):
        updated = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)
        destination = fictional_destination(
            data_source="fictional test dataset",
            last_updated=updated,
            capacity=120,
            available=True,
        )

        self.assertEqual(destination.capacity, 120)
        self.assertTrue(destination.available)
        self.assertEqual(destination.last_updated, updated)

    def test_unknown_optional_values_remain_explicitly_unknown(self):
        destination = fictional_destination()

        self.assertEqual(destination.data_source, "unknown")
        self.assertIsNone(destination.last_updated)
        self.assertIsNone(destination.capacity)
        self.assertIsNone(destination.available)

    def test_accepts_explicitly_unavailable_destination(self):
        destination = fictional_destination(available=False)

        self.assertIs(destination.available, False)

    def test_rejects_invalid_or_out_of_range_coordinates(self):
        for latitude, longitude in (
            (-90.1, 0),
            (90.1, 0),
            (0, -180.1),
            (0, 180.1),
            (float("nan"), 0),
            (0, float("inf")),
            (True, 0),
            ("37.5", -122.2),
        ):
            with self.subTest(latitude=latitude, longitude=longitude):
                with self.assertRaises(ValueError):
                    Coordinates(latitude=latitude, longitude=longitude)

    def test_rejects_invalid_destination_fields_and_metadata(self):
        for overrides in (
            {"identifier": " "},
            {"name": ""},
            {"destination_type": "shelter"},
            {"capacity": -1},
            {"capacity": True},
            {"available": "yes"},
            {"last_updated": datetime(2026, 10, 20)},
            {"data_source": ""},
        ):
            with self.subTest(overrides=overrides):
                with self.assertRaises(ValueError):
                    fictional_destination(**overrides)

    def test_catalog_rejects_duplicate_identifiers(self):
        first = fictional_destination()
        second = fictional_destination(name="Another fictional test site")

        with self.assertRaisesRegex(DuplicateDestinationError, "fictional-test-site-1"):
            DestinationCatalog([first, second])

    def test_catalog_keeps_order_and_supports_identifier_lookup(self):
        destination = fictional_destination()
        catalog = DestinationCatalog([destination])

        self.assertEqual(catalog.destinations, (destination,))
        self.assertIs(catalog.get(destination.identifier), destination)
        self.assertIsNone(catalog.get("missing"))


class RoutingBoundaryTests(unittest.TestCase):
    def test_route_request_without_provider_fails_without_claiming_a_route(self):
        origin = Coordinates(latitude=37.7, longitude=-122.4)
        destination = fictional_destination()

        with self.assertRaisesRegex(
            RoutingProviderUnavailableError, "no route was calculated"
        ):
            request_candidate_route(None, origin, destination)

    def test_does_not_request_route_to_destination_marked_unavailable(self):
        class TestProvider:
            def request_route(self, origin, destination):
                raise AssertionError("provider must not be called")

        with self.assertRaisesRegex(ValueError, "marked unavailable"):
            request_candidate_route(
                TestProvider(),
                Coordinates(latitude=37.7, longitude=-122.4),
                fictional_destination(available=False),
            )


if __name__ == "__main__":
    unittest.main()
