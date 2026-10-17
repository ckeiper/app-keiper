import unittest
from datetime import date, timedelta
from decimal import Decimal
from listing_ranking import ranking_metrics


class ListingRankingTests(unittest.TestCase):
    def setUp(self):
        self.end = date(2026, 10, 17)
        self.covered = [(self.end - timedelta(days=i)).isoformat()
                        for i in range(60)]
        self.order = {
            "conexao_id": 1, "pedido_id": "a", "status": "paid",
            "total": 100, "moeda": "BRL",
            "criado_em": "2026-10-16T12:00:00-03:00",
            "pagamentos_json": [{"status": "approved"}], "unidades": 2}
        self.item = {
            "conexao_id": 1, "pedido_id": "a", "item_id": "MLB1",
            "quantidade": 2, "preco_unitario": 50}

    def run_ranking(self, orders=None, items=None, covered=None, pending=False):
        return ranking_metrics(
            [self.order] if orders is None else orders,
            [self.item] if items is None else items,
            self.covered if covered is None else covered,
            ["MLB1", "MLB2"], end=self.end, pending=pending)

    def test_verified_sales_and_zero_for_other_listing(self):
        r = self.run_ranking()
        self.assertTrue(r["available"])
        self.assertEqual(r["rows"]["MLB1"]["value"], Decimal("100"))
        self.assertEqual(r["rows"]["MLB1"]["ticket"], Decimal("100"))
        self.assertEqual(r["rows"]["MLB1"]["trend"], "novas")
        self.assertEqual(r["rows"]["MLB2"]["orders"], 0)

    def test_seven_days_works_without_sixty_day_history(self):
        r = ranking_metrics(
            [self.order], [self.item], self.covered[:14],
            ["MLB1"], end=self.end, days=7)
        self.assertTrue(r["available"])
        self.assertEqual(r["rows"]["MLB1"]["orders"], 1)
        r30 = self.run_ranking(covered=self.covered[:14])
        self.assertFalse(r30["available"])

    def test_missing_earlier_coverage_hides_ranking(self):
        r = self.run_ranking(covered=self.covered[:30])
        self.assertFalse(r["available"])

    def test_unverified_old_orders_hides_ranking(self):
        self.assertFalse(self.run_ranking(pending=True)["available"])

    def test_missing_item_mapping_hides_ranking(self):
        self.assertFalse(self.run_ranking(items=[])["available"])

    def test_invalid_price_hides_ranking(self):
        self.assertFalse(self.run_ranking(
            items=[dict(self.item, preco_unitario=None)])["available"])

    def test_previous_period_and_decline(self):
        old = dict(self.order, pedido_id="b",
                   criado_em="2026-09-10T12:00:00-03:00")
        old_item = dict(self.item, pedido_id="b")
        r = self.run_ranking(orders=[old], items=[old_item])
        self.assertTrue(r["available"])
        self.assertEqual(r["rows"]["MLB1"]["previous_orders"], 1)
        self.assertEqual(r["rows"]["MLB1"]["growth_pct"], Decimal("-100"))
        self.assertEqual(r["rows"]["MLB1"]["trend"], "queda")

    def test_multi_item_order_is_not_overallocated(self):
        order = dict(self.order, unidades=3, total=400)
        other = dict(self.item, item_id="MLB2", quantidade=1,
                     preco_unitario=200)
        r = self.run_ranking(orders=[order], items=[self.item, other])
        self.assertTrue(r["available"])
        self.assertEqual(r["rows"]["MLB1"]["value"], Decimal("100"))
        self.assertEqual(r["rows"]["MLB2"]["value"], Decimal("200"))


if __name__ == "__main__":
    unittest.main()
