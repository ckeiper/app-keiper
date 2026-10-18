"""Tests for the official Mercado Livre shipments/{id}/costs response shape."""
import unittest
from decimal import Decimal
from freight_ml import seller_shipping_cost, seller_shipment_item_count


class FreightMLTests(unittest.TestCase):
    def test_uses_seller_cost_not_receiver_or_gross_amount(self):
        response = {
            "gross_amount": 24.55,
            "receiver": {"user_id": 999, "cost": 0},
            "senders": [{"user_id": 123, "cost": 8.19,
                         "discounts": [{"promoted_amount": 12.29}]}],
        }
        self.assertEqual(seller_shipping_cost(response, 123), (Decimal("8.19"), None))
        self.assertEqual(seller_shipping_cost(response, "123"), (Decimal("8.19"), None))

    def test_different_seller_is_never_charged(self):
        response = {"receiver": {"cost": 17}, "gross_amount": 25,
                    "senders": [{"user_id": 444, "cost": 9}]}
        cost, reason = seller_shipping_cost(response, 123)
        self.assertIsNone(cost)
        self.assertTrue(reason)

    def test_ambiguous_sender_and_invalid_amount_fail_closed(self):
        self.assertIsNone(seller_shipping_cost({"senders": [
            {"user_id": 123, "cost": 8}, {"user_id": 123, "cost": 9}]}, 123)[0])
        self.assertIsNone(seller_shipping_cost({"senders": [
            {"user_id": 123, "cost": "NaN"}]}, 123)[0])
        self.assertIsNone(seller_shipping_cost({"senders": [
            {"user_id": 123, "cost": -1}]}, 123)[0])
        self.assertIsNone(seller_shipping_cost({"senders": []}, 123)[0])
        self.assertIsNone(seller_shipping_cost(None, 123)[0])

    def test_item_quantity_and_unknown_multiseller(self):
        self.assertEqual(seller_shipment_item_count([
            {"sender_id": 123, "quantity": 2},
            {"sender_id": 123, "quantity": 1}], 123), 3)
        self.assertIsNone(seller_shipment_item_count([
            {"sender_id": 123, "quantity": 1},
            {"sender_id": 456, "quantity": 1}], 123))
        self.assertIsNone(seller_shipment_item_count([
            {"sender_id": 123, "quantity": "1"}], 123))
        self.assertIsNone(seller_shipment_item_count({}, 123))


if __name__ == "__main__":
    unittest.main()
