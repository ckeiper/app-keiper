import unittest
from decimal import Decimal
from listing_trends import comparison


def report(orders, units, gross):
    return {"orders": orders, "units": units, "gross_items": gross,
            "reason": None}


class ListingTrendsTests(unittest.TestCase):
    def test_increase_and_decrease(self):
        r = comparison(report(4, 5, Decimal("200")),
                       report(2, 7, Decimal("100")))
        self.assertTrue(r["available"])
        self.assertEqual(r["orders"]["percent"], Decimal("100"))
        self.assertEqual(r["units"]["status"], "queda")
        self.assertEqual(r["gross_items"]["difference"], Decimal("100"))

    def test_missing_coverage_is_not_a_zero(self):
        r = comparison(report(2, 2, 50),
                       dict(report(None, None, None), reason="Sem cobertura"))
        self.assertFalse(r["available"])
        self.assertEqual(r["reason"], "Sem cobertura")

    def test_previous_zero_is_not_infinite_growth(self):
        r = comparison(report(3, 4, 120), report(0, 0, 0))
        self.assertEqual(r["orders"]["status"], "novas_vendas")
        self.assertIsNone(r["orders"]["percent"])

    def test_both_zero_is_no_movement(self):
        r = comparison(report(0, 0, 0), report(0, 0, 0))
        self.assertEqual(r["orders"]["status"], "sem_movimento")
        self.assertIsNone(r["orders"]["percent"])

    def test_equal_values_are_stable(self):
        r = comparison(report(3, 3, 99), report(3, 3, 99))
        self.assertEqual(r["orders"]["status"], "estavel")
        self.assertEqual(r["orders"]["percent"], 0)


if __name__ == "__main__":
    unittest.main()
