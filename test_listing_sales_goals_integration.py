import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from auth_test_support import database_session
from listing_sales_goals import create,validate,init_schema
from sales_metrics import reporting_today
from test_listing_sales_goals import form

@unittest.skipUnless(os.getenv('KEIPER_TEST_DATABASE_URL'),'isolated PostgreSQL not configured')
class SalesGoalIntegrationTests(unittest.TestCase):
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
        for label in ('Goal A','Goal B'):
            cid=m.consultar(conn,"INSERT INTO conexoes(cliente,status) VALUES(%s,'ativa') RETURNING id",(label,))[0]['id'];self.ids.append(cid)
            m.executar(conn,"INSERT INTO anuncios(conexao_id,item_id,titulo,quantidade,atualizado_em) VALUES(%s,'MLB123',%s,2,%s)",(cid,label,int(__import__('time').time())))
    self.c=m.app.test_client()
    with database_session(self.c) as s:s.update(usuario_id=1,tipo='admin')
    self.path=f'/anuncios/{self.ids[0]}/MLB123/metas-vendas';self.assertEqual(self.c.get(self.path).status_code,200)
    with self.c.session_transaction() as s:self.token=s['_csrf'];self.actor=s['usuario_id']
 def tearDown(self):
    with self.m.banco() as conn:
        for table in ('listing_sales_goals','vendas_cobertura','anuncios'):self.m.executar(conn,'DELETE FROM '+table+' WHERE conexao_id=ANY(%s)',(self.ids,))
        self.m.executar(conn,'DELETE FROM conexoes WHERE id=ANY(%s)',(self.ids,))
 def data(self):
    from datetime import timedelta
    day=reporting_today()
    return dict(form(),operation='create',start_date=day.isoformat(),end_date=(day+timedelta(days=29)).isoformat(),_csrf=self.token)
 def rows(self):
    with self.m.banco() as conn:return self.m.consultar(conn,'SELECT * FROM listing_sales_goals WHERE conexao_id=%s ORDER BY id',(self.ids[0],))
 def test_create_retry_scoped_cancel_and_preserved_history(self):
    data=self.data();self.assertEqual(self.c.post(self.path,data=data).status_code,303);self.assertEqual(self.c.post(self.path,data=data).status_code,303)
    self.assertEqual(len(self.rows()),1);row=self.rows()[0]
    self.assertEqual(self.c.post(self.path,data=dict(data,target='8')).status_code,400)
    self.assertIn('Aguardando primeiro dia completo',self.c.get(self.path).get_data(as_text=True))
    foreign=self.path.replace('/'+str(self.ids[0])+'/', '/'+str(self.ids[1])+'/')
    cancel=dict(operation='cancel',goal_id=row['id'],_csrf=self.token)
    self.assertEqual(self.c.post(foreign,data=cancel).status_code,404)
    self.assertEqual(self.c.post(self.path,data=cancel).status_code,303);first=self.rows()[0]
    self.assertEqual(self.c.post(self.path,data=cancel).status_code,303);self.assertEqual(self.rows()[0]['cancelled_at'],first['cancelled_at'])
    self.assertEqual(self.rows()[0]['target'],10);self.assertEqual(self.rows()[0]['cancelled_by'],self.actor)
    other=self.m.app.test_client()
    with database_session(other) as s:s.update(usuario_id=2,tipo='cliente',conexao_id=self.ids[0])
    self.assertEqual(other.get(self.path).status_code,403)
    self.assertEqual(self.c.post(self.path,data=dict(data,_csrf='bad')).status_code,400)
 def test_concurrent_retries_and_idempotent_schema(self):
    m=self.m;barrier=Barrier(2);data=validate(self.data(),reporting_today())
    with m.banco() as conn:init_schema(conn,m.executar);init_schema(conn,m.executar)
    def run(_):
        with m.banco() as conn:
            barrier.wait(timeout=5);return create(conn,m.consultar,self.ids[0],'MLB123',data,self.actor)
    with ThreadPoolExecutor(max_workers=2) as pool:ids=list(pool.map(run,range(2)))
    self.assertEqual(ids[0],ids[1]);self.assertEqual(len(self.rows()),1)
 def test_closed_goal_requires_coverage_and_is_scoped(self):
    from datetime import timedelta
    day=reporting_today()-timedelta(days=1)
    data=dict(self.data(),start_date=day.isoformat(),end_date=day.isoformat())
    self.assertEqual(self.c.post(self.path,data=data).status_code,303)
    self.assertIn('Resultado não verificado',self.c.get(self.path).text)
    with self.m.banco() as conn:
        self.m.executar(conn,'INSERT INTO vendas_cobertura(conexao_id,dia,atualizado_em) VALUES(%s,%s,1)',(self.ids[1],day.isoformat()))
    self.assertIn('Resultado não verificado',self.c.get(self.path).text)
    with self.m.banco() as conn:
        self.m.executar(conn,'INSERT INTO vendas_cobertura(conexao_id,dia,atualizado_em) VALUES(%s,%s,1)',(self.ids[0],day.isoformat()))
    result=self.c.get(self.path).text
    self.assertIn('Prazo encerrado · meta não atingida',result);self.assertIn('Apurado: 0',result)
