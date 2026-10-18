import unittest
from listing_diagnostic_rules import diagnose_listing_periods


class ListingDiagnosticRulesTests(unittest.TestCase):
    def test_missing_data_does_not_turn_into_zero(self):
        result = diagnose_listing_periods(
            {"visits": None, "orders": 2, "revenue": 100},
            {"visits": 100, "orders": 4, "revenue": 200})
        self.assertEqual([r["code"] for r in result], ["insufficient_data"])

    def test_traffic_and_conversion_are_distinct(self):
        result = diagnose_listing_periods(
            {"visits": 100, "orders": 5, "revenue": 500},
            {"visits": 200, "orders": 20, "revenue": 2000})
        self.assertEqual([r["code"] for r in result],
                         ["orders_drop", "traffic_drop", "conversion_drop"])

    def test_zero_visits_never_divides_by_zero(self):
        result = diagnose_listing_periods(
            {"visits": 0, "orders": 0, "revenue": 0},
            {"visits": 0, "orders": 0, "revenue": 0})
        self.assertEqual(result[0]["code"], "conversion_unavailable")

    def test_stable_period_has_no_alert(self):
        result = diagnose_listing_periods(
            {"visits": 120, "orders": 12, "revenue": 1200},
            {"visits": 100, "orders": 10, "revenue": 1000})
        self.assertEqual(result[0]["code"], "no_alert")

    def test_negative_or_nan_values_rejected(self):
        result = diagnose_listing_periods(
            {"visits": -1, "orders": 2, "revenue": "NaN"},
            {"visits": 10, "orders": 2, "revenue": 20})
        self.assertEqual(result[0]["code"], "insufficient_data")


if __name__ == "__main__":
    unittest.main()
