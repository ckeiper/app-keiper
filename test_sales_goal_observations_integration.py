import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from auth_test_support import database_session
from listing_sales_goals import create,validate,init_schema
from sales_metrics import reporting_today
from test_listing_sales_goals import form

@unittest.skipUnless(os.getenv('KEIPER_TEST_DATABASE_URL'),'isolated PostgreSQL not configured')
class SalesGoalHistoryIntegrationTests(unittest.TestCase):
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
        for table in ('listing_sales_goal_observations','listing_sales_goals','vendas_cobertura','anuncios'):self.m.executar(conn,'DELETE FROM '+table+' WHERE conexao_id=ANY(%s)',(self.ids,))
        self.m.executar(conn,'DELETE FROM conexoes WHERE id=ANY(%s)',(self.ids,))
 def data(self):
    from datetime import timedelta
    day=reporting_today()
    return dict(form(),operation='create',start_date=day.isoformat(),end_date=(day+timedelta(days=29)).isoformat(),_csrf=self.token)
 def rows(self):
    with self.m.banco() as conn:return self.m.consultar(conn,'SELECT * FROM listing_sales_goals WHERE conexao_id=%s ORDER BY id',(self.ids[0],))
 def test_persist_retry_coverage_revision_cancel_history_and_tenant(self):
    from datetime import timedelta
    from sales_goal_observations import collect,init_schema
    import time
    m=self.m;day=reporting_today()-timedelta(days=1);now=int(time.time())
    data=dict(self.data(),start_date=day.isoformat(),end_date=day.isoformat())
    self.assertEqual(self.c.post(self.path,data=data).status_code,303)
    goal=self.rows()[0];gid=goal['id']
    # Collection cannot predate creation when the request crosses a second.
    now=max(int(time.time()),goal['created_at'])
    with m.banco() as conn:init_schema(conn,m.executar);init_schema(conn,m.executar)
    collect(self.ids[0],m.banco,m.consultar,m.executar,now);collect(self.ids[0],m.banco,m.consultar,m.executar,now)
    with m.banco() as conn:
        rows=m.consultar(conn,'SELECT * FROM listing_sales_goal_observations WHERE goal_id=%s',(gid,))
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['state'],'unknown');self.assertIsNone(rows[0]['value'])
        m.executar(conn,'INSERT INTO vendas_cobertura(conexao_id,dia,atualizado_em) VALUES(%s,%s,%s)',(self.ids[0],day.isoformat(),now))
    collect(self.ids[0],m.banco,m.consultar,m.executar,now+1)
    history=self.path+'/historico/'+str(gid)
    self.assertIn('meta não atingida',self.c.get(history).text)
    self.assertIn('Resultado não verificado',self.c.get(history).text)
    foreign=history.replace('/'+str(self.ids[0])+'/', '/'+str(self.ids[1])+'/');self.assertEqual(self.c.get(foreign).status_code,404)
    self.assertEqual(self.c.post(self.path,data=dict(operation='cancel',goal_id=gid,_csrf=self.token)).status_code,303)
    collect(self.ids[0],m.banco,m.consultar,m.executar,now+2)
    with m.banco() as conn:self.assertEqual(m.consultar(conn,'SELECT COUNT(*) AS n FROM listing_sales_goal_observations WHERE goal_id=%s',(gid,))[0]['n'],2)
    self.assertEqual(self.c.get(history).status_code,200)
