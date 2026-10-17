"""Unit tests for deterministic freight templates (no database or ML API)."""
import unittest
from decimal import Decimal
from freight_contestation import money, generate_messages, render_generator


class FreightContestationTests(unittest.TestCase):
    def test_money_brazilian_format(self):
        self.assertEqual(money("R$ 1.234,56"), Decimal("1234.56"))
        self.assertEqual(money("116,00"), Decimal("116.00"))

    def test_reject_invalid_money(self):
        for value in ("", "-1", "NaN", "Infinity", "1,999", "abc"):
            self.assertIsNone(money(value))

    def test_three_distinct_editable_templates(self):
        messages = generate_messages("123", "MLB123", "456", "12,00", "15,50")
        self.assertEqual(len(messages), 3)
        self.assertEqual(len({title for title, _ in messages}), 3)
        for _, text in messages:
            self.assertIn("Pedido: 123", text)
            self.assertIn("R$ 3,50", text)
            self.assertIn("confirmados", text)

    def test_no_positive_difference_for_lower_charge(self):
        text = generate_messages("1", "", "", "15,50", "12,00")[0][1]
        self.assertIn("Possível diferença positiva: não informado", text)

    def test_escape_html_and_attributes(self):
        html = render_generator({"order_id": '"><script>alert(1)</script>'})
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertEqual(html.count("<textarea"), 3)


if __name__ == "__main__":
    unittest.main()
