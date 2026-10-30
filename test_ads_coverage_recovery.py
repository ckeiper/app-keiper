"""Regression tests for Ads missing-day recovery and honest coverage messaging."""
import unittest
from datetime import date, timedelta
from decimal import Decimal
from ads_coverage import missing_days_to_fetch
from management_data import advertising


class AdsRecoveryTests(unittest.TestCase):
    def test_established_store_repairs_recent_gap_even_after_sixty_days(self):
        today=date(2026,10,22)
        known=[(today-timedelta(days=i)).isoformat() for i in range(1,90) if i!=5]
        self.assertEqual(missing_days_to_fetch(known,today,initial=False),['2026-10-17'])

    def test_retry_is_bounded_and_never_uses_today(self):
        today=date(2026,10,22)
        result=missing_days_to_fetch([],today,max_recent=3)
        self.assertEqual(result,['2026-09-22','2026-09-23','2026-09-24'])
        self.assertNotIn(today.isoformat(),result)

    def test_initial_backfill_does_not_redownload_existing_days(self):
        today=date(2026,10,22)
        self.assertNotIn('2026-10-21',missing_days_to_fetch(['2026-10-21'],today,initial=True))
        self.assertEqual(len(missing_days_to_fetch(['2026-10-21'],today,initial=True)),88)

    def test_missing_day_blocks_ratios_and_names_missing_date(self):
        rows=[dict(data='2026-10-19',gasto=5,faturamento=40,cliques=3,impressoes=100)]
        result=advertising(rows,date(2026,10,19),date(2026,10,20))
        self.assertEqual(result['missing_dates'],['2026-10-20'])
        self.assertEqual(result['coverage'],1)
        self.assertIsNone(result['spend'])
        self.assertIsNone(result['roas'])
        self.assertIsNone(result['acos'])
        full=advertising(rows,date(2026,10,19),date(2026,10,19))
        self.assertEqual(full['spend'],Decimal(5))
        self.assertEqual(full['missing_dates'],[])
        self.assertEqual(full['roas'],Decimal(8))

    def test_management_view_explains_and_offers_real_retry_route(self):
        from pathlib import Path
        source=Path('management_view.py').read_text()
        self.assertIn('Faltam:',source)
        self.assertIn('/ads/',source)
        self.assertIn('não tratamos lacunas como gasto zero',source)


if __name__=='__main__':
    unittest.main()
