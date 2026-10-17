"""Regression tests for the overview query performance fix."""
import unittest
from datetime import date, datetime, timedelta, timezone

from overview_store import DAILY_SQL, UNUSUAL_SQL
from sales_metrics import created_day


def sql_native_equivalent(iso):
    """Python counterpart of the native UTC -> fixed -03:00 SQL expression."""
    stamp = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return (stamp.astimezone(timezone.utc) - timedelta(hours=3)).date()


class OverviewQueryPerformanceTests(unittest.TestCase):
    def test_canonical_dates_preserve_reporting_day(self):
        for iso in (
            "2026-10-17T00:15:00Z",
            "2026-10-16T23:59:59-03:00",
            "2026-10-17T01:30:00+02:00",
            "2026-10-17T23:59:59.123456+00:00",
            "2026-10-17T03:00:00Z",
            "2026-10-17 12:00:00-03:00",
        ):
            with self.subTest(iso=iso):
                self.assertEqual(created_day(iso), sql_native_equivalent(iso))

    def test_indexed_classifier_still_guards_canonical_selection(self):
        self.assertIn("keiper_overview_day_v1(criado_em) IS NOT NULL", DAILY_SQL)
        self.assertIn("keiper_overview_day_v1(criado_em) BETWEEN %s AND %s", DAILY_SQL)
        self.assertIn("keiper_overview_day_v1(criado_em) IS NULL", UNUSUAL_SQL)

    def test_fast_native_conversion_used_only_for_canonical_grouping(self):
        self.assertIn("criado_em::timestamptz AT TIME ZONE 'UTC'", DAILY_SQL)
        self.assertIn("INTERVAL '3 hours')::date AS dia", DAILY_SQL)
        self.assertIn("payment_checks AS MATERIALIZED", DAILY_SQL)
        self.assertNotIn("keiper_overview_day_v1(criado_em) AS dia", DAILY_SQL)


if __name__ == "__main__":
    unittest.main()
