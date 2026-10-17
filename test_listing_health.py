import unittest
from listing_health import diagnose_listing


class ListingHealthTests(unittest.TestCase):
    def test_paused_out_of_stock_listing_is_high_priority(self):
        results = diagnose_listing({"status": "paused", "quantidade": 0,
                                    "fotos": 2, "clips": 0, "preco": 99})
        self.assertEqual(results[0]["priority"], "alta")
        self.assertEqual([r["title"] for r in results[:2]],
                         ["Anúncio pausado", "Estoque zerado"])
        self.assertTrue(any(r["title"] == "Poucas fotos" for r in results))

    def test_missing_fields_are_not_treated_as_zero(self):
        results = diagnose_listing({})
        titles = {r["title"] for r in results}
        self.assertIn("Estoque não verificado", titles)
        self.assertIn("Fotos não verificadas", titles)
        self.assertNotIn("Estoque zerado", titles)
        self.assertNotIn("Nenhuma foto registrada", titles)
        self.assertNotIn("Vídeo não identificado", titles)

    def test_healthy_listing_does_not_claim_sales_performance(self):
        results = diagnose_listing({"status": "active", "quantidade": 50,
                                    "fotos": 8, "clips": 1, "preco": 120})
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["priority"], "ok")
        self.assertNotIn("conversão", results[0]["title"])

    def test_invalid_values_are_not_interpreted_as_stock(self):
        for stock in ("NaN", -1, True, "bad", 1.5):
            with self.subTest(stock=stock):
                results = diagnose_listing({"status": "active", "quantidade": stock,
                                            "fotos": 8, "preco": 100})
                self.assertTrue(any(r["title"] == "Estoque não verificado"
                                    for r in results))

    def test_small_inventory_is_actionable(self):
        results = diagnose_listing({"status": "active", "quantidade": 3,
                                    "fotos": 8, "clips": None, "preco": 100})
        self.assertEqual(results[0]["title"], "Estoque baixo")


if __name__ == "__main__":
    unittest.main()
