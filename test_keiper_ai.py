import copy
import os
import unittest
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch, Mock

from keiper_ai import recommendations, render
from keiper_ai_budget import settings, limit_brl, price, interpret, budget_status
from sales_metrics import SAO_PAULO


class RulesTests(unittest.TestCase):
    def setUp(self):
        self.today = date(2026, 10, 23)
        self.now = datetime(2026,10,23,10,tzinfo=SAO_PAULO).timestamp()
        self.report = dict(eligible=True, reasons=[], current=dict(revenue=700, orders=70),
                           previous=dict(revenue=1400, orders=100))
        self.ads = [dict(data=(self.today-timedelta(days=i)).isoformat(),
                         gasto=20, faturamento=0 if i <= 7 else 100,
                         atualizado_em=int(self.now)) for i in range(1,15)]

    def analyze(self):
        return recommendations(self.report, self.ads, self.today, self.now)

    def test_top_three_evidence_and_closed_windows(self):
        result = self.analyze()
        self.assertEqual([x['code'] for x in result['recommendations']], ['ads_no_revenue','tacos','revenue'])
        self.assertEqual(result['start'],'2026-10-16')
        self.assertEqual(result['end'],'2026-10-22')
        self.assertEqual(result['previous_start'],'2026-10-09')
        self.assertEqual(result['recommendations'][0]['evidence']['spend'],140)

    def test_missing_sales_not_zero_and_no_cross_signal(self):
        self.report.update(eligible=False, reasons=['Cobertura incompleta'])
        codes = [r['code'] for r in self.analyze()['recommendations']]
        self.assertEqual(codes,['data_quality','ads_no_revenue'])

    def test_partial_invalid_missing_old_ads_not_used(self):
        for mutation in ('missing','partial','nan','future','stale'):
            with self.subTest(mutation=mutation):
                original=copy.deepcopy(self.ads)
                if mutation == 'missing': self.ads.pop()
                if mutation == 'partial': self.ads[0]['atualizado_em']=int(self.now)-86400
                if mutation == 'nan': self.ads[0]['gasto']=float('nan')
                if mutation == 'future': self.ads[0]['atualizado_em']=int(self.now)+1
                if mutation == 'stale': self.ads[-1]['atualizado_em']=int(self.now)-8*86400
                result=self.analyze()
                self.assertTrue(result['quality'])
                self.assertFalse(any(r['code'] in ('roas','ads_no_revenue','tacos') for r in result['recommendations']))
                self.ads=original

    def test_roas_drop_and_no_false_zero_baseline(self):
        for r in self.ads: r['faturamento']=20 if r['data'] >= '2026-10-16' else 100
        self.assertIn('roas',[r['code'] for r in self.analyze()['recommendations']])
        self.report['previous']=dict(revenue=0,orders=0)
        self.ads=[]
        self.assertEqual([r['code'] for r in self.analyze()['recommendations']],['data_quality'])

    def test_render_escapes_model_and_evidence(self):
        result=self.analyze()
        result['interpretation']='<script>alert(1)</script>'
        result['recommendations'][0]['evidence']={'x':'<img onerror=x>'}
        html=render(result,'2026-10-23')
        self.assertNotIn('<script>',html)
        self.assertNotIn('<img',html)
        self.assertIn('&lt;script&gt;',html)


class BudgetTests(unittest.TestCase):
    def config(self):
        return dict(KEIPER_AI_PAID_ENABLED='true',KEIPER_AI_PAID_CONFIRMATION='APPROVED',
                    OPENAI_API_KEY='test-only',KEIPER_AI_MODEL='test-model',
                    KEIPER_AI_INPUT_USD_PER_MILLION='1',KEIPER_AI_OUTPUT_USD_PER_MILLION='4',KEIPER_AI_USD_BRL='6')

    def test_all_gates_required_and_bad_prices_fail_closed(self):
        env=self.config()
        self.assertIsNotNone(settings(env))
        for key in env:
            missing=dict(env); missing.pop(key)
            self.assertIsNone(settings(missing),key)
        for value in ('NaN','Infinity','-1','0','garbage'):
            env['KEIPER_AI_USD_BRL']=value
            self.assertIsNone(settings(env))
            self.assertEqual(limit_brl({'KEIPER_AI_MONTHLY_BRL':value}),0)
        self.assertEqual(limit_brl({}),50)

    def test_price_rounds_up(self):
        self.assertEqual(price(1000,500,settings(self.config())),Decimal('.018000'))

    def test_disabled_never_connects_or_calls_provider(self):
        db,post=Mock(),Mock()
        with patch.dict(os.environ,{},clear=True):
            self.assertIsNone(interpret(1,{},db,Mock(),Mock(),post)[0])
        db.assert_not_called(); post.assert_not_called()

    def test_budget_alerts_and_circuit_breaker(self):
        with patch.dict(os.environ,{},clear=True):
            for used,overrun,blocked,alert in ((39,False,False,'Dentro'),(40,False,False,'80%'),
                                             (50,False,True,'Bloqueio'),(1,True,True,'Bloqueio')):
                query=Mock(return_value=[dict(used=Decimal(used),overrun=overrun)])
                state=budget_status(None,query,date(2026,10,23))
                self.assertEqual(state['blocked'],blocked)
                self.assertIn(alert,state['alert'])


if __name__ == '__main__':
    unittest.main()
