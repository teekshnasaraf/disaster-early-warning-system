import unittest

from risk_assessment import RiskThresholds, assess_risk


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

    def test_rejects_invalid_magnitude(self):
        with self.assertRaises(ValueError):
            assess_risk(-1)
        with self.assertRaises(ValueError):
            assess_risk(True)
        with self.assertRaises(ValueError):
            assess_risk(float("inf"))


if __name__ == "__main__":
    unittest.main()