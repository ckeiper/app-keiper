import unittest
from copy import deepcopy
from datetime import date,datetime,timedelta
from decimal import Decimal
from offer_history import BR,price_events,reading_coverage,render
from test_offer_history import observed

END=date(2026,10,23)
BASE=int(datetime(2026,10,23,12,tzinfo=BR).timestamp())

class OfferReadingCoverageTests(unittest.TestCase):
 def test_duplicate_timestamp_breaks_events_regardless_of_order(self):
  for duplicate in [80,90]:
   rows=[observed(BASE,70),observed(BASE+100,80),observed(BASE+100,duplicate),observed(BASE+200,100),observed(BASE+300,110)]
   events=price_events(rows)
   self.assertEqual(len(events),1)
   self.assertEqual(events[0]['previous_at'],BASE+200)
   self.assertEqual(events[0]['after'],110)
   self.assertEqual(price_events(list(reversed(rows))),events)

 def test_only_explicit_true_and_positive_cent_price_confirm(self):
  for update in [dict(confirmed='true'),dict(confirmed=1),dict(confirmed=None),dict(price=True),dict(price='0.001'),dict(price='NaN'),dict(price=0)]:
   middle=observed(BASE+100,80);middle.update(update)
   self.assertEqual(price_events([observed(BASE,70),middle,observed(BASE+200,100)]),[])

 def test_exact_six_hour_boundary_and_promotion_end(self):
  rows=[observed(BASE,80,True),observed(BASE+21600,100,False)]
  self.assertTrue(price_events(rows)[0]['promotion_ended'])
  self.assertEqual(price_events(rows)[0]['delta'],25)
  rows[-1]['observed_at']+=1;self.assertEqual(price_events(rows),[])

 def test_both_periods_counts_and_duplicates_are_not_confirmation(self):
  rows=[observed(BASE-7*86400,100,True),observed(BASE-7*86400+100,110,None),
        observed(BASE,80,True),observed(BASE+100,100,False),
        observed(BASE+200,100),observed(BASE+200,100),observed(BASE+300,None,confirmed=False)]
  before=deepcopy(rows);summary=reading_coverage(rows,END)
  self.assertEqual(summary['previous'],dict(readings=2,confirmed=2,changes=1,promotion=1))
  self.assertEqual(summary['current'],dict(readings=5,confirmed=2,changes=1,promotion=1))
  self.assertEqual(rows,before)

 def test_boundaries_exclude_today_and_outside_window(self):
  boundary=int(datetime(2026,10,17,tzinfo=BR).timestamp())
  rows=[observed(boundary-1,80),observed(boundary,100),observed(boundary+7*86400,200),observed(boundary-7*86400-1,50)]
  summary=reading_coverage(rows,END)
  self.assertEqual(summary['previous']['readings'],1)
  self.assertEqual(summary['current']['readings'],1)
  self.assertEqual(summary['current']['changes'],1)

 def test_empty_periods_and_sample_limits_are_visible(self):
  data=dict(own=[],targets=[],competitors=[],targets_limited=False,history_limited=False)
  html=render(data,42,'MLB1',END)
  self.assertEqual(html.count('Sem leituras no período'),2)
  self.assertIn('não é possível afirmar que o preço permaneceu estável',html)
  self.assertIn('Não indicam dias em promoção',html)
  data['own']=[observed(BASE,100,True)]
  html=render(data,42,'MLB1',END)
  self.assertIn('1 de 1</b> leituras com preço confirmado',html)
  self.assertIn('0 mudanças entre leituras comparáveis · 1 leituras com promoção confirmada',html)
  self.assertIn('17/10/2026 a 23/10/2026',html)

 def test_competitor_change_label_uses_selected_period_length(self):
  data=dict(own=[],targets=[],competitors=[dict(target_id=1,observed_at=BASE,price=100,previous_price=90,price_changed=True)],targets_limited=False,history_limited=False)
  html=render(data,42,'MLB1',END,days=30)
  self.assertIn('Mudanças observadas nos 60 dias consultados',html)
