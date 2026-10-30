import unittest
from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock
from listing_comparison import load_visits,visit_cell
from test_listing_comparison import sample,END


def observations():
 return [dict(conexao_id=1,item_id='MLB'+str(i),dia=(END-timedelta(days=13-n)).isoformat(),visitas=20 if n<7 else 10)
         for i in range(1,5) for n in range(14)]

class ComparisonVisitTests(unittest.TestCase):
 def test_one_scoped_read_same_closed_windows_and_exact_rate(self):
  query=Mock(return_value=observations());r=load_visits(None,query,1,['MLB1','MLB2'],END)
  self.assertEqual(query.call_count,1)
  self.assertEqual(query.call_args.args[2],(1,['MLB1','MLB2'],'2026-10-10','2026-10-23'))
  self.assertIn('conexao_id=%s AND item_id=ANY(%s)',query.call_args.args[1])
  self.assertEqual(r['MLB1']['previous']['totals']['visitas'],140)
  self.assertEqual(r['MLB1']['current']['totals']['visitas'],70)
  ranking,_=sample();self.assertEqual(visit_cell(ranking['rows']['MLB1'],r['MLB1'],'orders_per_visit',7),'1,43% → 1,43%')
 def test_gap_duplicate_or_invalid_day_never_forms_partial_total(self):
  for mode in ['gap','duplicate','negative','boolean','fraction','nan']:
   rows=observations()
   if mode=='gap':rows=rows[1:]
   elif mode=='duplicate':rows.append(dict(rows[0]))
   else:rows[0]['visitas']={'negative':-1,'boolean':True,'fraction':'1.5','nan':'NaN'}[mode]
   r=load_visits(None,Mock(return_value=rows),1,['MLB1','MLB2'],END)['MLB1']
   self.assertFalse(r['previous']['complete']);self.assertEqual(r['previous']['covered'],6)
   self.assertIsNone(r['previous']['totals'])
   ranking,_=sample();self.assertIn('Indisponível',visit_cell(ranking['rows']['MLB1'],r,'orders_per_visit',7))
 def test_zero_visits_stays_zero_but_rate_is_unavailable(self):
  rows=observations()
  for row in rows:row['visitas']=0
  r=load_visits(None,Mock(return_value=rows),1,['MLB1','MLB2'],END)['MLB1'];ranking,_=sample()
  self.assertEqual(visit_cell(ranking['rows']['MLB1'],r,'visits',7),'0 → 0')
  self.assertIn('Indisponível',visit_cell(ranking['rows']['MLB1'],r,'orders_per_visit',7))
 def test_foreign_store_or_unknown_item_cannot_contribute(self):
  rows=observations()
  for row in rows:row['conexao_id']=2
  rows.append(dict(conexao_id=1,item_id='MLB99',dia=END.isoformat(),visitas=999))
  r=load_visits(None,Mock(return_value=rows),1,['MLB1','MLB2'],END)
  self.assertEqual(r['MLB1']['current']['covered'],0)
  self.assertFalse(r['MLB1']['current']['complete'])
 def test_invalid_selection_or_window_has_no_reads(self):
  for ids,days in [(['MLB1'],7),(['MLB1','MLB1'],7),(['MLB1','bad'],7),(['MLB1','MLB2'],1),(['MLB1','MLB2','MLB3','MLB4','MLB5'],7)]:
   query=Mock();self.assertEqual(load_visits(None,query,1,ids,END,days),{});query.assert_not_called()
