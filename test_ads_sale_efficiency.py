import unittest
from decimal import Decimal
from copy import deepcopy
from ads_sale_efficiency import metrics,comparison,render

class SaleEfficiencyTests(unittest.TestCase):
 def window(self,**kw):return dict(spend=100,revenue=1000,attributed_sales=5,**kw)
 def test_exact_averages_and_deltas(self):
  old=self.window();new=dict(old,spend=150,revenue=900)
  r=comparison(new,old)
  self.assertEqual(r['rows'][0]['current'],30);self.assertEqual(r['rows'][0]['delta'],10)
  self.assertEqual(r['rows'][0]['percent'],50)
  self.assertEqual(r['rows'][1]['delta'],-20)
 def test_missing_and_invalid_counts(self):
  for v in [None,True,-1,'NaN','Infinity','2.5','bad']:
   self.assertFalse(metrics(dict(self.window(),attributed_sales=v))['available'])
 def test_zero_sales_does_not_become_infinite_cost(self):
  r=metrics(dict(self.window(),attributed_sales=0));self.assertFalse(r['available'])
  self.assertIn('Nenhuma venda',r['reason'])
 def test_zero_spend_and_zero_revenue_remain_real_zero(self):
  r=metrics(dict(self.window(),spend=0,revenue=0));self.assertTrue(r['available'])
  self.assertEqual(r['cost'],0);self.assertEqual(r['revenue'],0)
 def test_zero_baseline_has_no_percentage(self):
  r=comparison(self.window(),dict(self.window(),spend=0,revenue=0))
  self.assertTrue(all(row['percent'] is None for row in r['rows']))
 def test_invalid_amounts_and_missing_window(self):
  for v in [None,True,-1,'NaN','Infinity']:
   for k in ['spend','revenue']:self.assertFalse(metrics(dict(self.window(),**{k:v}))['available'])
  self.assertFalse(metrics(None)['available'])
 def test_inputs_not_mutated_and_proportional_counts(self):
  old=self.window();before=deepcopy(old)
  r=comparison(dict(spend=200,revenue=2000,attributed_sales=10),old)
  self.assertTrue(all(row['delta']==0 for row in r['rows']));self.assertEqual(old,before)
 def test_render_missing_and_scope_caveats(self):
  html=render(None,self.window());self.assertNotIn('<table',html)
  self.assertIn('Ausência de dados não é zero',html)
  html=render(self.window(),self.window())
  self.assertIn('Não é custo de aquisição',html);self.assertIn('não comprova causalidade',html)
