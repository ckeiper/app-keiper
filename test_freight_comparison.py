import unittest

from freight_comparison import FreightComparisonError, compare_freight


class FreightComparisonTests(unittest.TestCase):
    def test_overcharge(self):
        result = compare_freight("18.50", "15.00")
        self.assertEqual(result["difference"], "3.50")
        self.assertEqual(result["status"], "acima")

    def test_undercharge(self):
        self.assertEqual(compare_freight("9", "12")["status"], "abaixo")

    def test_tolerance(self):
        self.assertEqual(compare_freight("10.01", "10")["status"], "dentro_tolerancia")

    def test_rounding(self):
        self.assertEqual(compare_freight("10.005", "10")["charged"], "10.01")

    def test_invalid_inputs(self):
        for value in (None, True, "-1", "NaN", "Infinity", "abc"):
            with self.subTest(value=value):
                with self.assertRaises(FreightComparisonError):
                    compare_freight(value, "10")


if __name__ == "__main__":
    unittest.main()
