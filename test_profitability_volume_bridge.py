import unittest
from copy import deepcopy
from decimal import Decimal as D
from profitability_units import contribution_bridge,render_bridge
from test_profitability_comparison import pair_records
from profitability_comparison import compare

class VolumeBridgeTests(unittest.TestCase):
 def model(self,old_units,new_units,old,new):
  pair,current,previous=pair_records()
  c=compare(pair['current'],pair['previous'],current,previous)
  for side,units,value in [('previous',old_units,old),('current',new_units,new)]:
   c[side]['units']=D(units);c[side]['contribution']=D(value)
  return c
 def test_volume_only_change_preserves_average(self):
  c=self.model(10,20,100,200);before=deepcopy(c);r=contribution_bridge(c)
  self.assertEqual((r['volume'],r['average'],r['delta']),(100,0,100));self.assertEqual(c,before)
 def test_average_only_change_and_compensation(self):
  r=contribution_bridge(self.model(10,10,100,70))
  self.assertEqual((r['volume'],r['average'],r['delta']),(0,-30,-30))
  r=contribution_bridge(self.model(10,20,100,80))
  self.assertEqual((r['volume'],r['average'],r['delta']),(100,-120,-20))
 def test_more_volume_with_negative_average_remains_negative(self):
  r=contribution_bridge(self.model(10,20,-100,-150))
  self.assertEqual((r['volume'],r['average'],r['delta']),(-100,50,-50))
 def test_rounding_reconciles_exactly_and_unknown_never_becomes_zero(self):
  r=contribution_bridge(self.model(3,7,1,2))
  self.assertEqual(r['volume'],D('1.33'));self.assertEqual(r['average'],D('-0.33'))
  self.assertEqual(r['volume']+r['average'],r['delta'])
  for units in [0,-1,'1.5','NaN']:
   self.assertFalse(contribution_bridge(self.model(units,7,1,2))['available'])
  c=self.model(3,7,1,2);c['available']=False
  self.assertEqual(render_bridge(c),'')
 def test_zero_contribution_is_valid_and_limits_are_visible(self):
  c=self.model(3,7,0,0);r=contribution_bridge(c)
  self.assertEqual(r['volume'],0);self.assertEqual(r['average'],0)
  html=render_bridge(c)
  self.assertIn('não comprovam causas',html);self.assertIn('Contribuição não é lucro líquido',html)
