import unittest

from freight_comparison import (FreightComparisonError, compare_freight,
                                format_brl, render_freight_comparison_demo)


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

    def test_exact_tolerance_boundary(self):
        self.assertEqual(compare_freight("10.02", "10.00", "0.02")["status"],
                         "dentro_tolerancia")
        self.assertEqual(compare_freight("10.03", "10.00", "0.02")["status"],
                         "acima")

    def test_undercharge_tolerance_boundary(self):
        self.assertEqual(compare_freight("9.98", "10.00", "0.02")["status"],
                         "dentro_tolerancia")
        self.assertEqual(compare_freight("9.97", "10.00", "0.02")["status"],
                         "abaixo")

    def test_zero_and_large_values(self):
        self.assertEqual(compare_freight("0", "0")["status"], "dentro_tolerancia")
        self.assertEqual(compare_freight("1000000.99", "1000000.98")["difference"],
                         "0.01")

    def test_invalid_tolerance(self):
        for value in ("-0.01", "NaN", None, True):
            with self.subTest(value=value):
                with self.assertRaises(FreightComparisonError):
                    compare_freight("10", "10", value)

    def test_brazilian_currency_formatting(self):
        self.assertEqual(format_brl("1234.50"), "R$ 1.234,50")
        self.assertEqual(format_brl("-3.00"), "R$ -3,00")

    def test_demo_has_disclaimer_and_all_statuses(self):
        html = render_freight_comparison_demo()
        self.assertIn("Dados ficticios", html)
        self.assertIn("Nao representam cobrancas de nenhuma loja", html)
        self.assertIn("Acima do esperado", html)
        self.assertIn("Abaixo do esperado", html)
        self.assertIn("Dentro da tolerancia", html)
        self.assertIn("R$ 18,50", html)
        self.assertIn("R$ -3,00", html)
        self.assertEqual(html.count("<tr>"), 4)

    def test_invalid_inputs(self):
        for value in (None, True, "-1", "NaN", "Infinity", "abc"):
            with self.subTest(value=value):
                with self.assertRaises(FreightComparisonError):
                    compare_freight(value, "10")


if __name__ == "__main__":
    unittest.main()
