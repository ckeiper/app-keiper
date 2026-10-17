"""Promotion column must distinguish campaign price from confirmed final sale price."""
import time
import unittest

from listing_details import normalize_promotions, render_promotions


def snapshot(promotions, sale_price=None):
    result = {"checked_at": time.time(),
              "promotions": normalize_promotions(promotions)}
    if sale_price is not None:
        result["sale_price"] = {"checked_at": time.time(), "data": sale_price}
    return result


class PromotionPriceVisibilityTests(unittest.TestCase):
    def test_single_active_campaign_price_visible_without_sale_price(self):
        value = render_promotions(snapshot([{
            "id": "P1", "type": "DEAL", "status": "started",
            "original_price": 200, "price": 149.9,
        }]))
        self.assertIn("Preço informado pela campanha: R$ 149,90", value)
        self.assertIn("Preço final de venda não confirmado", value)
        self.assertNotIn("<b>Por R$ 149,90", value)

    def test_official_effective_price_takes_precedence(self):
        value = render_promotions(snapshot([{
            "id": "P1", "type": "DEAL", "status": "started", "price": 149.9,
        }], {"amount": 145, "regular_amount": 200, "currency_id": "BRL",
             "metadata": {"promotion_id": "P1"}}))
        self.assertIn("<b>Por R$ 145,00</b>", value)
        self.assertNotIn("Preço informado pela campanha", value)

    def test_conflicting_campaigns_never_guess_winner(self):
        value = render_promotions(snapshot([
            {"id": "P1", "type": "DEAL", "status": "started", "price": 145},
            {"id": "P2", "type": "SMART", "status": "started", "price": 130},
        ]))
        self.assertIn("Campanhas com preços diferentes", value)
        self.assertNotIn("<b>Por R$", value)

    def test_unpriced_campaign_never_guesses(self):
        value = render_promotions(snapshot([{
            "id": "P1", "type": "DEAL", "status": "started",
        }]))
        self.assertIn("Preço da campanha não informado", value)

    def test_stale_campaign_does_not_show_price(self):
        snap = snapshot([{
            "id": "P1", "type": "DEAL", "status": "started", "price": 145,
        }])
        snap["checked_at"] = 1
        value = render_promotions(snap)
        self.assertIn("desatualizados", value)
        self.assertNotIn("Preço informado pela campanha", value)


if __name__ == "__main__":
    unittest.main()
