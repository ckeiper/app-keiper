"""Disposable PostgreSQL: concurrency, scope, durable intent and route retries."""
import os
import time
import unittest
import uuid
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock
import psycopg2
import requests
from psycopg2.extras import RealDictCursor
import attribute_edit_store as store
from attribute_edit_workflow import apply
from test_attribute_completion import listing,definition,response,facts,analyze

@unittest.skipUnless(os.getenv('KEIPER_TEST_DATABASE_URL'),'isolated PostgreSQL not configured')
class AttributeStoreIntegration(unittest.TestCase):
 def bank(self):return psycopg2.connect(os.environ['KEIPER_TEST_DATABASE_URL'])
 def query(self,conn,sql,args=()):
  with conn.cursor(cursor_factory=RealDictCursor) as c:c.execute(sql,args);return c.fetchall()
 @classmethod
 def setUpClass(cls):
  self=cls();conn=self.bank()
  try:
   store.init_schema(conn,lambda c,s,a=():c.cursor().execute(s,a));store.init_schema(conn,lambda c,s,a=():c.cursor().execute(s,a));conn.commit()
  finally:conn.close()
 def setUp(self):self.item='MLB'+str(uuid.uuid4().int%10**19);self.ids=[]
 def tearDown(self):
  conn=self.bank()
  try:
   with conn:
    self.query(conn,'DELETE FROM listing_attribute_events WHERE plan_id IN (SELECT id FROM listing_attribute_plans WHERE item_id=%s) RETURNING id',(self.item,))
    self.query(conn,'DELETE FROM listing_attribute_plans WHERE item_id=%s RETURNING id',(self.item,))
  finally:conn.close()
 def ready(self,conn,key,cid=991):
  p,_=store.create(conn,self.query,cid,self.item,42,key*24);data=analyze(facts());data['fingerprint']=data['fingerprint']
  store.transition(conn,self.query,p,42,'ready',data=data);return store.load(conn,self.query,cid,self.item,42,str(p['id']))
 def test_session_lock_survives_commits_and_is_released_on_close(self):
  with store.locked(self.bank,self.query,991,self.item) as conn:
   conn.commit()
   def competing():
    with self.assertRaises(ValueError):
     with store.locked(self.bank,self.query,992,self.item):pass
   with ThreadPoolExecutor(max_workers=1) as pool:pool.submit(competing).result(timeout=10)
  with store.locked(self.bank,self.query,992,self.item):pass
 def test_dedup_scope_and_global_pending_constraint(self):
  with store.locked(self.bank,self.query,991,self.item) as conn:
   p=self.ready(conn,'a');same,created=store.create(conn,self.query,991,self.item,42,'a'*24)
   self.assertFalse(created);self.assertEqual(same['id'],p['id'])
   with self.assertRaises(ValueError):store.load(conn,self.query,992,self.item,42,str(p['id']))
   with self.assertRaises(ValueError):store.load(conn,self.query,991,self.item,43,str(p['id']))
   other=self.ready(conn,'b',992);store.transition(conn,self.query,p,42,'sending',selected=['MATERIAL'])
   with self.assertRaises(psycopg2.IntegrityError):store.transition(conn,self.query,other,42,'sending',selected=['MATERIAL'])
   conn.rollback();self.assertEqual(store.load(conn,self.query,991,self.item,42,str(p['id']))['state'],'sending')
 def test_concurrent_plans_at_most_one_marketplace_write(self):
  backend=listing(id=self.item);defs=[definition()];description=dict(plain_text='Material: Aço')
  def get(url,**kwargs):
   if url.endswith('/users/me'):value=dict(id=123)
   elif url.endswith('/description'):value=description
   elif url.endswith('/attributes'):value=defs
   elif url.endswith('/technical_specs/input'):value=dict(groups=[])
   else:value=backend
   return response(deepcopy(value))
  from attribute_completion import gather
  data=analyze(gather('private',123,self.item,get))
  plans=[]
  with store.locked(self.bank,self.query,991,self.item) as conn:
   for key in ['a','b']:
    p,_=store.create(conn,self.query,991,self.item,42,key*24);store.transition(conn,self.query,p,42,'ready',data=data);plans.append(str(p['id']))
  def put(url,**kwargs):backend['attributes']=kwargs['json']['attributes'];return response({})
  writer=Mock(side_effect=put)
  def run(identifier):
   try:
    with store.locked(self.bank,self.query,991,self.item) as conn:
     p=store.load(conn,self.query,991,self.item,42,identifier)
     persist=lambda state,result,**kw:store.transition(conn,self.query,p,42,state,result,**kw)
     apply(p,['MATERIAL'],'private',123,self.item,get,writer,persist)
    return 'done'
   except ValueError:return 'busy'
  with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(run,plans))
  self.assertEqual(writer.call_count,1)
  with store.locked(self.bank,self.query,991,self.item) as conn:
   rows=self.query(conn,'SELECT state FROM listing_attribute_plans WHERE item_id=%s',(self.item,));self.assertEqual(sum(r['state']=='confirmed' for r in rows),1)

 def test_route_analyze_apply_retry_and_actor_isolation(self):
  from flask import Flask,session,redirect
  from functools import wraps
  from attribute_editor import register
  from web_security import install_security
  app=Flask(__name__);app.secret_key='isolated';app.testing=True;install_security(app)
  backend=listing(id=self.item);defs=[definition()]
  def get(url,**kwargs):
   if url.endswith('/users/me'):value=dict(id=123)
   elif url.endswith('/description'):value=dict(plain_text='Material: Aço')
   elif url.endswith('/attributes'):value=defs
   elif url.endswith('/technical_specs/input'):value=dict(groups=[])
   else:value=backend
   return response(deepcopy(value))
  def put(url,**kwargs):
   update=kwargs['json']
   if 'attributes' in update:backend['attributes']=deepcopy(update['attributes'])
   for v in update.get('variations',[]):
    existing=next(row for row in backend['variations'] if row['id']==v['id'])
    if 'attributes' in v:existing['attributes']=deepcopy(v['attributes'])
   return response({})
  reader=Mock(side_effect=get);writer=Mock(side_effect=put)
  def query(conn,sql,args=()):
   if 'JOIN anuncios' in sql:return [dict(user_id=123,titulo='Produto',cliente='Loja',status='ativa')]
   return self.query(conn,sql,args)
  def login(fn):
   @wraps(fn)
   def guard(*a,**kw):return fn(*a,**kw) if session.get('usuario_id') else redirect('/login')
   return guard
  register(app,login,lambda cid:cid==991,self.bank,query,lambda *a,**kw:a[-1],lambda shop:'private',reader,writer)
  c=app.test_client();path=f'/anuncios/991/{self.item}/completar-ficha'
  with c.session_transaction() as state:state.update(usuario_id=42,tipo='admin',_csrf='csrf')
  self.assertEqual(c.get(path).status_code,200);reader.assert_not_called();writer.assert_not_called()
  self.assertEqual(c.post(path,data=dict(action='analyze',analysis_key='k'*24)).status_code,400)
  result=c.post(path,data=dict(_csrf='csrf',action='analyze',analysis_key='k'*24));self.assertEqual(result.status_code,303)
  location=result.headers['Location'];pid=location.split('plan=')[1]
  self.assertIn('Aplicar selecionadas',c.get(location).text);writer.assert_not_called()
  data=dict(_csrf='csrf',action='apply',plan=pid,selected='MATERIAL')
  self.assertEqual(c.post(path,data=data).status_code,303);self.assertIn('Gravação confirmada',c.get(location).text)
  before=reader.call_count;self.assertEqual(c.post(path,data=data).status_code,200);self.assertEqual(writer.call_count,1);self.assertEqual(reader.call_count,before)
  backend['attributes']=[]
  pending=c.post(path,data=dict(_csrf='csrf',action='analyze',analysis_key='l'*24)).headers['Location'];pending_id=pending.split('plan=')[1]
  writer.side_effect=requests.Timeout()
  self.assertEqual(c.post(path,data=dict(_csrf='csrf',action='apply',plan=pending_id,selected='MATERIAL')).status_code,303)
  self.assertIn('Gravação não confirmada',c.get(pending).text);self.assertEqual(writer.call_count,2)
  reads=reader.call_count
  self.assertEqual(c.post(path,data=dict(_csrf='csrf',action='analyze',analysis_key='m'*24)).headers['Location'],pending)
  self.assertEqual(reader.call_count,reads);self.assertEqual(writer.call_count,2)
  self.assertEqual(c.post(path,data=dict(_csrf='csrf',action='verify',plan=pending_id)).status_code,303);self.assertEqual(writer.call_count,2)
  self.assertEqual(c.post(path,data=dict(_csrf='csrf',action='close',plan=pending_id)).status_code,200)
  self.assertEqual(c.post(path,data=dict(_csrf='csrf',action='close',plan=pending_id,manual_checked='1')).status_code,303)
  self.assertIn('Encerrada após conferência manual',c.get(pending).text);self.assertEqual(writer.call_count,2)
  # A declared value creates a successor review; no marketplace write occurs.
  backend['attributes']=[]
  original=c.post(path,data=dict(_csrf='csrf',action='analyze',analysis_key='n'*24)).headers['Location'];original_id=original.split('plan=')[1]
  manual=dict(_csrf='csrf',action='manual',plan=original_id,manual_key='o'*24,manual_field='MATERIAL',manual_value='Plástico',manual_note='Fabricante')
  writes=writer.call_count
  child=c.post(path,data=manual);self.assertEqual(child.status_code,303)
  child_location=child.headers['Location'];child_id=child_location.split('plan=')[1]
  self.assertNotEqual(child_id,original_id);self.assertEqual(writer.call_count,writes)
  self.assertIn('Informado: Plástico',c.get(child_location).text)
  self.assertIn('Continuar revisão atualizada',c.get(original).text)
  reads=reader.call_count
  self.assertEqual(c.post(path,data=manual).headers['Location'],child_location)
  self.assertEqual(reader.call_count,reads);self.assertEqual(writer.call_count,writes)
  changed=dict(manual,manual_value='Ferro')
  self.assertEqual(c.post(path,data=changed).status_code,200);self.assertEqual(reader.call_count,reads)
  self.assertEqual(c.post(path,data=dict(manual,manual_key='p'*24)).status_code,200);self.assertEqual(reader.call_count,reads)
  # An invalid official value leaves the current revision available and retains input.
  invalid=dict(manual,plan=child_id,manual_key='q'*24,manual_value='x'*101)
  failed=c.post(path,data=invalid);self.assertEqual(failed.status_code,200);self.assertIn('Valor incompatível',failed.text)
  self.assertIn('value="'+'x'*101+'"',failed.text)
  writer.side_effect=put
  self.assertEqual(c.post(path,data=dict(_csrf='csrf',action='apply',plan=child_id,selected='MATERIAL')).status_code,303)
  self.assertEqual(writer.call_count,writes+1);self.assertEqual(backend['attributes'],[dict(id='MATERIAL',value_name='Plástico')])
  self.assertIn('Gravação confirmada',c.get(child_location).text)
  with self.bank() as conn:
   saved=store.load(conn,self.query,991,self.item,42,child_id)
   self.assertEqual(saved['data']['manual_actor'],42);self.assertEqual(saved['data']['manual_inputs'][0]['note'],'Fabricante')
   self.assertEqual(store.load(conn,self.query,991,self.item,42,original_id)['state'],'stale')
  # Variation attributes keep every ID and previously recorded value.
  from test_attribute_variations import variant,rule
  backend['variations']=[variant(),variant(102)];defs[:]=[rule()]
  variation=c.post(path,data=dict(_csrf='csrf',action='analyze',analysis_key='r'*24)).headers['Location'];variation_id=variation.split('plan=')[1]
  before=writer.call_count;reads=reader.call_count
  vform=dict(_csrf='csrf',action='manual',plan=variation_id,manual_key='s'*24,manual_field='v:999:GTIN',manual_value='789000001',manual_note='Fabricante')
  self.assertEqual(c.post(path,data=vform).status_code,200);self.assertEqual(reader.call_count,reads);self.assertEqual(writer.call_count,before)
  vform['manual_field']='v:101:GTIN'
  draft=c.post(path,data=vform);self.assertEqual(draft.status_code,303);draft_location=draft.headers['Location'];draft_id=draft_location.split('plan=')[1]
  self.assertIn('Variação 101',c.get(draft_location).text);self.assertEqual(writer.call_count,before)
  self.assertEqual(c.post(path,data=dict(_csrf='csrf',action='apply',plan=draft_id,selected='v:101:GTIN')).status_code,303)
  self.assertEqual(writer.call_count,before+1);self.assertIn('Gravação confirmada',c.get(draft_location).text)
  update=writer.call_args.kwargs['json'];self.assertEqual([v['id'] for v in update['variations']],[101,102]);self.assertEqual(update['variations'][1],dict(id=102))
  self.assertEqual(backend['variations'][0]['attributes'][0],dict(id='SELLER_SKU',value_name='sku-101'));self.assertEqual(backend['variations'][0]['available_quantity'],4)
  self.assertEqual(backend['variations'][1]['attributes'],[dict(id='SELLER_SKU',value_name='sku-102')])
  self.assertEqual(c.post(path,data=dict(_csrf='csrf',action='apply',plan=draft_id,selected='v:101:GTIN')).status_code,200);self.assertEqual(writer.call_count,before+1)
  # A mixed batch produces one successor and one read, never a partial draft.
  from werkzeug.datastructures import MultiDict
  backend['attributes']=[];backend['variations']=[variant(),variant(102)];defs[:]=[definition(),rule()]
  batch_parent=c.post(path,data=dict(_csrf='csrf',action='analyze',analysis_key='t'*24)).headers['Location'].split('plan=')[1]
  batch=MultiDict([('_csrf','csrf'),('action','manual'),('plan',batch_parent),('manual_key','u'*24),('manual_field','MATERIAL'),('manual_value','Aço'),('manual_note','Fonte comum'),('manual_field','v:101:GTIN'),('manual_value','789000001'),('manual_note','Fonte azul'),('manual_field','v:102:GTIN'),('manual_value','x'*101),('manual_note','Fonte preta')])
  before=writer.call_count;reads=reader.call_count
  failed=c.post(path,data=batch);self.assertEqual(failed.status_code,200);self.assertIn('Valor incompatível',failed.text);self.assertEqual(failed.text.count('class="ae-manual-row"'),3)
  self.assertIn('Fonte azul',failed.text);self.assertIn('Fonte preta',failed.text);self.assertEqual(writer.call_count,before)
  with self.bank() as conn:
   self.assertEqual(store.load(conn,self.query,991,self.item,42,batch_parent)['state'],'ready');self.assertIsNone(store.by_key(conn,self.query,991,self.item,42,'u'*24))
  batch.setlist('manual_value',['Aço','789000001','789000002']);reads=reader.call_count
  result=c.post(path,data=batch);self.assertEqual(result.status_code,303);self.assertEqual(reader.call_count-reads,5);self.assertEqual(writer.call_count,before)
  batch_location=result.headers['Location'];batch_id=batch_location.split('plan=')[1]
  reads=reader.call_count;self.assertEqual(c.post(path,data=batch).headers['Location'],batch_location);self.assertEqual(reader.call_count,reads)
  with self.bank() as conn:
   saved=store.load(conn,self.query,991,self.item,42,batch_id);self.assertEqual(len(saved['data']['manual_inputs']),3);self.assertEqual(saved['data']['manual_actor'],42)
  selected=MultiDict([('_csrf','csrf'),('action','apply'),('plan',batch_id),('selected','MATERIAL'),('selected','v:102:GTIN')])
  self.assertEqual(c.post(path,data=selected).status_code,303);self.assertEqual(writer.call_count,before+1)
  update=writer.call_args.kwargs['json'];self.assertEqual(update['attributes'],[dict(id='MATERIAL',value_name='Aço')]);self.assertEqual(update['variations'][0],dict(id=101));self.assertEqual(update['variations'][1]['attributes'][-1]['value_name'],'789000002')
  self.assertIn('Gravação confirmada',c.get(batch_location).text)
  with c.session_transaction() as state:state['usuario_id']=43
  self.assertEqual(c.get(location).status_code,404)
