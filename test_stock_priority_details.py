import unittest
from decimal import Decimal
from listing_priority_sources import listing_signals
from listing_priority_evidence import enrich_priorities
from listing_action_plan import build,render

NOW=1800000000
RANKING=dict(available=True,rows={'MLB1':dict(units=21)})

class StockPriorityDetailsTests(unittest.TestCase):
    def signals(self, **changes):
        row=dict(item_id='MLB1',quantidade=12,atualizado_em=NOW)
        row.update(changes)
        return listing_signals([row],RANKING,7,now=NOW)['MLB1']

    def test_timestamp_contract_and_six_hour_boundary(self):
        for stamp in [True,False,0,-1,NOW+.5,NOW-0.5,'bad',float('nan'),float('inf'),NOW-21601]:
            with self.subTest(stamp=stamp):
                self.assertFalse(self.signals(atualizado_em=stamp)['stock_verified'])
        self.assertTrue(self.signals(atualizado_em=NOW-21600)['stock_verified'])
        self.assertTrue(self.signals(atualizado_em=str(NOW))['stock_verified'])

    def test_stock_and_velocity_must_be_nonnegative_integer_units(self):
        for stock in [True,False,-1,1.5,None]:
            self.assertFalse(self.signals(quantidade=stock)['stock_verified'])
        row=dict(item_id='MLB1',quantidade=12,atualizado_em=NOW)
        for units in [True,False,1.5,-1,None,float('inf')]:
            ranking=dict(available=True,rows={'MLB1':dict(units=units)})
            signals=listing_signals([row],ranking,7,now=NOW)['MLB1']
            self.assertTrue(signals['stock_verified'])
            self.assertNotIn('daily_units',signals)
        self.assertNotIn('daily_units',listing_signals([row],RANKING,True,now=NOW)['MLB1'])

    def test_coverage_shows_observed_basis_and_plan_uses_it(self):
        queue=dict(available=True,items=[dict(item_id='MLB1')])
        row=enrich_priorities(queue,{'MLB1':self.signals()})['items'][0]
        finding=row['additional_findings'][0]
        self.assertEqual(finding['code'],'stock_coverage')
        self.assertIn('4,00 dias',finding['evidence'])
        self.assertIn('12 unidades registradas',finding['evidence'])
        self.assertIn('21 unidades vendidas em 7 dias encerrados',finding['evidence'])
        self.assertIn('sem previsão de demanda',finding['evidence'])
        self.assertEqual(build(row)['steps'][0]['evidence'],finding['evidence'])
        self.assertIn('4,00 dias',render(row))

    def test_exact_threshold_and_small_rate_no_false_zero(self):
        queue=dict(available=True,items=[dict(item_id='MLB1')])
        def evidence(stock,rate):
            return enrich_priorities(queue,{'MLB1':dict(stock_verified=True,stock=stock,daily_units=rate)})['items'][0]['additional_findings']
        self.assertEqual(evidence(21,3),[])
        self.assertIn('6,99 dias',evidence(20,Decimal('2.86'))[0]['evidence'])
        self.assertIn('<0,01 dias',evidence(1,1000)[0]['evidence'])
        self.assertIn('&lt;0,01 dias',render(dict(additional_findings=evidence(1,1000))))

    def test_stale_stock_never_generates_an_operational_finding(self):
        queue=dict(available=True,items=[dict(item_id='MLB1')])
        row=enrich_priorities(queue,{'MLB1':self.signals(atualizado_em=NOW-21601,quantidade=0)})['items'][0]
        self.assertEqual(row['additional_findings'],[])
        self.assertIn('estoque',row['data_limitations'])
