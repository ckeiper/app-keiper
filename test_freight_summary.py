import unittest

from freight_comparison import FreightComparisonError, summarize_freight_orders


class FreightSummaryTests(unittest.TestCase):
    def test_aggregates_excess_and_below_separately(self):
        rows = [
            {"order_id": "1", "charged": "18.50", "expected": "15.00"},
            {"order_id": "2", "charged": "9.00", "expected": "12.00"},
            {"order_id": "3", "charged": "10.01", "expected": "10.00"},
            {"order_id": "4", "charged": "17.00", "expected": "15.00"},
        ]
        result = summarize_freight_orders(rows)
        self.assertEqual(result["total_orders"], 4)
        self.assertEqual(result["counts"], {
            "acima": 2, "abaixo": 1, "dentro_tolerancia": 1})
        self.assertEqual(result["excess_charges"], "5.50")
        self.assertEqual(result["below_expected"], "3.00")

    def test_empty_input(self):
        result = summarize_freight_orders([])
        self.assertEqual(result["total_orders"], 0)
        self.assertEqual(result["excess_charges"], "0.00")

    def test_rejects_duplicate_orders(self):
        rows = [
            {"order_id": "A", "charged": 10, "expected": 9},
            {"order_id": "A", "charged": 10, "expected": 9},
        ]
        with self.assertRaises(FreightComparisonError):
            summarize_freight_orders(rows)


if __name__ == "__main__":
    unittest.main()
