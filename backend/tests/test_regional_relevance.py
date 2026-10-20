import json
import unittest

from impact_estimation import ImpactParameters
from regional_relevance import (
    DEFAULT_TAMIL_NADU_AREA,
    TamilNaduAssessmentArea,
    assess_tamil_nadu_relevance,
)


PARAMETERS = ImpactParameters(
    base_radius_km=10,
    magnitude_scale_km=5,
    depth_scale_km=10,
)


def event(latitude=10.0, longitude=80.5, magnitude=5.0, depth_km=10.0):
    return {
        "magnitude": magnitude,
        "depth_km": depth_km,
        "coordinates": {"latitude": latitude, "longitude": longitude},
    }


class RegionalRelevanceTests(unittest.TestCase):
    def test_nearby_event_uses_magnitude_depth_radius_and_distance(self):
        result = assess_tamil_nadu_relevance(event(), PARAMETERS)
        shallower_event = assess_tamil_nadu_relevance(
            event(depth_km=0),
            PARAMETERS,
        )
        lower_magnitude_event = assess_tamil_nadu_relevance(
            event(magnitude=0),
            PARAMETERS,
        )

        self.assertEqual(result["status"], "within_heuristic_radius")
        self.assertGreater(result["distance_km"], 0)
        self.assertLessEqual(result["distance_km"], result["impact_radius_km"])
        self.assertEqual(result["impact_radius_km"], 17.5)
        self.assertGreater(
            shallower_event["impact_radius_km"],
            result["impact_radius_km"],
        )
        self.assertLess(
            lower_magnitude_event["impact_radius_km"],
            result["impact_radius_km"],
        )
        json.dumps(result, allow_nan=False)

    def test_distant_event_is_not_relabelled_as_tamil_nadu_risk(self):
        result = assess_tamil_nadu_relevance(
            event(latitude=37.7, longitude=-122.5, magnitude=8.0, depth_km=1.0),
            PARAMETERS,
        )

        self.assertEqual(result["status"], "outside_heuristic_radius")
        self.assertGreater(result["distance_km"], result["impact_radius_km"])
        self.assertNotIn("risk", result)

    def test_area_boundary_is_inclusive(self):
        result = assess_tamil_nadu_relevance(
            event(latitude=DEFAULT_TAMIL_NADU_AREA.south, longitude=78.0),
            PARAMETERS,
        )

        self.assertEqual(result["status"], "inside_assessment_area")
        self.assertEqual(result["distance_km"], 0)

    def test_missing_coordinates_return_unknown(self):
        result = assess_tamil_nadu_relevance({"magnitude": 5.0}, PARAMETERS)

        self.assertEqual(result["status"], "unknown")
        self.assertIsNone(result["distance_km"])
        self.assertIn("coordinates", result["reason"])

    def test_missing_magnitude_keeps_distance_but_cannot_assess_radius(self):
        result = assess_tamil_nadu_relevance(
            event(longitude=81.0, magnitude=None),
            PARAMETERS,
        )

        self.assertEqual(result["status"], "unknown")
        self.assertGreater(result["distance_km"], 0)
        self.assertIsNone(result["impact_radius_km"])
        json.dumps(result, allow_nan=False)

    def test_negative_and_non_finite_magnitudes_make_outside_relevance_unknown(self):
        for magnitude in (-0.1, float("nan"), float("inf")):
            with self.subTest(magnitude=str(magnitude)):
                result = assess_tamil_nadu_relevance(
                    event(longitude=81.0, magnitude=magnitude),
                    PARAMETERS,
                )

                self.assertEqual(result["status"], "unknown")
                self.assertGreater(result["distance_km"], 0)
                self.assertIsNone(result["impact_radius_km"])
                self.assertIn("magnitude", result["reason"])
                json.dumps(result, allow_nan=False)

    def test_distance_exactly_equal_to_radius_is_within_heuristic_radius(self):
        area = TamilNaduAssessmentArea(south=9, west=77, north=11, east=80)
        outside_event = event(latitude=10, longitude=81, magnitude=0, depth_km=0)
        distance = assess_tamil_nadu_relevance(
            outside_event,
            ImpactParameters(base_radius_km=1, magnitude_scale_km=0, depth_scale_km=1),
            area,
        )["distance_km"]
        parameters = ImpactParameters(
            base_radius_km=distance,
            magnitude_scale_km=0,
            depth_scale_km=1,
        )

        result = assess_tamil_nadu_relevance(outside_event, parameters, area)

        self.assertEqual(result["distance_km"], result["impact_radius_km"])
        self.assertEqual(result["status"], "within_heuristic_radius")

    def test_invalid_coordinates_and_depth_are_handled_deterministically(self):
        invalid_coordinates = assess_tamil_nadu_relevance(
            event(latitude=float("nan")),
            PARAMETERS,
        )
        invalid_depth = assess_tamil_nadu_relevance(
            event(longitude=81.0, depth_km=-1),
            PARAMETERS,
        )

        self.assertEqual(invalid_coordinates["status"], "unknown")
        self.assertIsNone(invalid_coordinates["distance_km"])
        self.assertEqual(invalid_depth["status"], "unknown")
        self.assertGreater(invalid_depth["distance_km"], 0)
        self.assertIn("depth_km", invalid_depth["reason"])
        json.dumps(invalid_coordinates, allow_nan=False)
        json.dumps(invalid_depth, allow_nan=False)

    def test_area_can_be_reconfigured_and_rejects_invalid_bounds(self):
        area = TamilNaduAssessmentArea(south=9, west=77, north=11, east=79)
        result = assess_tamil_nadu_relevance(
            event(latitude=10, longitude=78, magnitude=None),
            PARAMETERS,
            area,
        )

        self.assertEqual(result["status"], "inside_assessment_area")
        with self.assertRaises(ValueError):
            TamilNaduAssessmentArea(south=11, north=9)


if __name__ == "__main__":
    unittest.main()
