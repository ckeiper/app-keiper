import unittest
from datetime import date
from page_performance import ranking_query_bounds


class RankingPerformanceTests(unittest.TestCase):
    def test_seven_day_bounds_include_both_periods_and_timezone_margin(self):
        self.assertEqual(
            ranking_query_bounds(7, date(2026, 10, 17)),
            ("2026-10-03", "2026-10-18", "2026-10-04", "2026-10-17"))

    def test_thirty_day_bounds(self):
        self.assertEqual(
            ranking_query_bounds(30, date(2026, 10, 17)),
            ("2026-08-18", "2026-10-18", "2026-08-19", "2026-10-17"))

    def test_unbounded_window_rejected(self):
        with self.assertRaises(ValueError):
            ranking_query_bounds(365, date(2026, 10, 17))


if __name__ == "__main__":
    unittest.main()
