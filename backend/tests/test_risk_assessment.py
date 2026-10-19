import unittest

from risk_assessment import RiskThresholds, assess_risk, explain_risk


class RiskAssessmentTests(unittest.TestCase):
    def test_classifies_threshold_boundaries(self):
        self.assertEqual(assess_risk(3.9), "low")
        self.assertEqual(assess_risk(4.0), "moderate")
        self.assertEqual(assess_risk(6.0), "high")

    def test_uses_configured_thresholds(self):
        thresholds = RiskThresholds(moderate=2.5, high=5.5)

        self.assertEqual(assess_risk(2.5, thresholds), "moderate")
        self.assertEqual(assess_risk(5.5, thresholds), "high")

    def test_rejects_invalid_threshold_order(self):
        with self.assertRaises(ValueError):
            RiskThresholds(moderate=6, high=5)

        with self.assertRaises(ValueError):
            RiskThresholds(moderate=float("nan"), high=6)
        with self.assertRaises(ValueError):
            RiskThresholds(moderate=10**10000, high=10**10001)

    def test_rejects_invalid_magnitude(self):
        with self.assertRaises(ValueError):
            assess_risk(-1)
        with self.assertRaises(ValueError):
            assess_risk(True)
        with self.assertRaises(ValueError):
            assess_risk(float("inf"))
        with self.assertRaises(ValueError):
            assess_risk(10**10000)

    def test_explains_classification_rule_and_reason(self):
        result = explain_risk(5.0)

        self.assertEqual(result["level"], "moderate")
        self.assertEqual(result["rule"], "magnitude_thresholds_v1")
        self.assertIn("moderate threshold", result["reason"])
        self.assertEqual(result["thresholds"], {"moderate": 4.0, "high": 6.0})

    def test_missing_magnitude_is_unknown_not_low(self):
        result = explain_risk(None)

        self.assertEqual(result["level"], "unknown")
        self.assertIn("unavailable", result["reason"])


if __name__ == "__main__":
    unittest.main()