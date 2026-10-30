import unittest
from copy import deepcopy
from listing_action_plan import build,render

class ListingActionPlanTests(unittest.TestCase):
 def test_operational_then_documented_finance_then_offer_order(self):
  row=dict(codes=['trafego','preco','full'],additional_findings=[dict(code='negative_contribution',evidence='R$ -10,00')])
  self.assertEqual([s['code'] for s in build(row)['steps']],['full','negative_contribution','preco'])
  self.assertEqual(build(row)['total'],4)
 def test_stockout_and_negative_remove_overlapping_steps(self):
  r=build(dict(codes=['full'],additional_findings=[dict(code='stockout'),dict(code='stock_coverage'),dict(code='margin_decline',evidence='Margem menor'),dict(code='negative_contribution',evidence='Contribuição negativa')]))
  self.assertEqual([s['code'] for s in r['steps']],['stockout','negative_contribution'])
 def test_financial_code_without_evidence_does_not_invent_values(self):
  r=build(dict(codes=['negative_contribution','margin_decline']))
  self.assertEqual(r['steps'][0]['code'],'coverage')
 def test_no_signal_keeps_uncertainty_and_does_not_claim_completed_action(self):
  html=render(dict(codes=[]))
  self.assertIn('sem ação executada ou causa confirmada',html)
  self.assertIn('sem sinal adicional suficiente',html)
 def test_ads_is_shop_context_not_allocated_to_listing(self):
  step=build(dict(codes=['ads_loja']))['steps'][0]
  self.assertIn('refere-se à loja',step['evidence']);self.assertIn('não distribuir gasto',step['follow_up'])
 def test_html_escaping_no_mutation_and_compact_limit(self):
  row=dict(codes=['preco','trafego','eficiencia'],additional_findings=[dict(code='negative_contribution',evidence='<script>')]);before=deepcopy(row)
  html=render(row);self.assertNotIn('<script>',html);self.assertIn('&lt;script&gt;',html)
  self.assertEqual(row,before)
  html=render(row,compact=True);self.assertEqual(html.count('<li>'),1);self.assertNotIn('Como acompanhar:',html)
 def test_unknown_codes_do_not_create_false_actions(self):
  self.assertEqual(build(dict(codes=['made-up']))['steps'][0]['code'],'coverage')
 def test_deduplication_and_priority_are_stable(self):
  a=build(dict(codes=['trafego','full','preco','full']))
  b=build(dict(codes=['preco','full','trafego']))
  self.assertEqual(a,b)
