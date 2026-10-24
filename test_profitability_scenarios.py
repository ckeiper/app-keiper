import unittest,contextlib
from decimal import Decimal
from copy import deepcopy
from functools import wraps
from unittest.mock import Mock,patch
from flask import Flask,session,redirect
from web_security import install_security
from profitability_scenarios import simulate,register,render,FIELDS


def form():
    return dict(price='100',product='40',fee_pct='10',fixed_fee='5',tax_pct='5',shipping='10',ads='5',adjustments='0',qty_0='3',discount_0='10',assumptions='yes',_csrf='test-token')

class DiscountScenarioTests(unittest.TestCase):
 def test_exact_order_and_same_quantity_baseline(self):
  f=form();before=deepcopy(f);r=simulate(f)['rows'][0]
  self.assertEqual(r['price'],90);self.assertEqual(r['gross'],270)
  self.assertEqual(r['costs'],Decimal('180.50'));self.assertEqual(r['contribution'],Decimal('89.50'))
  self.assertEqual(r['baseline'],115);self.assertEqual(r['delta'],Decimal('-25.50'))
  self.assertEqual(f,before)
 def test_price_and_percentage_round_at_documented_steps(self):
  f=form();f['price']='19,99';r=simulate(f)['rows'][0]
  self.assertEqual(r['price'],Decimal('17.99'));self.assertEqual(r['gross'],Decimal('53.97'))
  self.assertEqual(r['fees'],Decimal('10.40'));self.assertEqual(r['taxes'],Decimal('2.70'))
 def test_zero_discount_equals_same_quantity_baseline_and_negative_is_allowed(self):
  f=form();f.update(discount_0='0',product='200');r=simulate(f)['rows'][0]
  self.assertEqual(r['delta'],0);self.assertLess(r['contribution'],0)
 def test_no_missing_cost_or_invalid_number_becomes_zero(self):
  for key in FIELDS:
   for value in ['',None,'NaN','-1','1.001','1e2','1.000,00','9999999',True]:
    f=form();f[key]=value
    with self.assertRaises(ValueError,msg=(key,value)):simulate(f)
 def test_progressive_order_uniqueness_and_partial_rows(self):
  for updates in [dict(qty_1='2',discount_1='20'),dict(qty_1='3',discount_1='20'),dict(qty_1='5',discount_1='5'),dict(qty_1='5'),dict(discount_1='15'),dict(qty_0='1.5'),dict(qty_0='0'),dict(qty_0='10001')]:
   f=form();f.update(updates)
   with self.assertRaises(ValueError):simulate(f)
 def test_up_to_five_tiers_have_independent_order_costs(self):
  f=form()
  for i in range(5):f.update({'qty_'+str(i):str(i+1),'discount_'+str(i):str(i*5)})
  r=simulate(f)['rows'];self.assertEqual(len(r),5)
  self.assertEqual(r[0]['contribution'],25)
  for row in r:self.assertEqual(row['product'],40*row['quantity'])
 def test_confirmation_and_positive_price_required(self):
  for updates in [dict(assumptions=''),dict(price='0'),dict(discount_0='100'),dict(price='0.01',discount_0='99.99'),dict(fee_pct='100.01'),dict(qty_0='',discount_0='')]:
   f=form();f.update(updates)
   with self.assertRaises(ValueError):simulate(f)
 def test_renderer_escapes_and_does_not_create_historical_evidence(self):
  f=form();f['price']='<script>'
  html=render(1,'MLB100','<script>','token',f,None,'bad <script>')
  self.assertNotIn('<script>',html);self.assertIn('&lt;script&gt;',html)
  self.assertNotIn('id="discount-results"',html)
  self.assertIn('não lê custos históricos',html)

class DiscountScenarioRouteTests(unittest.TestCase):
 def setUp(self):
  self.app=Flask(__name__);self.app.secret_key='isolated';self.app.testing=True
  install_security(self.app)
  self.query=Mock(return_value=[dict(cliente='Loja',titulo='Teste')])
  def login(fn):
   @wraps(fn)
   def guard(*args,**kw):return fn(*args,**kw) if session.get('usuario_id') else redirect('/login')
   return guard
  register(self.app,login,lambda cid:cid==1,lambda:contextlib.nullcontext(None),self.query,lambda *args:args[-1])
  self.client=self.app.test_client();self.path='/anuncios/1/MLB100/simulacao-descontos'
  with self.client.session_transaction() as s:s.update(usuario_id=1,tipo='admin',_csrf='test-token')
 def test_get_blank_and_post_calculates_without_network_or_writes(self):
  with patch('requests.get',side_effect=AssertionError('No remote reads')),patch('requests.post',side_effect=AssertionError('No writes')):
   page=self.client.get(self.path);self.assertEqual(page.status_code,200)
   self.assertNotIn('id="discount-results"',page.text)
   response=self.client.post(self.path,data=form());self.assertEqual(response.status_code,200)
   self.assertIn('R$ 89,50',response.text)
  self.assertEqual(self.query.call_args.args[2],(1,'MLB100'))
  self.assertTrue(all(call.args[1].lstrip().startswith('SELECT') for call in self.query.call_args_list))
 def test_roles_store_scope_unknown_listing_and_csrf(self):
  self.assertEqual(self.app.test_client().get(self.path).status_code,302)
  with self.client.session_transaction() as s:s['tipo']='cliente'
  self.assertEqual(self.client.get(self.path).status_code,403)
  with self.client.session_transaction() as s:s['tipo']='admin'
  self.assertEqual(self.client.get(self.path.replace('/1/','/2/')).status_code,403)
  f=form();f.pop('_csrf');self.assertEqual(self.client.post(self.path,data=f).status_code,400)
  self.query.assert_not_called()
  self.query.return_value=[];self.assertEqual(self.client.get(self.path).status_code,404)
 def test_bad_inputs_return_400_without_financial_results(self):
  f=form();f['ads']=''
  response=self.client.post(self.path,data=f)
  self.assertEqual(response.status_code,400);self.assertNotIn('id="discount-results"',response.text)
