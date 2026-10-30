import unittest
from decimal import Decimal
from listing_profitability import contribution


class ListingProfitabilityTests(unittest.TestCase):
    def test_complete_costs(self):
        result = contribution(1000, 10, unit_cost=40, marketplace_fees=120,
                              seller_shipping=60, taxes=50, advertising=70)
        self.assertTrue(result["available"])
        self.assertEqual(result["contribution"], Decimal("300"))
        self.assertEqual(result["margin_pct"], Decimal("30"))

    def test_missing_ads_does_not_invent_profit(self):
        result = contribution(1000, 10, unit_cost=40, marketplace_fees=120,
                              seller_shipping=60, taxes=50)
        self.assertFalse(result["available"])
        self.assertIsNone(result["contribution"])
        self.assertIn("advertising", result["missing"])

    def test_zero_revenue_does_not_divide_by_zero(self):
        result = contribution(0, 0, 0, 0, 0, 0, 0)
        self.assertTrue(result["available"])
        self.assertIsNone(result["margin_pct"])

    def test_negative_cost_is_not_trusted(self):
        result = contribution(100, 1, -5, 0, 0, 0, 0)
        self.assertFalse(result["available"])

    def test_negative_contribution_is_allowed(self):
        result = contribution(100, 1, 120, 0, 0, 0, 0)
        self.assertEqual(result["contribution"], Decimal("-20"))


if __name__ == "__main__":
    unittest.main()
