import unittest
from datetime import date
from decimal import Decimal
from financial_priority_queue import build,render

def signal(value):return dict(contribution_current=value,contribution_verified=True,margin_documented=True)
class FinancialQueueTests(unittest.TestCase):
 def test_includes_negative_without_gross_loss_and_does_not_net_positives(self):
  result=build({'MLB1':signal(-10),'MLB2':signal(100),'MLB3':signal(-20)})
  self.assertEqual(result['documented'],3);self.assertEqual(result['total'],2)
  self.assertEqual(result['negative_sum'],-30)
  self.assertEqual([r['item_id'] for r in result['rows']],['MLB3','MLB1'])
 def test_invalid_stale_flags_and_missing_never_enter(self):
  cases=[dict(signal(-1),contribution_verified=False),dict(signal(-1),margin_documented='true'),signal(None),signal('NaN'),signal(True)]
  for case in cases:self.assertEqual(build({'MLB1':case})['documented'],0)
  self.assertEqual(build({'<script>':signal(-1)})['total'],0)
 def test_limit_applies_to_display_not_sum_and_stable_ties(self):
  r=build({'MLB'+str(i):signal(Decimal('-1.01')) for i in range(10)})
  self.assertEqual(len(r['rows']),6);self.assertEqual(r['total'],10)
  self.assertEqual(r['negative_sum'],Decimal('-10.10'))
  self.assertEqual(r['rows'][0]['item_id'],'MLB0')
 def test_html_escaping_period_link_and_unknown_state(self):
  args=([dict(item_id='MLB1',titulo='<script>')],42,date(2026,10,17),date(2026,10,23))
  html=render({'MLB1':signal(-1)},*args)
  self.assertNotIn('<script>',html);self.assertIn('&lt;script&gt;',html)
  self.assertIn('inicio=2026-10-17&amp;fim=2026-10-23',html)
  self.assertIn('não é resultado da loja',html)
  self.assertNotIn('fq-card',render({},*args))
 def test_zero_and_positive_never_claim_profit(self):
  html=render({'MLB1':signal(0)},[],1,date(2026,10,17),date(2026,10,23))
  self.assertIn('não comprova lucro líquido',html)
