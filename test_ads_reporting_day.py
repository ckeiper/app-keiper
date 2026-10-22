"""Exercise the actual collector without importing the production app."""
import ast
from contextlib import nullcontext
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from ads_coverage import daily_days_to_fetch
from sales_metrics import reporting_today


class AdsReportingDayTests(unittest.TestCase):
    def test_after_midnight_utc_is_still_previous_day_in_brazil(self):
        import sales_metrics
        class FrozenDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                return datetime(2026, 10, 22, 1, 30, tzinfo=timezone.utc).astimezone(tz)
        with patch.object(sales_metrics, 'datetime', FrozenDatetime):
            self.assertEqual(reporting_today(), date(2026, 10, 21))

    def test_yesterday_is_refreshed_even_when_already_saved(self):
        today = date(2026, 10, 21)
        known = [(today.fromordinal(today.toordinal()-i)).isoformat() for i in range(1, 90)]
        self.assertEqual(daily_days_to_fetch(known, today), ['2026-10-20'])

    def test_refresh_keeps_bounded_repairs_and_deduplicates_yesterday(self):
        today = date(2026, 10, 21)
        days = daily_days_to_fetch([], today, max_recent=3)
        self.assertEqual(len(days), 4)
        self.assertEqual(days[0], '2026-10-20')
        self.assertNotIn(today.isoformat(), days)
        days = daily_days_to_fetch([], today, initial=True)
        self.assertEqual(len(days), 89)
        self.assertEqual(len(days), len(set(days)))

    def collector(self, failed_day=None, official=None, pending=None):
        import datetime as datetime_module
        import time
        tree = ast.parse(Path('main.py').read_text())
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'puxar_ads')
        self.requested = []
        self.written = []
        self.errors = []
        def get(url, **kwargs):
            if url.endswith('/advertising/advertisers'):
                return SimpleNamespace(status_code=200, json=lambda: [{'advertiser_id': 1, 'site_id': 'MLB'}])
            params = kwargs['params']
            day = params.get('date_from')
            if day:
                self.assertIn('organic_items_quantity',params['metrics'])
                self.assertIn('advertising_items_quantity',params['metrics'])
                self.requested.append(day)
            if day == failed_day and failed_day is not None:
                return SimpleNamespace(status_code=503, text='Unavailable')
            result = {'results': [{'id': 9, 'metrics': {'cost': 15, 'total_amount': 90,
                       'prints': 100, 'clicks': 5}}], 'paging': {'total': 1}}
            result['results'][0]['metrics'].update(official or {})
            return SimpleNamespace(status_code=200, json=lambda: result)
        def query(conn, sql, params):
            if 'metricas_vendas_coletadas_em IS NULL' in sql:
                return [{'data': d} for d in (pending or [])]
            if 'SELECT data FROM ads_dia' in sql:
                self.bounds = params
                return [{'data': date(2026, 10, 21).fromordinal(date(2026, 10, 21).toordinal()-i).isoformat()}
                        for i in range(1, 90)]
            return []
        namespace = dict(datetime=datetime_module, time=time, API='https://example.invalid',
                         requests=SimpleNamespace(get=get, RequestException=RuntimeError),
                         banco=lambda: nullcontext(object()), consultar=query,
                         executar=lambda conn, sql, params: self.written.append((sql, params)),
                         registrar_erro=lambda *args: self.errors.append(args))
        exec(compile(ast.Module(body=[node], type_ignores=[]), 'main.py', 'exec'), namespace)
        return namespace['puxar_ads']

    def test_collector_uses_one_brazilian_date_and_updates_previous_day(self):
        collect = self.collector()
        with patch('sales_metrics.reporting_today', return_value=date(2026, 10, 21)) as today:
            self.assertTrue(collect(5, 'test-token', 1))
        today.assert_called_once()
        self.assertEqual(self.requested, ['2026-10-21', '2026-10-20'])
        self.assertEqual(self.bounds, (5, '2026-07-24', '2026-10-20'))
        snapshots = [params for sql, params in self.written if 'INSERT INTO ads_dia' in sql]
        self.assertEqual([p[1] for p in snapshots], self.requested)
        self.assertTrue(all(p[2:6] == (15.0, 90.0, 100, 5) for p in snapshots))

    def test_failed_yesterday_request_does_not_overwrite_with_zero(self):
        collect = self.collector(failed_day='2026-10-20')
        with patch('sales_metrics.reporting_today', return_value=date(2026, 10, 21)):
            collect(5, 'test-token', 1)
        snapshots = [params for sql, params in self.written if 'INSERT INTO ads_dia' in sql]
        self.assertEqual([p[1] for p in snapshots], ['2026-10-21'])
        self.assertEqual(self.errors[0][1], 'ads')

    def test_official_campaign_sales_persist_for_today_and_history(self):
        collect=self.collector(official={'advertising_items_quantity':3,
            'organic_items_quantity':7,'organic_units_amount':123.45})
        with patch('sales_metrics.reporting_today',return_value=date(2026,10,21)):
            collect(5,'test-token',1)
        rows=[params for sql,params in self.written if 'INSERT INTO ads_campanha_dia' in sql]
        self.assertEqual(len(rows),2)
        self.assertEqual([r[2] for r in rows],['2026-10-21','2026-10-20'])
        self.assertTrue(all(r[6:9]==(3,7,123.45) for r in rows))

    def test_absent_official_fields_remain_unknown_and_legacy_days_are_enriched(self):
        collect=self.collector(pending=['2026-10-20','2026-10-19'])
        with patch('sales_metrics.reporting_today',return_value=date(2026,10,21)):
            collect(5,'test-token',1)
        self.assertEqual(self.requested,['2026-10-21','2026-10-20','2026-10-19'])
        rows=[params for sql,params in self.written if 'INSERT INTO ads_campanha_dia' in sql]
        self.assertTrue(all(r[6:9]==(None,None,None) for r in rows))


if __name__ == '__main__':
    unittest.main()
