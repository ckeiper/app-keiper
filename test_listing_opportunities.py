import unittest
from listing_opportunities import listing_opportunities, opportunity_actions


class ListingOpportunitiesTests(unittest.TestCase):
    def test_prioritizes_interruption_and_material_decline(self):
        rows = {
            "A": {"orders": 0, "previous_orders": 8},
            "B": {"orders": 2, "previous_orders": 7},
            "C": {"orders": 0, "previous_orders": 0},
            "D": {"orders": 0, "previous_orders": 1},
        }
        signals = listing_opportunities(rows)
        self.assertEqual([s["item_id"] for s in signals], ["A", "B"])
        self.assertEqual(signals[0]["kind"], "interrupcao")

    def test_no_signal_for_small_samples_or_growth(self):
        self.assertEqual(listing_opportunities({
            "A": {"orders": 2, "previous_orders": 3},
            "B": {"orders": 9, "previous_orders": 4},
        }), [])

    def test_actions_are_investigations_not_causal_claims(self):
        for kind in ("interrupcao", "queda"):
            steps = opportunity_actions(kind)
            self.assertEqual(len(steps), 3)
            self.assertTrue(all(isinstance(step, str) for step in steps))
        self.assertEqual(opportunity_actions("unknown"), ())

    def test_limit_and_stable_order(self):
        rows = {str(i): {"orders": 0, "previous_orders": 5} for i in range(8)}
        self.assertEqual(len(listing_opportunities(rows, limit=3)), 3)


if __name__ == "__main__":
    unittest.main()
