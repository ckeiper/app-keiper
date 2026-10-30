import unittest
from decimal import Decimal as D
from unittest.mock import Mock
from test_profitability_action import fixture,TODAY,DAY,ITEM
from profitability_action import load,render,unit_contribution

class ActionFinanceVolumeTests(unittest.TestCase):
 def context(self):
  periods,orders,items,records=fixture()
  return periods,load(None,Mock(return_value=records),1,ITEM,periods,orders,items,TODAY)
 def test_historical_average_uses_verified_units_and_keeps_negative_sign(self):
  periods,r=self.context()
  self.assertEqual(unit_contribution(r['before']),D(640)/r['before']['units'])
  self.assertEqual(unit_contribution(r['after']),D(1340)/r['after']['units'])
  r['after']['contribution']=D(-400)
  self.assertLess(unit_contribution(r['after']),0)
  html=render(r,1,ITEM,periods,TODAY)
  self.assertIn('Valor bruto dos itens',html);self.assertIn('Unidades verificadas',html)
  self.assertIn('Contribuição média por unidade',html)
  self.assertIn('não equivale ao lucro por produto',html)
 def test_zero_missing_fractional_or_invalid_units_never_divide(self):
  for units in [D(0),D(-1),D('1.5'),D('NaN'),D('Infinity'),None,True]:
   self.assertIsNone(unit_contribution(dict(available=True,units=units,contribution=D(10))))
  self.assertIsNone(unit_contribution(dict(available=False,units=D(1),contribution=D(10))))
 def test_source_links_target_exact_versions_without_changing_dates(self):
  periods,r=self.context();html=render(r,1,ITEM,periods,TODAY)
  self.assertIn('inicio=2026-10-05&amp;fim=2026-10-11&amp;registro=1#pf-registro',html)
  self.assertIn('inicio=2026-10-13&amp;fim=2026-10-19&amp;registro=2#pf-registro',html)
  self.assertEqual(r['before']['contribution'],640)
 def test_waiting_or_unknown_costs_do_not_create_unit_values_or_record_ids(self):
  periods,orders,items,records=fixture()
  r=load(None,Mock(),1,ITEM,periods,orders,items,DAY)
  html=render(r,1,ITEM,periods,DAY)
  self.assertNotIn('<table',html);self.assertNotIn('registro=',html)
  self.assertIn('Aguardando os dois períodos',html)
 def test_record_identifier_is_escaped_and_invalid_link_not_generated(self):
  periods,r=self.context();r['records'][0]['id']='<script>'
  html=render(r,1,ITEM,periods,TODAY)
  self.assertIn('&lt;script&gt;',html);self.assertNotIn('<script>',html)
  self.assertNotIn('registro=%3Cscript',html)
