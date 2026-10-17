import unittest
from decimal import Decimal
from datetime import date
from listing_sales import listing_sales_summary


class ListingSalesTests(unittest.TestCase):
    def setUp(self):
        self.end = date(2026, 10, 17)
        self.days = [(self.end.fromordinal(self.end.toordinal() - i)).isoformat()
                     for i in range(30)]
        self.order = {
            "conexao_id": 1, "pedido_id": "o1", "status": "paid",
            "total": 100, "moeda": "BRL",
            "criado_em": "2026-10-16T14:00:00.000-03:00",
            "pagamentos_json": [{"status": "approved"}],
            "unidades": 2,
        }
        self.item = {"conexao_id": 1, "pedido_id": "o1",
                     "item_id": "MLB1", "quantidade": 2,
                     "preco_unitario": 50}

    def report(self, orders=None, items=None, covered=None, item_id="MLB1"):
        return listing_sales_summary(
            [self.order] if orders is None else orders,
            [self.item] if items is None else items,
            self.days if covered is None else covered,
            item_id, end=self.end)

    def test_verified_sale(self):
        r = self.report()
        self.assertEqual((r["orders"], r["units"]), (1, 2))

    def test_verified_value_and_ticket(self):
        r = self.report()
        self.assertEqual(r["gross_items"], Decimal("100"))
        self.assertEqual(r["ticket"], Decimal("100"))

    def test_zero_sales_has_zero_value_but_no_ticket(self):
        r = self.report(item_id="MLB2")
        self.assertEqual(r["gross_items"], Decimal("0"))
        self.assertIsNone(r["ticket"])

    def test_missing_item_price_hides_all_listing_indicators(self):
        r = self.report(items=[dict(self.item, preco_unitario=None)])
        self.assertIsNone(r["orders"])
        self.assertIsNone(r["gross_items"])
        self.assertIn("Preço unitário", r["reason"])

    def test_unrelated_listing_missing_price_does_not_hide_this_listing(self):
        order = dict(self.order, unidades=3)
        items = [self.item, dict(self.item, item_id="MLB2",
                                 quantidade=1, preco_unitario=None)]
        r = self.report(orders=[order], items=items)
        self.assertEqual(r["gross_items"], Decimal("100"))

    def test_seven_day_window_is_independent_of_thirty_day_coverage(self):
        recent = self.days[:7]
        r = listing_sales_summary([self.order], [self.item], recent,
                                  "MLB1", end=self.end, days=7)
        self.assertEqual(r["orders"], 1)
        r30 = self.report(covered=recent)
        self.assertIsNone(r30["orders"])

    def test_verified_zero_for_other_item(self):
        r = self.report(item_id="MLB2")
        self.assertEqual((r["orders"], r["units"]), (0, 0))

    def test_missing_coverage_is_unavailable(self):
        r = self.report(covered=self.days[:-1])
        self.assertIsNone(r["orders"])

    def test_missing_order_item_is_unavailable(self):
        r = self.report(items=[])
        self.assertIsNone(r["orders"])

    def test_partial_mapping_is_unavailable(self):
        r = self.report(items=[dict(self.item, quantidade=1)])
        self.assertIsNone(r["orders"])

    def test_unapproved_payment_not_counted(self):
        r = self.report(orders=[dict(self.order, pagamentos_json=[{"status": "rejected"}])])
        self.assertEqual((r["orders"], r["units"]), (0, 0))

    def test_cancelled_order_not_counted(self):
        r = self.report(orders=[dict(self.order, status="cancelled")])
        self.assertEqual((r["orders"], r["units"]), (0, 0))


if __name__ == "__main__":
    unittest.main()
