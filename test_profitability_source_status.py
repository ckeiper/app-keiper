import unittest
from copy import deepcopy
from profitability_store import result_for
from profitability_view import render,render_source_status
from margin_recovery import render_recovery
from test_profitability import summary,record,START,END

class ProfitabilitySourceStatusTests(unittest.TestCase):
 def page(self,s,r):
  return render(42,'MLB100','Produto',START,END,s,result_for(s,r),r,[r] if r else [],'csrf','x'*32)
 def test_valid_sources_are_declared_not_automatically_audited(self):
  s=summary();r=record();before=deepcopy(r)
  html=self.page(s,r)
  self.assertIn('Vinculados à base verificada',html)
  self.assertIn('Referências declaradas, sem auditoria automática',html)
  self.assertNotIn('Este registro não valida',html)
  self.assertIn('id="pf-fontes"',html)
  self.assertEqual(r,before)
 def test_missing_costs_offer_only_existing_form(self):
  html=self.page(summary(),None)
  self.assertIn('Ainda não registrados',html)
  self.assertIn('href="#pf-fontes"',html)
  self.assertIn('id="pf-fontes"',html)
 def test_changed_sales_preserve_record_but_warn_against_current_use(self):
  r=dict(record(),sales_fingerprint='changed')
  html=self.page(summary(),r)
  self.assertIn('Registro requer conferência',html)
  self.assertIn('Este registro não valida o cálculo atual',html)
  self.assertIn('Registro preservado para conferência',html)
  self.assertIn('Base registrada:',html)
  self.assertIn('não substituem a conferência',html)
 def test_unverified_sales_never_link_to_missing_cost_form(self):
  s=dict(summary(),orders=None,units=None,gross_items=None,reason='Pedidos pendentes')
  html=self.page(s,record())
  self.assertIn('Verificação pendente',html)
  self.assertNotIn('href="#pf-fontes"',html)
  self.assertNotIn('id="pf-fontes"',html)
  self.assertIn('Registros anteriores permanecem preservados',html)
 def test_untrusted_reason_escaped_and_history_destination_honest(self):
  s=dict(summary(),orders=None,reason='<script>')
  html=self.page(s,record())
  self.assertNotIn('<script>',html)
  self.assertIn('&lt;script&gt;',html)
  self.assertIn('abre a última versão do período',html)
