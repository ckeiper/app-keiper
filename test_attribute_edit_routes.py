import contextlib
from copy import deepcopy
from unittest import TestCase
from unittest.mock import Mock,patch
from functools import wraps
from flask import Flask,session,redirect
from web_security import install_security
from attribute_editor import register,valid_plan
from attribute_edit_view import render
from test_attribute_completion import facts,analyze

PID='11111111-1111-4111-8111-111111111111'

def plan(state='ready'):
 return dict(id=PID,state=state,data=analyze(facts()),selected=['MATERIAL'],result={})

class EditorRouteGuards(TestCase):
 def setUp(self):
  self.app=Flask(__name__);self.app.secret_key='test';self.app.testing=True;install_security(self.app)
  self.query=Mock(return_value=[]);self.get=Mock();self.put=Mock();self.resolve=Mock(return_value='private-token')
  def login(fn):
   @wraps(fn)
   def guard(*a,**k):return fn(*a,**k) if session.get('usuario_id') else redirect('/login')
   return guard
  register(self.app,login,lambda cid:cid==1,lambda:contextlib.nullcontext(None),self.query,lambda *a,**kw:a[-1],self.resolve,self.get,self.put)
  self.c=self.app.test_client();self.path='/anuncios/1/MLB123/completar-ficha'
  with self.c.session_transaction() as s:s.update(usuario_id=1,tipo='admin',_csrf='csrf')
 def test_auth_role_scope_and_csrf_stop_before_api_and_database(self):
  self.assertEqual(self.app.test_client().get(self.path).status_code,302)
  self.assertEqual(self.c.post(self.path,data=dict(action='analyze')).status_code,400)
  self.assertEqual(self.c.get(self.path.replace('/1/','/2/')).status_code,403)
  self.assertEqual(self.c.get(self.path.replace('MLB123','bad')).status_code,404)
  with self.c.session_transaction() as s:s['tipo']='cliente'
  self.assertEqual(self.c.post(self.path,data=dict(_csrf='csrf',action='apply')).status_code,403)
  self.query.assert_not_called();self.resolve.assert_not_called();self.get.assert_not_called();self.put.assert_not_called()
 def test_get_is_read_only_and_does_not_resolve_token(self):
  self.query.side_effect=[[dict(user_id=123,titulo='Produto',cliente='Loja',status='ativa')],[]]
  r=self.c.get(self.path);self.assertEqual(r.status_code,200);self.assertIn('Analisar e completar ficha',r.text)
  self.get.assert_not_called();self.put.assert_not_called();self.resolve.assert_not_called()
  for c in self.query.call_args_list:self.assertTrue(c.args[1].lstrip().startswith('SELECT'))
 def test_uuid_validation(self):
  self.assertTrue(valid_plan(PID));self.assertFalse(valid_plan('-'*36));self.assertFalse(valid_plan('not-a-plan'))

class EditorViewTests(TestCase):
 def test_explicit_review_no_default_selection_and_no_secret(self):
  p=plan();text=render(1,'MLB123','Produto','csrf','k'*24,p)
  self.assertIn('Aplicar selecionadas no Mercado Livre',text);self.assertNotIn(' checked',text);self.assertIn('Antes: sem valor',text);self.assertIn('Material: Aço',text);self.assertNotIn('private-token',text)
 def test_blocked_and_uncertain_do_not_offer_send(self):
  p=plan();p['data']['blocked']='Vínculo compartilhado';text=render(1,'MLB123','P','csrf','k'*24,p)
  self.assertNotIn('Aplicar selecionadas',text);self.assertIn(' disabled',text)
  text=render(1,'MLB123','P','csrf','k'*24,plan('uncertain'));self.assertIn('Confirmar envio por nova leitura',text);self.assertNotIn('Aplicar selecionadas',text);self.assertIn('manual_checked',text)
 def test_html_escaping_of_source_and_values(self):
  p=plan();p['data']['proposals'][0].update(name='<script>name</script>',value='<img src=x onerror=alert(1)>',evidence=[dict(source='<b>',text='</blockquote><script>window.injected=1</script>')])
  text=render(1,'MLB123','<script>title</script>','csrf','k'*24,p)
  self.assertNotIn('<script>window.injected',text);self.assertNotIn('<img src=x',text);self.assertIn('&lt;img',text)

 def test_confirmed_inventory_is_updated_without_rewriting_audit_source(self):
  p=plan('confirmed');original=deepcopy(p['data']);p['result']=dict(fields=[dict(id='MATERIAL',name='Material',confirmed=True)])
  text=render(1,'MLB123','Produto','csrf','k'*24,p)
  self.assertIn('Gravado: Aço',text);self.assertIn('Valor confirmado por nova leitura',text);self.assertEqual(p['data'],original)

 def test_old_reader_or_expired_analysis_does_not_offer_send(self):
  p=plan();p['data'].pop('extractor_version',None)
  text=render(1,'MLB123','P','csrf','k'*24,p)
  self.assertNotIn('Aplicar selecionadas',text);self.assertIn('O leitor foi atualizado',text)
  p=plan();p['created_at']=1;text=render(1,'MLB123','P','csrf','k'*24,p)
  self.assertNotIn('Aplicar selecionadas',text);self.assertIn('A análise expirou',text)
