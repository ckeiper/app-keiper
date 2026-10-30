import unittest
from decimal import Decimal
from unittest.mock import patch

from listing_priority_evidence import enrich_priorities
from listing_priority_queue import prioritize, render
from listing_priority_sources import listing_signals


class PriorityEvidenceTests(unittest.TestCase):
    def test_missing_evidence_is_not_zero(self):
        queue = {"available": True, "items": [{"item_id": "MLB1"}]}
        result = enrich_priorities(queue, {"MLB1": {"stock": 0, "margin_current_pct": 5}})
        self.assertEqual(result["items"][0]["additional_findings"], [])
        self.assertEqual(result["items"][0]["data_limitations"], ["estoque", "margem"])

    def test_stockout_and_margin_decline(self):
        queue = {"available": True, "items": [{"item_id": "MLB1"}]}
        signals = {"MLB1": {"stock_verified": True, "stock": 0,
                            "margin_verified": True, "margin_current_pct": 10,
                            "margin_previous_pct": 20}}
        findings = enrich_priorities(queue, signals)["items"][0]["additional_findings"]
        self.assertEqual([f["code"] for f in findings], ["stockout", "margin_decline"])

    def test_coverage_under_seven_days(self):
        queue = {"available": True, "items": [{"item_id": "MLB1"}]}
        signals = {"MLB1": {"stock_verified": True, "stock": 12, "daily_units": 3}}
        findings = enrich_priorities(queue, signals)["items"][0]["additional_findings"]
        self.assertEqual([f["code"] for f in findings], ["stock_coverage"])

    def test_invalid_stock_does_not_trigger(self):
        queue = {"available": True, "items": [{"item_id": "MLB1"}]}
        result = enrich_priorities(queue, {"MLB1": {"stock_verified": True, "stock": -1}})
        self.assertEqual(result["items"][0]["additional_findings"], [])

    def test_optional_integration_preserves_old_behavior(self):
        analysis = {"available": True, "rows": [{
            "item_id": "MLB1", "loss": Decimal("30"),
            "percent": Decimal("-10"), "share": Decimal("1")}],
            "lost": Decimal("30")}
        with patch("listing_priority_queue.investigate", return_value=analysis):
            legacy = prioritize({}, limit=1)
            enriched = prioritize({}, limit=1, verified_signals_by_item={
                "MLB1": {"stock_verified": True, "stock": 0}})
        self.assertNotIn("additional_findings", legacy["items"][0])
        self.assertEqual(enriched["items"][0]["additional_findings"][0]["code"], "stockout")

    def test_fresh_stock_source_and_verified_velocity(self):
        listings = [{"item_id": "MLB1", "quantidade": 12, "atualizado_em": 1000}]
        ranking = {"available": True, "rows": {"MLB1": {"units": 21}}}
        signals = listing_signals(listings, ranking, 7, now=1200)
        self.assertTrue(signals["MLB1"]["stock_verified"])
        self.assertEqual(signals["MLB1"]["daily_units"], Decimal("3"))

    def test_stale_stock_source_rejected(self):
        listings = [{"item_id": "MLB1", "quantidade": 0, "atualizado_em": 1000}]
        signals = listing_signals(listings, {"available": True}, 7, now=30000)
        self.assertFalse(signals["MLB1"]["stock_verified"])

    def test_render_verified_evidence_and_escapes_markup(self):
        queue = {"available": True, "items": [{
            "item_id": "MLB1", "loss": Decimal("20"), "pct": -10,
            "reasons": [], "action": "Revisar anúncio",
            "coverage": None, "expected": None,
            "additional_findings": [{"evidence": "<script>ruim</script>",
                                      "action": "Conferir reposição"}],
            "data_limitations": ["margem"]}],
            "total": 1, "loss": Decimal("20")}
        html = render(queue, [{"item_id": "MLB1", "titulo": "Produto"}], 10)
        self.assertIn("Conferir reposição", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("<script>ruim</script>", html)

    def test_unavailable_queue_unchanged(self):
        queue = {"available": False, "reason": "Sem cobertura", "items": []}
        self.assertEqual(enrich_priorities(queue), queue)


if __name__ == "__main__":
    unittest.main()
