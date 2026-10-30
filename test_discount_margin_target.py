import unittest
from decimal import Decimal
from profitability_scenarios import simulate,render
from test_profitability_scenarios import form
class TargetTests(unittest.TestCase):
 def test_optional_target_not_invented(self):
  r=simulate(form());self.assertIsNone(r['target_margin']);self.assertNotIn('target_met',r['rows'][0])
 def test_explicit_target_and_gap(self):
  f=form();f['target_margin']='40';r=simulate(f)['rows'][0]
  self.assertFalse(r['target_met']);self.assertEqual(r['target_contribution'],108);self.assertEqual(r['target_gap'],Decimal('18.50'))
 def test_zero_target_is_explicit_and_negative_still_fails(self):
  f=form();f.update(target_margin='0',product='200');r=simulate(f)['rows'][0]
  self.assertFalse(r['target_met']);self.assertEqual(r['target_gap'],-r['contribution'])
 def test_precision_rejects_false_rounded_pass_and_bad_targets(self):
  f=form();f.update(price='0.03',product='0.01',fee_pct='0',fixed_fee='0',tax_pct='0',shipping='0',ads='0',qty_0='1',discount_0='0',target_margin='66.67')
  r=simulate(f)['rows'][0];self.assertEqual(r['target_contribution'],Decimal('.03'));self.assertFalse(r['target_met'])
  for v in ['NaN','-1','100.01','1.001','1e2']:
   f['target_margin']=v
   with self.assertRaises(ValueError):simulate(f)
