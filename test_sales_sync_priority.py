import datetime
import unittest
from contextlib import nullcontext
from unittest.mock import Mock, patch
from sales_sync import select_sync_days, sync_orders

class SyncPriorityTests(unittest.TestCase):
    def test_full_sync_reuses_only_recent_complete_coverage_for_today(self):
        today = datetime.date(2026, 11, 16)
        now = 1800000000
        for age, today_only, reads_today in (
            (None, False, True),
            (899, False, False),
            (900, False, True),
            (-1, False, True),
            (60, True, True),
        ):
            with self.subTest(age=age, today_only=today_only):
                rows = [] if age is None else [
                    {"dia": today.isoformat(), "atualizado_em": now - age}
                ]
                with patch("sales_sync.reporting_today", return_value=today), \
                     patch("sales_sync.time.time", return_value=now), \
                     patch("sales_sync.collect_day", return_value=({}, True, "")) as collect:
                    self.assertTrue(sync_orders(
                        1, "token", 10, nullcontext, Mock(return_value=rows),
                        Mock(), Mock(), Mock(), today_only=today_only,
                    ))
                days = [call.args[-1] for call in collect.call_args_list]
                self.assertEqual(today in days, reads_today)
                if not today_only:
                    self.assertTrue(all(
                        today - datetime.timedelta(days=i) in days for i in range(1, 7)
                    ))

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
