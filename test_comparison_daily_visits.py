import unittest
from decimal import Decimal
from unittest.mock import Mock
from listing_comparison import load_visits,render_daily,render
from test_listing_comparison import sample,END
from test_listing_comparison_visits import observations

class ComparisonDailyVisitsTests(unittest.TestCase):
 def data(self,rows=None):
  query=Mock(return_value=observations() if rows is None else rows)
  data=load_visits(None,query,1,['MLB1','MLB2'],END)
  self.assertEqual(query.call_count,1)
  return data
 def test_same_read_exposes_valid_daily_numbers_and_preserves_totals(self):
  data=self.data()
  self.assertEqual(data['MLB1']['daily'][END.isoformat()],10)
  self.assertEqual(len(data['MLB1']['daily']),14)
  self.assertEqual(sum(data['MLB1']['daily'].values()),210)
  self.assertEqual(data['MLB1']['current']['totals']['visitas'],70)
 def test_zero_missing_duplicate_and_invalid_stay_distinct(self):
  for mode in ['zero','missing','duplicate','invalid']:
   rows=observations()
   target=next(r for r in rows if r['item_id']=='MLB1' and r['dia']==END.isoformat())
   if mode=='zero':target['visitas']=0
   elif mode=='missing':rows.remove(target)
   elif mode=='duplicate':rows.append(dict(target))
   else:target['visitas']=True
   data=self.data(rows)
   self.assertEqual(data['MLB1']['daily'][END.isoformat()],Decimal(0) if mode=='zero' else None)
 def test_pagination_preserves_normalized_selection_and_period(self):
  data=self.data()
  text=render_daily(42,['MLB2','MLB1'],{},data,dict(leituras_pagina='2'),END,7)
  self.assertIn('Página 2 de 2',text);self.assertIn('comparar1=MLB2&amp;comparar2=MLB1&amp;dias=7&amp;leituras_pagina=1#lc-leituras',text)
  self.assertEqual(text.count('<tr><th scope="row">'),7)
  self.assertIn('16/10/2026',text);self.assertIn('<small>Anterior</small>',text)
  self.assertNotIn('23/10/2026',text)
 def test_invalid_page_limits_and_thirty_day_window_are_bounded(self):
  data=self.data()
  text=render_daily(42,['MLB1','MLB2'],{},data,dict(leituras_pagina='999'),END,30)
  self.assertIn('Página 9 de 9',text);self.assertEqual(text.count('<tr><th scope="row">'),4)
  for value in ['bad','-100','"><script>']:
   text=render_daily(42,['MLB1','MLB2'],{},data,dict(leituras_pagina=value),END,7)
   self.assertIn('Página 1 de 2',text);self.assertNotIn('<script>',text)
 def test_main_comparison_shows_gaps_without_losing_sales_or_untrusted_text(self):
  rows=observations();rows=[r for r in rows if not(r['item_id']=='MLB1' and r['dia']==END.isoformat())]
  data=self.data(rows);ranking,listings=sample();listings[0]['titulo']='<script>'
  text=render(1,ranking,listings,dict(comparar1='MLB1',comparar2='MLB2'),END,visits=data)
  self.assertIn('R$ 200,00 → R$ 100,00',text)
  self.assertIn('Sem dado válido',text);self.assertIn('&lt;script&gt;',text);self.assertNotIn('<script>',text)
  self.assertIn('lc-daily',text)
  self.assertEqual(render_daily(1,['MLB1','MLB2'],{},None,{},END,7),'')
