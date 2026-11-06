import unittest
from datetime import date
from financeiro_store import cents, due_date, balance_status


class FinanceiroTests(unittest.TestCase):
    def test_cents(self):
        self.assertEqual(cents("2000.50"), 200050)
        with self.assertRaises(ValueError):
            cents("-1")
        with self.assertRaises(ValueError):
            cents("NaN")

    def test_fixed_due_date(self):
        self.assertEqual(due_date(2026, 11), date(2026, 11, 5))
        self.assertEqual(due_date(2028, 2), date(2028, 2, 5))

    def test_payment_states(self):
        today = date(2026, 11, 6)
        self.assertEqual(balance_status(200000, 200000, date(2026, 11, 5), today), "pago")
        self.assertEqual(balance_status(200000, 120000, date(2026, 11, 5), today), "parcial_atrasado")
        self.assertEqual(balance_status(200000, 0, date(2026, 12, 5), today), "aberto")
        self.assertEqual(balance_status(200000, 0, date(2026, 11, 5), today), "atrasado")


if __name__ == "__main__":
    unittest.main()
