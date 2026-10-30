import unittest
from copy import deepcopy
from decimal import Decimal as D
from datetime import timedelta
from competitive_sales_context import build,render
from test_listing_competitiveness import data,END,STAMP


def fixture():
    offers=data()
    for row in list(offers['own']):offers['own'].append(dict(row,observed_at=row['observed_at']-7*86400,price=90))
    for row in list(offers['competitors']):offers['competitors'].append(dict(row,observed_at=row['observed_at']-7*86400))
    ranking=dict(available=True,rows={'MLB1':dict(value=D(100),previous_value=D(200),orders=2,previous_orders=4,units=3,previous_units=5)})
    return ranking,offers


class CompetitiveSalesContextTests(unittest.TestCase):
    def test_exact_sales_and_sample_changes_without_mutation(self):
        ranking,offers=fixture();original=deepcopy([ranking,offers])
        result=build(ranking,'MLB1',offers,END)
        self.assertTrue(result['available']);self.assertEqual(result['delta'],D(-100))
        self.assertEqual(result['delta_pct'],D(-50))
        row=result['rows'][0]
        self.assertEqual(row['previous_above_pct'],D(0));self.assertEqual(row['current_above_pct'],D(50))
        self.assertEqual(row['change_pp'],D(50));self.assertIn('Queda bruta e maior proporção',row['status'])
        self.assertEqual([ranking,offers],original)

    def test_missing_period_pairs_never_generate_comparison(self):
        r,o=fixture();o['competitors']=[row for row in o['competitors'] if row['observed_at']>STAMP-86400]
        result=build(r,'MLB1',o,END)['rows'][0]
        self.assertIsNone(result['previous_above_pct']);self.assertIsNone(result['change_pp'])
        self.assertEqual(result['status'],'Comparação competitiva pendente')
        self.assertIn('Sem pares comparáveis',render(r,'MLB1',o,END))

    def test_invalid_or_foreign_sales_never_show_zero_or_loss(self):
        for changes in [dict(value=None),dict(value=True),dict(value=D('NaN')),dict(previous_value=-1),dict(orders=D('1.5'))]:
            r,o=fixture();r['rows']['MLB1'].update(changes)
            self.assertFalse(build(r,'MLB1',o,END)['available'])
        r,o=fixture();self.assertFalse(build(r,'MLB999',o,END)['available'])
        r['available']=False;text=render(r,'MLB1',o,END)
        self.assertNotIn('<table',text);self.assertNotIn('Variação bruta',text)
        self.assertIn('Dados incompletos não são zero',text)

    def test_zero_previous_has_no_false_percent_and_growth_is_not_loss(self):
        r,o=fixture();r['rows']['MLB1']['previous_value']=D(0)
        result=build(r,'MLB1',o,END)
        self.assertIsNone(result['delta_pct']);self.assertFalse(result['declining'])
        self.assertEqual(result['rows'][0]['status'],'Sem queda bruta entre os períodos')
        self.assertIn('Sem base percentual anterior',render(r,'MLB1',o,END))
        r['rows']['MLB1'].update(value=D(0),previous_value=D(200))
        self.assertEqual(build(r,'MLB1',o,END)['delta_pct'],D(-100))

    def test_limited_history_never_emits_competitive_exposure_conclusion(self):
        for flag in ['history_limited','targets_limited']:
            r,o=fixture();o[flag]=True
            result=build(r,'MLB1',o,END)
            self.assertIn('Histórico limitado',result['rows'][0]['status'])
            self.assertNotIn('Queda bruta e maior proporção',render(r,'MLB1',o,END))
            self.assertIn('nenhuma conclusão',render(r,'MLB1',o,END))

    def test_invalid_and_duplicate_price_reads_remain_out_of_valid_denominator(self):
        r,o=fixture();o['competitors'].append(dict(target_id=1,observed_at=STAMP+3000,price=None,error='failed'))
        row=build(r,'MLB1',o,END)['rows'][0]
        self.assertEqual(row['current']['observed'],3);self.assertEqual(row['current']['valid'],2)
        self.assertEqual(row['current_above_pct'],D(50))
        o['competitors'].append(dict(o['competitors'][1]))
        row=build(r,'MLB1',o,END)['rows'][0]
        self.assertEqual(row['current']['valid'],1);self.assertEqual(row['current_above_pct'],D(0))
        self.assertIn('sem aumento',row['status'])

    def test_scope_dates_escaping_and_no_causal_or_financial_claim(self):
        r,o=fixture();o['targets'][0]['label']='<script>'
        text=render(r,'MLB1',o,END)
        self.assertIn('&lt;script&gt;',text);self.assertNotIn('<script>',text)
        for phrase in ['10/10/2026 a 16/10/2026','17/10/2026 a 23/10/2026','R$ 200,00 → R$ 100,00','Coincidência não comprova causa','sem ponderação por tempo ou vendas']:
            self.assertIn(phrase,text)
        text=render(r,'MLB1',o,END,30)
        self.assertIn('25/08/2026 a 23/09/2026',text);self.assertIn('24/09/2026 a 23/10/2026',text)

    def test_no_targets_shows_sales_but_no_invented_competitiveness(self):
        r,o=fixture();o['targets']=[]
        result=build(r,'MLB1',o,END)
        self.assertTrue(result['available']);self.assertEqual(result['rows'],[])
        text=render(r,'MLB1',o,END)
        self.assertIn('Sem concorrentes vinculados',text);self.assertNotIn('<table',text)
