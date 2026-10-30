import unittest

from freight_comparison import FreightComparisonError, compare_freight_orders


class FreightOrdersTests(unittest.TestCase):
    def test_comparison_preserves_order_ids(self):
        records = [
            {"order_id": "ML-001", "charged": "18.50", "expected": "15.00"},
            {"order_id": "ML-002", "charged": "9.00", "expected": "12.00"},
        ]
        results = compare_freight_orders(records)
        self.assertEqual([r["order_id"] for r in results], ["ML-001", "ML-002"])
        self.assertEqual([r["status"] for r in results], ["acima", "abaixo"])
        self.assertEqual([r["difference"] for r in results], ["3.50", "-3.00"])

    def test_duplicate_order_is_rejected(self):
        rows = [{"order_id": " 123 ", "charged": 2, "expected": 1},
                {"order_id": "123", "charged": 3, "expected": 2}]
        with self.assertRaises(FreightComparisonError):
            compare_freight_orders(rows)

    def test_missing_identifier_and_unverified_charge_rejected(self):
        for rows in ([{"order_id": "", "charged": 2, "expected": 1}],
                     [{"order_id": "1", "charged": None, "expected": 1}]):
            with self.assertRaises(FreightComparisonError):
                compare_freight_orders(rows)

    def test_rejects_invalid_tolerance_even_for_empty_report(self):
        with self.assertRaises(FreightComparisonError):
            compare_freight_orders([], "-0.1")

    def test_does_not_mutate_input(self):
        rows = [{"order_id": "1", "charged": "2", "expected": "1"}]
        compare_freight_orders(rows)
        self.assertEqual(rows, [{"order_id": "1", "charged": "2", "expected": "1"}])


if __name__ == "__main__":
    unittest.main()
