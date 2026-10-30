import unittest
from datetime import timedelta
from listing_timeline import build,render
from test_listing_timeline import END,stamp
from test_investigation_triage import evidence,offer
from test_investigation_evidence import END as TRIAGE_END,stock
from offer_history import continuous_price_since

class DiagnosticContinuityTests(unittest.TestCase):
 def timeline(self,offers,days=14):
  return build('MLB1',[],[],[],[],[],offers,END,days=days)

 def test_daily_price_rejects_ambiguous_latest_and_does_not_fall_back(self):
  first=dict(observed_at=stamp(END,9),confirmed=True,price=80)
  last=dict(observed_at=stamp(END,12),confirmed=True,price=100)
  for rows in [[first,last,dict(last)],[first,dict(last,confirmed='true')],[first,dict(last,confirmed=1)],[first,dict(last,price='0.001')]]:
   self.assertIsNone(self.timeline(rows)['prices'][-1])
   self.assertEqual(self.timeline(rows)['events'],[])
  self.assertEqual(self.timeline([first,last])['prices'][-1],100)

 def test_malformed_or_outside_window_timestamps_do_not_break_graph(self):
  rows=[dict(observed_at=value,confirmed=True,price=100) for value in [True,None,'bad',0,-1,10**1000,stamp(END+timedelta(days=1))]]
  self.assertEqual(self.timeline(rows)['prices'],[None]*14)
  self.assertEqual(self.timeline(rows)['events'],[])

 def test_first_visible_day_keeps_valid_event_from_prior_day(self):
  first=END-timedelta(days=6)
  rows=[dict(observed_at=stamp(first-timedelta(days=1),23),confirmed=True,price=80),dict(observed_at=stamp(first,1),confirmed=True,price=100)]
  result=self.timeline(rows,days=7)
  self.assertEqual(result['prices'][0],100)
  self.assertEqual(result['events'][0]['day'],first.isoformat())

 def test_intermediate_failure_or_long_gap_blocks_old_increase_recommendation(self):
  for rows in [[offer(hour=9,price=80),offer(hour=10,price=100),offer(hour=11,price=None,confirmed=False),offer(hour=12,price=100)],
               [offer(hour=1,price=80),offer(hour=2,price=100),offer(hour=12,price=100)]]:
   self.assertNotIn('preco',[r['code'] for r in evidence(rows)['actions']])

 def test_duplicate_latest_blocks_triage_and_daily_coverage(self):
  rows=[offer(hour=9,price=80),offer(price=100),offer(price=100)]
  result=evidence(rows)
  self.assertNotIn('preco',[r['code'] for r in result['actions']])
  self.assertTrue(any('Preço próprio: 0/14' in gap for gap in result['triage']['gaps']))

 def test_full_unknown_latest_never_becomes_recovery_from_older_positive_read(self):
  result=evidence(full=[stock(TRIAGE_END-timedelta(days=2),'empty'),stock(TRIAGE_END-timedelta(days=1),'available')])
  action=next(r for r in result['actions'] if r['code']=='full')
  self.assertNotIn('já mostra Full com estoque',action['action'])
  self.assertEqual(result['actions'][0]['code'],'full')
  current=evidence(full=[stock(TRIAGE_END-timedelta(days=2),'empty'),stock(TRIAGE_END,'available')])
  self.assertIn('já mostra Full com estoque',next(r for r in current['actions'] if r['code']=='full')['action'])

 def test_new_valid_sequence_can_generate_new_recommendation_after_failure(self):
  rows=[offer(hour=8,price=None,confirmed=False),offer(hour=9,price=80),offer(hour=10,price=100),offer(hour=12,price=100)]
  self.assertIn('preco',[r['code'] for r in evidence(rows)['actions']])
  self.assertTrue(continuous_price_since(rows,rows[2]['observed_at']))
  self.assertFalse(continuous_price_since(rows,rows[0]['observed_at']))
