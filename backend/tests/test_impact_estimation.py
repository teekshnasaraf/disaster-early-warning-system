import math
import unittest

from impact_estimation import (
    EARTH_RADIUS_KM,
    ImpactParameters,
    estimate_impact,
    haversine_distance_km,
    is_location_within_impact,
)


PARAMETERS = ImpactParameters(base_radius_km=10, magnitude_scale_km=5, depth_scale_km=10)


def event(latitude=0.0, longitude=0.0, magnitude=4.0, depth_km=None):
    result = {
        "magnitude": magnitude,
        "coordinates": {"latitude": latitude, "longitude": longitude},
    }
    if depth_km is not None:
        result["depth_km"] = depth_km
    return result


class ImpactEstimationTests(unittest.TestCase):
    def test_estimates_radius_using_explicit_configured_heuristic(self):
        estimate = estimate_impact(event(magnitude=4), PARAMETERS)

        self.assertEqual(estimate["radius_km"], 30)
        self.assertEqual(estimate["center"], {"latitude": 0.0, "longitude": 0.0})

    def test_optional_depth_reduces_preliminary_radius_by_configured_formula(self):
        estimate = estimate_impact(event(magnitude=4, depth_km=10), PARAMETERS)

        self.assertEqual(estimate["radius_km"], 15)

    def test_accepts_top_level_coordinates(self):
        estimate = estimate_impact(
            {"latitude": 12, "longitude": 34, "magnitude": 2}, PARAMETERS
        )

        self.assertEqual(estimate["center"], {"latitude": 12.0, "longitude": 34.0})

    def test_missing_normalized_depth_uses_zero_depth_adjustment(self):
        estimate = estimate_impact(
            {
                "magnitude": 4.0,
                "depth_km": None,
                "coordinates": {"latitude": 0.0, "longitude": 0.0},
            },
            PARAMETERS,
        )

        self.assertEqual(estimate["radius_km"], 30.0)

    def test_bounding_box_contains_ordinary_center_and_has_ordered_latitudes(self):
        estimate = estimate_impact(event(latitude=20, longitude=30), PARAMETERS)
        bounds = estimate["bounding_box"]

        self.assertLess(bounds["south"], 20)
        self.assertGreater(bounds["north"], 20)
        self.assertLess(bounds["west"], 30)
        self.assertGreater(bounds["east"], 30)
        self.assertFalse(bounds["crosses_antimeridian"])

    def test_bounding_box_wraps_across_antimeridian(self):
        estimate = estimate_impact(event(latitude=0, longitude=179.9), PARAMETERS)
        bounds = estimate["bounding_box"]

        self.assertTrue(bounds["crosses_antimeridian"])
        self.assertGreater(bounds["west"], bounds["east"])
        self.assertGreater(bounds["west"], 179)
        self.assertLess(bounds["east"], -179)

    def test_bounding_box_includes_all_longitudes_when_reaching_pole(self):
        estimate = estimate_impact(event(latitude=89.9, longitude=45), PARAMETERS)
        bounds = estimate["bounding_box"]

        self.assertEqual(bounds["north"], 90)
        self.assertEqual(bounds["west"], -180)
        self.assertEqual(bounds["east"], 180)
        self.assertFalse(bounds["crosses_antimeridian"])

    def test_bounding_box_handles_radius_larger_than_hemisphere(self):
        angular_radius = math.radians(100)
        parameters = ImpactParameters(
            base_radius_km=angular_radius * EARTH_RADIUS_KM,
            magnitude_scale_km=0,
            depth_scale_km=1,
        )
        bounds = estimate_impact(event(latitude=0, longitude=0, magnitude=0), parameters)["bounding_box"]

        self.assertEqual(bounds["south"], -90)
        self.assertEqual(bounds["north"], 90)
        self.assertEqual(bounds["west"], -180)
        self.assertEqual(bounds["east"], 180)
        self.assertFalse(bounds["crosses_antimeridian"])

    def test_large_radius_covers_entire_globe(self):
        parameters = ImpactParameters(
            base_radius_km=math.pi * EARTH_RADIUS_KM + 1,
            magnitude_scale_km=0,
            depth_scale_km=1,
        )
        bounds = estimate_impact(event(magnitude=0), parameters)["bounding_box"]

        self.assertEqual(bounds, {
            "south": -90.0,
            "west": -180.0,
            "north": 90.0,
            "east": 180.0,
            "crosses_antimeridian": False,
        })

    def test_haversine_distance_is_zero_for_same_point(self):
        location = {"latitude": 10, "longitude": 20}

        self.assertEqual(haversine_distance_km(location, location), 0)

    def test_haversine_distance_uses_short_path_across_antimeridian(self):
        distance = haversine_distance_km(
            {"latitude": 0, "longitude": 179.9},
            {"latitude": 0, "longitude": -179.9},
        )

        self.assertAlmostEqual(distance, 22.239, delta=0.1)

    def test_candidate_membership_includes_radius_boundary(self):
        estimate = estimate_impact(event(latitude=0, longitude=0, magnitude=0), PARAMETERS)
        boundary = {"latitude": 0, "longitude": math.degrees(estimate["radius_km"] / EARTH_RADIUS_KM)}

        self.assertTrue(is_location_within_impact(boundary, estimate))
        self.assertFalse(is_location_within_impact({"latitude": 1, "longitude": 1}, estimate))

    def test_rejects_missing_coordinates(self):
        with self.assertRaises(ValueError):
            estimate_impact({"magnitude": 2}, PARAMETERS)
        with self.assertRaises(ValueError):
            estimate_impact({"magnitude": 2, "coordinates": {"latitude": 1}}, PARAMETERS)

    def test_rejects_invalid_event_values(self):
        for invalid_event in (
            event(latitude=91),
            event(longitude=-181),
            event(latitude=float("nan")),
            event(longitude=float("inf")),
            event(magnitude=float("inf")),
            event(magnitude=10**10000),
            event(magnitude=-1),
            event(depth_km=-1),
            event(depth_km=float("nan")),
        ):
            with self.subTest(invalid_event=invalid_event), self.assertRaises(ValueError):
                estimate_impact(invalid_event, PARAMETERS)

    def test_rejects_invalid_parameters(self):
        for values in (
            (-1, 1, 1),
            (1, -1, 1),
            (1, 1, 0),
            (0, 0, 1),
            (float("nan"), 1, 1),
            (1, float("inf"), 1),
            (10**10000, 1, 1),
        ):
            with self.subTest(values=values), self.assertRaises(ValueError):
                ImpactParameters(*values)

    def test_rejects_invalid_candidate_and_radius(self):
        estimate = estimate_impact(event(), PARAMETERS)

        with self.assertRaises(ValueError):
            is_location_within_impact({"latitude": 91, "longitude": 0}, estimate)
        with self.assertRaises(ValueError):
            is_location_within_impact({"latitude": 0, "longitude": 0}, {"center": estimate["center"], "radius_km": 0})


if __name__ == "__main__":
    unittest.main()