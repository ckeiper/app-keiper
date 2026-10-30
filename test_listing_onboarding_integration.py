import os
import unittest
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from auth_test_support import database_session
from listing_onboarding import create_plan,validate,init_schema
from listing_tasks import transition
from sales_metrics import reporting_today
from test_listing_onboarding import form

@unittest.skipUnless(os.getenv('KEIPER_TEST_DATABASE_URL'),'isolated PostgreSQL not configured')
class OnboardingIntegrationTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
    os.environ['DATABASE_URL']=os.environ['KEIPER_TEST_DATABASE_URL']
    import main
    cls.m=main
    if main.scheduler.running:main.scheduler.shutdown(wait=False)
    main.app.config['TESTING']=True
 def setUp(self):
    m=self.m;self.ids=[]
    with m.banco() as conn:
        for label in ('Onboarding A','Onboarding B'):
            cid=m.consultar(conn,"INSERT INTO conexoes(cliente,status) VALUES(%s,'ativa') RETURNING id",(label,))[0]['id'];self.ids.append(cid)
            m.executar(conn,"INSERT INTO anuncios(conexao_id,item_id,titulo) VALUES(%s,'MLB123',%s)",(cid,label))
    self.c=m.app.test_client()
    with database_session(self.c) as s:s.update(usuario_id=1,tipo='admin')
    self.path=f'/anuncios/{self.ids[0]}/MLB123/primeiros-30-dias';self.assertEqual(self.c.get(self.path).status_code,200)
    with self.c.session_transaction() as s:self.token=s['_csrf'];self.actor=s['usuario_id']
 def tearDown(self):
    with self.m.banco() as conn:
        self.m.executar(conn,'DELETE FROM listing_onboarding_steps WHERE plan_id IN (SELECT id FROM listing_onboarding_plans WHERE conexao_id=ANY(%s))',(self.ids,))
        for table in ('listing_onboarding_plans','listing_task_events','listing_tasks','anuncios'):self.m.executar(conn,'DELETE FROM '+table+' WHERE conexao_id=ANY(%s)',(self.ids,))
        self.m.executar(conn,'DELETE FROM conexoes WHERE id=ANY(%s)',(self.ids,))
 def data(self):return dict(form(),start_date=reporting_today().isoformat(),_csrf=self.token)
 def rows(self,table):
    with self.m.banco() as conn:return self.m.consultar(conn,'SELECT * FROM '+table+' WHERE conexao_id=%s ORDER BY id',(self.ids[0],))
 def test_create_retry_scope_csrf_and_progress_from_tasks(self):
    m=self.m;data=self.data()
    self.assertEqual(self.c.post(self.path,data=data).status_code,303)
    self.assertEqual(self.c.post(self.path,data=data).status_code,303)
    self.assertEqual(len(self.rows('listing_tasks')),4);self.assertEqual(len(self.rows('listing_task_events')),4)
    self.assertEqual(self.c.post(self.path,data=dict(data,responsible='Outro')).status_code,400)
    row=self.rows('listing_tasks')[0]
    with m.banco() as conn:transition(conn,m.consultar,m.executar,self.ids[0],'MLB123',row['id'],1,'open','done',self.actor)
    text=self.c.get(self.path).get_data(as_text=True);self.assertIn('1 de 4 etapas concluídas',text)
    foreign=self.path.replace('/'+str(self.ids[0])+'/', '/'+str(self.ids[1])+'/')
    self.assertIn('Planejar acompanhamento',self.c.get(foreign).get_data(as_text=True))
    self.assertEqual(self.c.post(self.path,data=dict(data,_csrf='wrong')).status_code,400)
    other=m.app.test_client()
    with database_session(other) as s:s.update(usuario_id=2,tipo='cliente',conexao_id=self.ids[0])
    self.assertEqual(other.get(self.path).status_code,403)
 def test_failure_rolls_back_whole_plan_and_schema_idempotent(self):
    m=self.m
    with m.banco() as conn:init_schema(conn,m.executar);init_schema(conn,m.executar)
    with patch('listing_onboarding.create',side_effect=RuntimeError('isolated task failure')):
        with self.assertRaises(RuntimeError):self.c.post(self.path,data=self.data())
    self.assertEqual(self.rows('listing_onboarding_plans'),[]);self.assertEqual(self.rows('listing_tasks'),[])
 def test_concurrent_retries_create_only_four_tasks(self):
    m=self.m;barrier=Barrier(2);data=validate(self.data(),reporting_today())
    def run(_):
        with m.banco() as conn:
            barrier.wait(timeout=5)
            return create_plan(conn,m.consultar,m.executar,self.ids[0],'MLB123',data,self.actor)
    with ThreadPoolExecutor(max_workers=2) as pool:ids=list(pool.map(run,range(2)))
    self.assertEqual(ids[0],ids[1]);self.assertEqual(len(self.rows('listing_tasks')),4)
