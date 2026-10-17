import unittest
from decimal import Decimal
from freight_audit import assess_freight


class FreightAuditTests(unittest.TestCase):
    def test_missing_historical_tariff_is_unverifiable(self):
        result = assess_freight(None, 19, reference_date="2026-10-01",
                                charge_source="ML shipment", comparable=True, shipment_items=1)
        self.assertEqual(result["status"], "Não foi possível conferir")

    def test_current_tariff_without_historical_date_is_unverifiable(self):
        result = assess_freight(12, 19, charge_source="ML shipment",
                                comparable=True, shipment_items=1)
        self.assertEqual(result["status"], "Não foi possível conferir")

    def test_multi_item_shipment_is_unverifiable(self):
        result = assess_freight(12, 19, reference_date="2026-10-01",
                                charge_source="ML shipment", comparable=True, shipment_items=2)
        self.assertEqual(result["status"], "Não foi possível conferir")

    def test_overcharge_threshold(self):
        args = dict(reference_date="2026-10-01", charge_source="ML shipment",
                    comparable=True, shipment_items=1)
        self.assertEqual(assess_freight("12,00", "12,01", **args)["difference"], Decimal("0.01"))
        self.assertEqual(assess_freight("12,00", "12,01", **args)["status"], "Possível divergência")
        self.assertEqual(assess_freight("12,00", "12,00", **args)["status"], "Sem diferença positiva")
        self.assertEqual(assess_freight("12,00", "11,99", **args)["status"], "Sem diferença positiva")

    def test_unknown_logistics_is_unverifiable(self):
        result = assess_freight(12, 19, reference_date="2026-10-01",
                                charge_source="ML shipment", comparable=False, shipment_items=1)
        self.assertEqual(result["status"], "Não foi possível conferir")


if __name__ == "__main__":
    unittest.main()
