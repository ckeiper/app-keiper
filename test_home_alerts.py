import contextlib
import unittest
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

from flask import Flask, jsonify
from home_alerts import evaluate, render, LABELS
from sales_metrics import SAO_PAULO
from test_listing_details import main_function


class HomeAlertTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 23, 12, tzinfo=SAO_PAULO)
        self.campaign = dict(conexao_id=1, campanha_id='a', nome='<Campanha>', status='active',
                             orcamento=100, roas_objetivo=5, atualizado_em=self.now.timestamp())
        self.today = dict(conexao_id=1, campanha_id='a', data='2026-10-23', gasto=95,
                          faturamento=100, impressoes=5, atualizado_em=self.now.timestamp())

    def groups(self, campaign=None, rows=None):
        return evaluate([campaign or self.campaign], [self.today] if rows is None else rows, self.now).get('1', {})

    def history(self, revenue=100):
        rows = [self.today]
        for offset in range(1, 15):
            rows.append(dict(self.today, data=(self.now.date()-timedelta(days=offset)).isoformat(),
                             gasto=10, faturamento=revenue if offset <= 7 else 200))
        return rows

    def test_forecast_pacing_and_exhaustion(self):
        self.assertIn('forecast', self.groups())
        self.assertIn('pacing', self.groups())
        groups = self.groups(rows=[dict(self.today, gasto=100)])
        self.assertIn('budget', groups)
        self.assertNotIn('forecast', groups)
        self.assertIn('budget', self.groups(campaign=dict(self.campaign, orcamento=0)))

    def test_unknown_and_stale_never_become_zero_delivery_or_budget(self):
        self.assertEqual(set(self.groups(rows=[])), {'quality'})
        self.assertEqual(set(self.groups(rows=[dict(self.today, atualizado_em=self.now.timestamp()-7201)])), {'quality'})
        self.assertNotIn('delivery', self.groups(rows=[dict(self.today, impressoes=None)]))
        self.assertIn('delivery', self.groups(rows=[dict(self.today, impressoes=0)]))
        self.assertEqual(self.groups(campaign=dict(self.campaign, status='paused')), {})
        self.assertNotIn('forecast', self.groups(rows=[dict(self.today, atualizado_em=self.now.timestamp()-301)]))

    def test_complete_history_and_minimum_spend_for_performance(self):
        self.assertIn('growth', self.groups(rows=self.history()))
        self.assertIn('decline', self.groups(rows=self.history()))
        self.assertIn('cost', self.groups(rows=self.history(20)))
        self.assertNotIn('growth', self.groups(rows=self.history()[:-1][:-7]))
        self.assertNotIn('cost', self.groups(rows=self.history(0)))

    def test_no_cross_store_history_and_escaped_details(self):
        rows = [dict(row, conexao_id=2) for row in self.history()]
        self.assertEqual(set(self.groups(rows=rows)), {'quality'})
        html = render(self.groups(), 1, True)
        self.assertIn('&lt;Campanha&gt;', html)
        self.assertIn('/ads/1/campanha/a', html)
        self.assertEqual(set(LABELS), {'budget','forecast','pacing','delivery','cost','decline','quality','growth'})

    def test_route_denies_other_store_before_read(self):
        namespace = dict(pode_ver_loja=lambda cid: False, jsonify=jsonify)
        handler = main_function('painel_alertas', namespace)
        app = Flask(__name__)
        with app.test_request_context():
            response, status = handler(99)
            self.assertEqual(status, 403)

    def test_route_returns_only_scoped_summary_and_no_cache(self):
        load = Mock(return_value=({'budget':[{'name':'secret detail'}]}, True))
        handler = main_function('painel_alertas', dict(pode_ver_loja=lambda cid:cid==1,
            jsonify=jsonify, banco=Mock(), consultar=Mock()))
        app = Flask(__name__)
        with app.test_request_context(), patch('home_alerts.load', load):
            response = handler(1)
            self.assertEqual(load.call_args.args[0], 1)
            self.assertEqual(response.headers['Cache-Control'], 'no-store')
            self.assertNotIn('secret detail', response.get_data(as_text=True))

    def test_home_refresh_fetches_today_only_and_persists_real_impressions(self):
        from test_ads_reporting_day import AdsReportingDayTests
        harness = AdsReportingDayTests()
        collect = harness.collector(pending=['2026-10-19'])
        today = date(2026, 10, 21)
        with patch('sales_metrics.reporting_today', return_value=today):
            self.assertTrue(collect(5, 'test-token', 1, refresh_range=(today,today)))
        self.assertEqual(harness.requested, ['2026-10-21'])
        saved = [params for sql, params in harness.written if 'INSERT INTO ads_campanha_dia' in sql]
        self.assertEqual(saved[0][-1], 100)

    def test_config_failure_cannot_report_fully_refreshed_ads(self):
        from test_ads_reporting_day import AdsReportingDayTests
        harness = AdsReportingDayTests()
        collect = harness.collector()
        requests = collect.__globals__['requests']
        original = requests.get
        def get(url, **kwargs):
            if 'params' in kwargs and not kwargs['params'].get('date_from'):
                return SimpleNamespace(status_code=503, text='Unavailable')
            return original(url, **kwargs)
        requests.get = get
        today = date(2026, 10, 21)
        with patch('sales_metrics.reporting_today', return_value=today):
            self.assertFalse(collect(5, 'test-token', 1, refresh_range=(today,today)))


if __name__ == '__main__':
    unittest.main()
