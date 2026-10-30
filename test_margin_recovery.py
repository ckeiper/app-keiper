import unittest
from decimal import Decimal
from test_profitability import summary,record
from margin_recovery import review_plan,render_recovery
from listing_profitability import COMPONENTS

class MarginReviewTests(unittest.TestCase):
 def test_missing_stale_or_unverified_never_show_plan(self):
  for s,r in [(summary(),None),(summary(),dict(record(),sales_fingerprint='stale')),(dict(summary(),orders=None),record())]:
   plan=review_plan(s,r)
   self.assertFalse(plan['available']);self.assertIsNone(plan['gap']);self.assertEqual(plan['rows'],[])
   html=render_recovery(s,r)
   self.assertNotIn('Déficit de contribuição documentada',html)
 def test_negative_gap_exact_and_costs_ranked_without_mutation(self):
  r=record();r['costs']={k:Decimal('100.01') for k in COMPONENTS}
  s=summary();plan=review_plan(s,r)
  self.assertTrue(plan['available'])
  self.assertEqual(plan['gap'],Decimal('600.06')-s['gross_items'])
  self.assertEqual(len(plan['rows']),3)
  self.assertEqual([v['key'] for v in plan['rows']],sorted(COMPONENTS)[:3])
  self.assertEqual(r['costs']['products'],Decimal('100.01'))
 def test_positive_and_zero_costs_do_not_imply_profit(self):
  r=record();r['costs']={k:Decimal(0) for k in COMPONENTS}
  self.assertEqual(review_plan(summary(),r)['gap'],0)
  html=render_recovery(summary(),r)
  self.assertIn('Todos os componentes',html);self.assertIn('não comprova lucro líquido',html)
 def test_zero_revenue_no_percentage_and_safe_identifier(self):
  s=summary();s['gross_items']=Decimal(0)
  r=record();r.update(gross_items=Decimal(0),id='<script>')
  plan=review_plan(s,r)
  self.assertTrue(all(row['share'] is None for row in plan['rows']))
  html=render_recovery(s,r)
  self.assertIn('&lt;script&gt;',html);self.assertNotIn('<script>',html)
  self.assertIn('Participação indisponível',html)
 def test_every_component_has_specific_action(self):
  for k in COMPONENTS:
   r=record();r['costs']={key:Decimal(10 if key==k else 0) for key in COMPONENTS}
   plan=review_plan(summary(),r)
   self.assertEqual(plan['rows'][0]['key'],k)
   self.assertTrue(plan['rows'][0]['action'])
