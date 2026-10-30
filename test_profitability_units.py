import unittest
from decimal import Decimal
from copy import deepcopy
from profitability_comparison import compare
from profitability_units import unit_comparison,render_unit_comparison
from test_profitability_comparison import pair_records

class UnitFinanceTests(unittest.TestCase):
 def comparison(self):
  pair,current,previous=pair_records()
  return compare(pair['current'],pair['previous'],current,previous)
 def test_exact_division_for_every_component_and_no_mutation(self):
  c=self.comparison();before=deepcopy(c);result=unit_comparison(c)
  self.assertTrue(result['available']);self.assertEqual(len(result['rows']),8)
  for row in result['rows']:
   key=row['key'];a=c['previous'];b=c['current']
   av=a['costs'][key] if key in a['costs'] else a[key]
   bv=b['costs'][key] if key in b['costs'] else b[key]
   self.assertEqual(row['previous'],av/a['units'])
   self.assertEqual(row['current'],bv/b['units'])
   self.assertEqual(row['delta'],bv/b['units']-av/a['units'])
  self.assertEqual(c,before)
 def test_proportional_volume_preserves_all_unit_values(self):
  c=self.comparison();old=c['previous'];new=deepcopy(old)
  for key in ['units','revenue','contribution']:new[key]*=3
  new['costs']={k:v*3 for k,v in old['costs'].items()};c['current']=new
  self.assertTrue(all(r['delta']==0 for r in unit_comparison(c)['rows']))
 def test_missing_or_changed_evidence_blocks(self):
  pair,current,previous=pair_records()
  for rec in [None,dict(previous,sales_fingerprint='stale')]:
   c=compare(pair['current'],pair['previous'],current,rec)
   self.assertFalse(unit_comparison(c)['available'])
   self.assertNotIn('<table',render_unit_comparison(c))
 def test_zero_negative_fractional_nonfinite_and_missing_units_block(self):
  for v in [Decimal(0),Decimal(-1),Decimal('1.5'),Decimal('NaN'),None,True]:
   for side in ['current','previous']:
    c=self.comparison();c[side]['units']=v
    self.assertFalse(unit_comparison(c)['available'])
 def test_negative_contribution_keeps_sign_and_disclaimer(self):
  c=self.comparison();c['current']['contribution']=Decimal('-100')
  self.assertLess(unit_comparison(c)['rows'][-1]['current'],0)
  html=render_unit_comparison(c)
  self.assertIn('mix de variações',html);self.assertIn('Despesas fixas não incluídas',html)
 def test_zero_revenue_still_has_unit_averages(self):
  c=self.comparison();c['current']['revenue']=Decimal(0)
  self.assertEqual(unit_comparison(c)['rows'][0]['current'],0)
