"""Real PostgreSQL, exclusively synthetic SMTP callbacks and isolated fixtures."""
import os,time,unittest
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock
from auth_test_support import database_session
from sales_metrics import reporting_today
from goal_notifications import save,dispatch,init_schema
from listing_goals import create as create_stock,validate as validate_stock
from listing_sales_goals import create as create_sales,validate as validate_sales
from goal_observations import collect as collect_stock
from sales_goal_observations import collect as collect_sales

@unittest.skipUnless(os.getenv('KEIPER_TEST_DATABASE_URL'),'isolated PostgreSQL not configured')
class GoalNotificationIntegrationTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
    os.environ['DATABASE_URL']=os.environ['KEIPER_TEST_DATABASE_URL']
    import main
    cls.m=main
    if main.scheduler.running:main.scheduler.shutdown(wait=False)
    main.app.config['TESTING']=True
 def setUp(self):
    m=self.m;self.now=int(time.time());day=reporting_today();self.day=day
    self.c=m.app.test_client()
    with database_session(self.c) as s:s.update(usuario_id=811,tipo='admin')
    with self.c.session_transaction() as s:self.uid=s['usuario_id']
    self.email='goal-admin@example.invalid'
    with m.banco() as conn:
        init_schema(conn,m.executar);init_schema(conn,m.executar)
        m.executar(conn,'UPDATE usuarios SET email=%s WHERE id=%s',(self.email,self.uid))
        self.cid=m.consultar(conn,"INSERT INTO conexoes(cliente,status) VALUES('Notification fixture','ativa') RETURNING id")[0]['id']
        m.executar(conn,"INSERT INTO anuncios(conexao_id,item_id,titulo,quantidade,atualizado_em) VALUES(%s,'MLB123','Synthetic',0,%s)",(self.cid,self.now))
        common=dict(start_date=day.isoformat(),end_date=day.isoformat(),responsible='Test',submission_key='x'*24)
        self.stock=create_stock(conn,m.consultar,self.cid,'MLB123',validate_stock(dict(common,minimum='5'),day),self.uid)
        past=(day-timedelta(days=1)).isoformat()
        self.sales=create_sales(conn,m.consultar,self.cid,'MLB123',validate_sales(dict(common,metric='units',target='5',start_date=past,end_date=past),day),self.uid)
    self.path=f'/anuncios/{self.cid}/MLB123/metas/avisos/stock/{self.stock}'
    self.assertEqual(self.c.get(self.path).status_code,200)
    with self.c.session_transaction() as s:self.token=s['_csrf']
    self.now=int(time.time())
    with m.banco() as conn:m.executar(conn,'UPDATE anuncios SET atualizado_em=%s WHERE conexao_id=%s',(self.now,self.cid))
 def tearDown(self):
    m=self.m
    with m.banco() as conn:
        m.executar(conn,'DELETE FROM listing_goal_notifications WHERE subscription_id IN (SELECT id FROM listing_goal_subscriptions WHERE conexao_id=%s)',(self.cid,))
        for table in ('listing_goal_subscriptions','listing_goal_observations','listing_sales_goal_observations','listing_stock_goals','listing_sales_goals','anuncios','vendas_cobertura'):
            m.executar(conn,'DELETE FROM '+table+' WHERE conexao_id=%s',(self.cid,))
        m.executar(conn,'DELETE FROM conexoes WHERE id=%s',(self.cid,))
        m.executar(conn,'UPDATE usuarios SET email=NULL WHERE id=%s',(self.uid,))
 def enable(self,kind='stock'):
    with self.m.banco() as conn:save(conn,self.m.consultar,self.cid,'MLB123',kind,self.stock if kind=='stock' else self.sales,self.uid,dict(enabled='yes',confirmed_email=self.email),self.now-1)
 def run_dispatch(self,now=None,sender=None):
    self.sender=sender or Mock(return_value=True)
    return dispatch(self.m.banco,self.m.consultar,self.m.executar,now or self.now+2,self.sender,lambda:True)
 def count(self):
    with self.m.banco() as conn:return self.m.consultar(conn,'SELECT n.* FROM listing_goal_notifications n JOIN listing_goal_subscriptions s ON s.id=n.subscription_id WHERE s.conexao_id=%s ORDER BY n.id',(self.cid,))
 def test_default_off_explicit_consent_csrf_own_email_and_disable(self):
    m=self.m;collect_stock(self.cid,m.banco,m.consultar,m.executar,self.now+1)
    self.assertEqual(self.run_dispatch(),0)
    self.assertEqual(self.c.post(self.path,data=dict(enabled='yes',confirmed_email=self.email)).status_code,400)
    self.assertEqual(self.c.post(self.path,data=dict(enabled='yes',confirmed_email='someone@example.invalid',_csrf=self.token)).status_code,400)
    self.enable();self.assertEqual(self.run_dispatch(),1);self.assertEqual(self.sender.call_args.args[0],self.email)
    self.assertEqual(self.run_dispatch(),0);self.assertEqual(len(self.count()),1)
    self.assertIn('Aceito pelo SMTP',self.c.get(self.path).text)
    self.assertEqual(self.c.post(self.path,data=dict(_csrf=self.token)).status_code,303)
    self.assertEqual(self.run_dispatch(self.now+3),0)
    self.assertEqual(self.c.get(self.path.replace('MLB123','MLB999')).status_code,404)
    other=m.app.test_client()
    with database_session(other) as s:s.update(usuario_id=812,tipo='admin')
    self.assertNotIn('Aceito pelo SMTP',other.get(self.path).text)
 def test_new_evaluation_after_enable_required_and_concurrent_dedup(self):
    m=self.m
    collect_stock(self.cid,m.banco,m.consultar,m.executar,self.now)
    with m.banco() as conn:save(conn,m.consultar,self.cid,'MLB123','stock',self.stock,self.uid,dict(enabled='yes',confirmed_email=self.email),self.now)
    self.assertEqual(self.run_dispatch(),0)
    collect_stock(self.cid,m.banco,m.consultar,m.executar,self.now+1)
    sender=Mock(return_value=True)
    def run(_):return dispatch(m.banco,m.consultar,m.executar,self.now+2,sender,lambda:True)
    with ThreadPoolExecutor(max_workers=2) as pool:counts=list(pool.map(run,range(2)))
    self.assertEqual(sum(counts),1);self.assertEqual(sender.call_count,1);self.assertEqual(len(self.count()),1)
 def test_unknown_sales_then_verified_deadline_and_uncertain_no_retry(self):
    m=self.m;self.enable('sales')
    collect_sales(self.cid,m.banco,m.consultar,m.executar,self.now+1);self.assertEqual(self.run_dispatch(),0)
    with m.banco() as conn:m.executar(conn,'INSERT INTO vendas_cobertura(conexao_id,dia,atualizado_em) VALUES(%s,%s,%s)',(self.cid,(self.day-timedelta(days=1)).isoformat(),self.now))
    collect_sales(self.cid,m.banco,m.consultar,m.executar,self.now+2)
    self.assertEqual(self.run_dispatch(self.now+3,Mock(side_effect=TimeoutError)),1);self.assertEqual(self.count()[0]['state'],'uncertain')
    self.assertEqual(self.run_dispatch(self.now+4),0)
 def test_suppression_latest_state_stale_stock_email_change_cancel_and_inactive(self):
    m=self.m;self.enable();collect_stock(self.cid,m.banco,m.consultar,m.executar,self.now+1)
    with m.banco() as conn:m.executar(conn,"UPDATE usuarios SET email='changed@example.invalid' WHERE id=%s",(self.uid,))
    self.assertEqual(self.run_dispatch(),0)
    with m.banco() as conn:
        m.executar(conn,'UPDATE usuarios SET email=%s WHERE id=%s',(self.email,self.uid))
        m.executar(conn,"UPDATE conexoes SET status='inativa' WHERE id=%s",(self.cid,))
    self.assertEqual(self.run_dispatch(),0)
    with m.banco() as conn:
        m.executar(conn,"UPDATE conexoes SET status='ativa' WHERE id=%s",(self.cid,))
        m.executar(conn,'UPDATE anuncios SET quantidade=10,atualizado_em=%s WHERE conexao_id=%s',(self.now+2,self.cid))
    self.assertEqual(self.run_dispatch(self.now+3),0) # Catalog changed since alert.
    collect_stock(self.cid,m.banco,m.consultar,m.executar,self.now+3);self.assertEqual(self.run_dispatch(self.now+4),0)
    with m.banco() as conn:m.executar(conn,'UPDATE anuncios SET quantidade=0,atualizado_em=%s WHERE conexao_id=%s',(self.now+4,self.cid))
    collect_stock(self.cid,m.banco,m.consultar,m.executar,self.now+5)
    self.assertEqual(self.run_dispatch(self.now+21605),0)
    with m.banco() as conn:m.executar(conn,'UPDATE listing_stock_goals SET cancelled_at=%s WHERE id=%s',(self.now+5,self.stock))
    self.assertEqual(self.run_dispatch(self.now+6),0)
