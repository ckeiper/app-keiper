import datetime
import unittest
from sales_sync import select_sync_days

class SyncPriorityTests(unittest.TestCase):
    def test_recent_days_are_first(self):
        today = datetime.date(2026, 10, 18)
        selected = select_sync_days(today, 1800000000, {}, older_limit=2)
        self.assertEqual(selected[:7], [today - datetime.timedelta(days=i) for i in range(7)])
        self.assertEqual(len(selected), 9)

    def test_missing_comparison_day_precedes_old_history(self):
        today = datetime.date(2026, 10, 18)
        missing = today - datetime.timedelta(days=20)
        old = today - datetime.timedelta(days=100)
        coverage = {(today - datetime.timedelta(days=i)).isoformat(): 1790000000
                    for i in range(7, 180) if i != 20}
        selected = select_sync_days(today, 1790100000, coverage, older_limit=1)
        self.assertEqual(selected[7], missing)
        self.assertNotIn(old, selected)

    def test_fresh_history_is_not_recollected(self):
        today = datetime.date(2026, 10, 18)
        now = 1790100000
        coverage = {(today - datetime.timedelta(days=i)).isoformat(): now
                    for i in range(7, 180)}
        self.assertEqual(len(select_sync_days(today, now, coverage)), 7)

if __name__ == '__main__':
    unittest.main()
