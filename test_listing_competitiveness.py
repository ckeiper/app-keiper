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
