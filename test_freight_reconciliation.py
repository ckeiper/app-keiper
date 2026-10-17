import unittest
from decimal import Decimal
from freight_reconciliation import compare_normalized_freight, ReconciliationError


def ledger(tid, oid, kind, amount):
    return {"transaction_id": tid, "order_id": oid, "kind": kind, "amount": amount}


def dashboard(oid, sid, amount):
    return {"order_id": oid, "shipment_id": sid, "amount": amount}


class ReconciliationTests(unittest.TestCase):
    def test_equal_values(self):
        result = compare_normalized_freight(
            [ledger("t1", "100", "debit", "12.30")],
            [dashboard("100", "s1", "12.30")])
        self.assertEqual(result[0]["status"], "matched")
        self.assertEqual(result[0]["difference"], Decimal("0.00"))

    def test_refund_is_subtracted_before_comparison(self):
        result = compare_normalized_freight(
            [ledger("t1", "100", "debit", "20"),
             ledger("t2", "100", "refund", "5")],
            [dashboard("100", "s1", "12")])
        self.assertEqual(result[0]["ledger_net"], Decimal("15.00"))
        self.assertEqual(result[0]["difference"], Decimal("3.00"))
        self.assertEqual(result[0]["status"], "difference")

    def test_missing_data_is_not_a_divergence(self):
        result = compare_normalized_freight(
            [ledger("t1", "100", "debit", "10")],
            [dashboard("200", "s2", "10")])
        self.assertEqual([x["status"] for x in result],
                         ["missing_dashboard", "missing_ledger"])
        self.assertTrue(all(x["difference"] is None for x in result))

    def test_multiple_shipments_are_ambiguous(self):
        result = compare_normalized_freight(
            [ledger("t1", "100", "debit", "10")],
            [dashboard("100", "s1", "5"), dashboard("100", "s2", "5")])
        self.assertEqual(result[0]["status"], "ambiguous_dashboard")
        self.assertIsNone(result[0]["difference"])

    def test_duplicate_transaction_fails_closed(self):
        with self.assertRaises(ReconciliationError):
            compare_normalized_freight(
                [ledger("t1", "100", "debit", "10"),
                 ledger("t1", "100", "debit", "10")], [])

    def test_rejects_invalid_amount_and_unclassified_ledger(self):
        for amount in ["NaN", "-1", "1.234", True, None, "abc"]:
            with self.subTest(amount=amount):
                with self.assertRaises(ReconciliationError):
                    compare_normalized_freight(
                        [ledger("t1", "100", "debit", amount)], [])
        with self.assertRaises(ReconciliationError):
            compare_normalized_freight(
                [ledger("t1", "100", "fee", "5")], [])

    def test_does_not_round_small_difference_away(self):
        result = compare_normalized_freight(
            [ledger("t1", "100", "debit", "10.01")],
            [dashboard("100", "s1", "10")])
        self.assertEqual(result[0]["difference"], Decimal("0.01"))


if __name__ == "__main__":
    unittest.main()
