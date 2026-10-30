import unittest
from copy import deepcopy
from investigation_evidence import build,render
from investigation_cross_signals import assess,render as render_cross
from test_investigation_triage import evidence,offer
from test_investigation_evidence import END,ranking,visits,advertising

class DiagnosticNavigationTests(unittest.TestCase):
 def test_first_action_has_internal_destination_and_explicit_plan(self):
  result=evidence([offer(hour=9,price=80),offer(price=100)])
  before=deepcopy(result);html=render(result,42,END)
  self.assertIn('href="#evidence-action-1"',html)
  for i,action in enumerate(result['actions'],1):
   self.assertIn("id='evidence-action-%s' tabindex='-1'"%i,html)
   self.assertIn(action['action'],html)
  self.assertEqual(html.count("class='evidence-action-details'"),len(result['actions']))
  self.assertNotIn("class='evidence-action-details' open",html)
  self.assertEqual(result,before)

 def test_unverified_sales_do_not_jump_to_unproven_priority(self):
  html=render(evidence(verified=False),42,END)
  self.assertNotIn('class="evidence-jump"',html)
  self.assertIn('validar cobertura e pedidos',html)

 def test_details_keep_untrusted_evidence_escaped(self):
  result=evidence([offer(hour=9,price=80),offer(price=100)])
  result['actions'][0].update(title='<script>',evidence='<img>',action='<iframe>',scope='<style>',follow_up='<svg>')
  html=render(result,42,END)
  for tag in ['script','img','iframe','style','svg']:
   self.assertIn('&lt;'+tag+'&gt;',html)
  self.assertNotIn('<script>',html)

 def test_period_labels_and_coverage_requirements_follow_selected_duration(self):
  result=build(ranking(),'MLB1',visits(),[],advertising(),END,days=14)
  html=render(result,42,END,days=14)
  self.assertIn('14 DIAS VS. 14 DIAS',html)
  self.assertIn('Completar as leituras de visitas dos 28 dias',html)
  self.assertIn('Conferir visitas diárias e lacunas (28 dias)',html)
  self.assertNotIn('LEITURA CRUZADA · 7 DIAS VS. 7 DIAS',html)

 def test_default_comparison_retains_seven_day_contract(self):
  result=evidence()
  html=render_cross(assess(result,result.get('sales_for_cross')))
  self.assertIn('7 DIAS VS. 7 DIAS',html)
