import unittest
from datetime import date,datetime,timedelta
from decimal import Decimal
from copy import deepcopy
from sales_metrics import SAO_PAULO
from listing_competitiveness import build,render

END=date(2026,10,23)
STAMP=int(datetime(2026,10,23,12,tzinfo=SAO_PAULO).timestamp())
def data():
 return dict(own=[dict(observed_at=STAMP-3600,price=100,confirmed=True),dict(observed_at=STAMP,price=110,confirmed=True)],
  targets=[dict(id=1,item_id='MLB2',label='Concorrente')],
  competitors=[dict(target_id=1,observed_at=STAMP-1800,price=100,error=None),dict(target_id=1,observed_at=STAMP+1800,price=100,error=None)])
class CompetitivenessTests(unittest.TestCase):
 def test_matches_only_prior_reads_and_exact_distance_change(self):
  d=data();before=deepcopy(d);row=build(d,END)[0]
  self.assertEqual(row['valid'],2);self.assertEqual(row['latest']['own_at'],STAMP)
  self.assertEqual(row['latest']['gap'],10);self.assertEqual(row['latest']['gap_pct'],10)
  self.assertEqual(row['latest']['delta_pp'],10);self.assertEqual(d,before)
 def test_never_uses_future_price_or_stale_read(self):
  for stamp in [STAMP+4000,STAMP-7*3600]:
   d=data();d['own']=[dict(observed_at=stamp,price=110,confirmed=True)]
   self.assertIsNone(build(d,END)[0]['latest'])
 def test_bad_own_latest_read_does_not_fall_back(self):
  for updates in [dict(confirmed=False),dict(confirmed='true'),dict(price=None),dict(price=0),dict(price='NaN')]:
   d=data();d['own'][-1].update(updates);self.assertIsNone(build(d,END)[0]['latest'])
 def test_failed_or_duplicate_competitor_reads_block_latest(self):
  for mode in ['error','duplicate','missing','zero']:
   d=data()
   if mode=='error':d['competitors'][-1]['error']='failed'
   elif mode=='duplicate':d['competitors'].append(dict(d['competitors'][-1]))
   elif mode=='missing':d['competitors'][-1]['price']=None
   else:d['competitors'][-1]['price']=0
   self.assertIsNone(build(d,END)[0]['latest'])
 def test_failed_middle_read_breaks_delta_but_not_valid_latest_pair(self):
  d=data();d['competitors'].insert(1,dict(target_id=1,observed_at=STAMP,error='failed',price=None))
  self.assertIsNone(build(d,END)[0]['latest']['delta_pp'])
 def test_window_excludes_today_and_unlinked_targets(self):
  d=data();d['competitors']=[dict(target_id=1,observed_at=STAMP+86400,price=1),dict(target_id=999,observed_at=STAMP,price=1)]
  r=build(d,END)[0];self.assertEqual(r['observed'],0);self.assertIsNone(r['latest'])
 def test_duplicate_own_read_is_ambiguous(self):
  d=data();d['own'].append(dict(d['own'][-1]));self.assertIsNone(build(d,END)[0]['latest'])
 def test_no_equivalence_causality_or_portfolio_claim_and_escape(self):
  d=data();d['targets'][0]['label']='<script>';d['history_limited']=True
  html=render(d,END);self.assertNotIn('<script>',html);self.assertIn('&lt;script&gt;',html)
  self.assertIn('não comprova equivalência',html);self.assertIn('não atribui causalidade',html)
  self.assertIn('Histórico limitado',html)

class CompetitivenessPeriodTests(unittest.TestCase):
 def test_periods_count_valid_above_equal_below_and_failures(self):
  d=data();d['own']=[];d['competitors']=[]
  for offset,own_price,competitor_price in [(-7*86400,90,100),(-7*86400+3600,100,100),(0,110,100),(3600,100,100),(7200,90,100)]:
   stamp=STAMP+offset
   d['own'].append(dict(observed_at=stamp,price=own_price,confirmed=True))
   d['competitors'].append(dict(target_id=1,observed_at=stamp,price=competitor_price))
  d['competitors'].append(dict(target_id=1,observed_at=STAMP+10800,error='failed'))
  r=build(d,END)[0]
  self.assertEqual(r['periods']['previous'],dict(observed=2,valid=2,above=0,equal=1,below=1))
  self.assertEqual(r['periods']['current'],dict(observed=4,valid=3,above=1,equal=1,below=1))
  self.assertIsNone(r['latest'])
  self.assertEqual(r['valid'],3)
  html=render(d,END)
  self.assertIn('3/4 pares válidos / leituras',html)
  self.assertIn('Próprio acima: 1 · igual: 1 · abaixo: 1',html)
  self.assertIn('Atual: 17/10 a 23/10/2026',html)
  self.assertIn('Anterior: 10/10 a 16/10/2026',html)

 def test_duplicate_observations_count_as_reads_but_never_valid_pairs(self):
  d=data();d['competitors'].append(dict(d['competitors'][-1]))
  r=build(d,END)[0]['periods']['current']
  self.assertEqual(r,dict(observed=3,valid=1,above=0,equal=1,below=0))

 def test_missing_previous_period_is_not_zero_price_or_stability(self):
  d=data();r=build(d,END)[0]
  self.assertEqual(r['periods']['previous'],dict(observed=0,valid=0,above=0,equal=0,below=0))
  html=render(d,END)
  self.assertIn('Sem leituras no período',html)
  self.assertIn('Sem leituras não significa preço estável',html)
  self.assertIn('sem ponderação por tempo ou vendas',html)

 def test_invalid_own_read_between_valid_pairs_breaks_delta(self):
  for invalid in [dict(confirmed=False,price=None),dict(confirmed=True,price=0),dict(confirmed=True,price='NaN')]:
   d=data();d['own'].append(dict(observed_at=STAMP-900,**invalid))
   row=build(d,END)[0]
   self.assertEqual(row['valid'],2)
   self.assertEqual(row['latest']['gap'],10)
   self.assertIsNone(row['latest']['delta_pp'])

 def test_duplicate_own_read_between_valid_pairs_breaks_delta(self):
  d=data();d['own'] += [dict(observed_at=STAMP-900,price=100,confirmed=True)]*2
  row=build(d,END)[0]
  self.assertEqual(row['valid'],2)
  self.assertIsNone(row['latest']['delta_pp'])

 def test_window_boundary_and_target_samples_stay_separate(self):
  d=data();boundary=int(datetime(2026,10,17,tzinfo=SAO_PAULO).timestamp())
  d['own']=[dict(observed_at=boundary-1,price=100,confirmed=True),dict(observed_at=boundary,price=110,confirmed=True)]
  d['targets'].append(dict(id=2,item_id='MLB3',label='Outro'))
  d['competitors']=[dict(target_id=1,observed_at=boundary-1,price=100),dict(target_id=1,observed_at=boundary,price=100),dict(target_id=2,observed_at=boundary,price=120)]
  first,second=build(d,END)
  self.assertEqual(first['periods']['previous']['equal'],1)
  self.assertEqual(first['periods']['current']['above'],1)
  self.assertEqual(second['periods']['current']['below'],1)
  self.assertEqual(second['periods']['previous']['observed'],0)
