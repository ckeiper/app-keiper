import unittest
from decimal import Decimal
from listing_kpis import listing_kpis


class ListingKpiTests(unittest.TestCase):
    def test_aggregates_verified_listing_metrics(self):
        rows = {
            "A": {"orders": 2, "previous_orders": 1, "units": 3, "value": Decimal("150")},
            "B": {"orders": 1, "previous_orders": 2, "units": 1, "value": Decimal("50")},
            "C": {"orders": 0, "previous_orders": 0, "units": 0, "value": Decimal("0")},
        }
        k = listing_kpis(rows)
        self.assertEqual(k["value"], Decimal("200"))
        self.assertEqual(k["units"], 4)
        self.assertEqual(k["rising"], 1)
        self.assertEqual(k["falling"], 1)
        self.assertEqual(k["newly_selling"], 0)
        self.assertEqual(k["selling_listings"], 2)
        self.assertEqual(k["listed"], 3)
        self.assertEqual(k["top_listing_share_pct"], Decimal("75"))
        self.assertEqual(k["average_value_per_listing_order"], Decimal("200") / 3)

    def test_zero_sales_does_not_invent_averages(self):
        k = listing_kpis({"A": {"orders": 0, "previous_orders": 0, "units": 0, "value": Decimal(0)}})
        self.assertIsNone(k["top_listing_share_pct"])
        self.assertIsNone(k["average_value_per_listing_order"])


if __name__ == "__main__":
    unittest.main()
