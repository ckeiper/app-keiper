import unittest
from decimal import Decimal
import test_profitability as fixtures
from profitability_view import render_inspection

class ProfitabilityInspectionTests(unittest.TestCase):
 def setUp(self):
  self.fx=fixtures.ProfitabilityRouteTests();self.fx.setUp();self.addCleanup(self.fx.doCleanups)
  self.fx.record=dict(fixtures.record(),id=2)
  self.old=dict(fixtures.record(),id=1,costs=dict(fixtures.record()['costs'],products=Decimal(200)))
  original=self.fx.read
  def read(conn,sql,params):
   if 'AND id=%s' in sql:return [self.old] if params[-1]==1 else []
   return original(conn,sql,params)
  self.fx.query.side_effect=read
 def test_exact_record_is_read_only_and_does_not_replace_latest_calculation(self):
  response=self.fx.client.get(self.fx.path+'?registro=1')
  self.assertEqual(response.status_code,200)
  self.assertIn('Consulta do registro #1',response.text)
  self.assertIn('Composição e fontes · registro #2',response.text)
  self.assertIn('R$ 240,00',response.text)
  self.assertIn('Selecionar este registro não altera os indicadores',response.text)
  self.fx.execute.assert_called_once_with(None,'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
  call=self.fx.query.call_args
  self.assertEqual(call.args[2],(42,'MLB100',fixtures.START,fixtures.END,1))
  for scope in ['conexao_id=%s','item_id=%s','inicio=%s','fim=%s','id=%s']:self.assertIn(scope,call.args[1])
  self.assertEqual(response.headers['Cache-Control'],'no-store')
 def test_missing_or_other_tenant_cannot_expose_inspection(self):
  self.assertEqual(self.fx.client.get(self.fx.path+'?registro=999').status_code,404)
  self.assertEqual(self.fx.client.get(self.fx.path.replace('/42/','/43/')+'?registro=1').status_code,403)
  with self.fx.client.session_transaction() as session:session['tipo']='cliente'
  self.assertEqual(self.fx.client.get(self.fx.path+'?registro=1').status_code,403)
 def test_invalid_identifiers_rejected_before_any_database_read(self):
  for value in ['0','-1','abc','1.5','9223372036854775808','1%20OR%201=1','']:
   self.fx.query.reset_mock()
   self.assertEqual(self.fx.client.get(self.fx.path+'?registro='+value).status_code,400)
   self.fx.query.assert_not_called()
 def test_normal_page_does_not_add_inspection_read(self):
  response=self.fx.client.get(self.fx.path)
  self.assertEqual(response.status_code,200)
  self.assertNotIn('class="pf-card pf-inspection"',response.text)
  self.assertFalse(any('AND id=%s' in call.args[1] for call in self.fx.query.call_args_list))
  self.assertIn('registro=2#pf-registro',response.text)
 def test_original_sources_are_escaped_and_no_restore_form_exists(self):
  self.old['sources']=dict(self.old['sources'],products='<script>bad</script>')
  html=render_inspection(self.old)
  self.assertIn('&lt;script&gt;',html);self.assertNotIn('<script>',html)
  self.assertNotIn('<form',html)
  self.assertIn('Não é possível restaurar',html)
