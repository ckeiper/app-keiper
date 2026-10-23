"""Real PostgreSQL ledger/runner/auth checks; never use a production database."""
import json
import os
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

from auth_test_support import database_session
from keiper_ai_budget import interpret, budget_status
from keiper_ai_store import run_one
from sales_metrics import SAO_PAULO
import test_keiper_ai as fixtures


@unittest.skipUnless(os.getenv('KEIPER_TEST_DATABASE_URL'), 'isolated PostgreSQL URL not configured')
class AIIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ['DATABASE_URL']=os.environ['KEIPER_TEST_DATABASE_URL']
        import main
        cls.m=main
        if main.scheduler.running: main.scheduler.shutdown(wait=False)
        main.iniciar_banco()
        main.app.config['TESTING']=True

    def setUp(self):
        self.env=patch.dict(os.environ, fixtures.BudgetTests().config() | {'KEIPER_AI_MONTHLY_BRL':'50'})
        self.env.start()
        self.ids=[]
        self.run_ids=[]
        with closing(self.m.banco()) as conn, conn:
            for i in range(2):
                self.ids.append(self.m.consultar(conn,"INSERT INTO conexoes(cliente,status) VALUES ('AI test','ativa') RETURNING id")[0]['id'])
                self.run_ids.append(self.m.consultar(conn,"INSERT INTO keiper_ai_runs(conexao_id,day) VALUES(%s,'2026-10-23') RETURNING id",(self.ids[-1],))[0]['id'])
        rules=fixtures.RulesTests(); rules.setUp()
        self.result=rules.analyze()

    def tearDown(self):
        with closing(self.m.banco()) as conn, conn:
            # Delete test ledger before cascading runs so no financial fixture remains.
            self.m.executar(conn,'DELETE FROM keiper_ai_usage WHERE run_id=ANY(%s)',(self.run_ids,))
            self.m.executar(conn,'DELETE FROM ads_dia WHERE conexao_id=ANY(%s)',(self.ids,))
            self.m.executar(conn,'DELETE FROM conexoes WHERE id=ANY(%s)',(self.ids,))
        self.env.stop()

    def call(self, run_id, post):
        return interpret(run_id,self.result,self.m.banco,self.m.consultar,self.m.executar,post)

    def usage(self, run_id):
        with closing(self.m.banco()) as conn, conn:
            return self.m.consultar(conn,'SELECT * FROM keiper_ai_usage WHERE run_id=%s',(run_id,))[0]

    def test_reservation_committed_before_network_and_no_duplicate(self):
        def provider(*args,**kwargs):
            row=self.usage(self.run_ids[0])
            self.assertEqual(row['status'],'reserved')
            self.assertGreater(row['committed_brl'],0)
            self.assertNotIn('AI test',json.dumps(kwargs['json']))
            self.assertFalse(kwargs['json']['store'])
            return Mock(json=lambda:dict(status='completed',usage=dict(input_tokens=100,output_tokens=50),
                output=[dict(type='message',content=[dict(type='output_text',text='Conferir evidências.')])]))
        post=Mock(side_effect=provider)
        text,status=self.call(self.run_ids[0],post)
        self.assertEqual(text,'Conferir evidências.')
        row=self.usage(self.run_ids[0])
        self.assertEqual(row['input_tokens'],100)
        self.assertLess(row['committed_brl'],row['reserved_brl'])
        self.call(self.run_ids[0],post)
        self.assertEqual(post.call_count,1)

    def test_timeout_reservation_survives_and_retry_is_blocked(self):
        post=Mock(side_effect=TimeoutError())
        self.assertIsNone(self.call(self.run_ids[0],post)[0])
        row=self.usage(self.run_ids[0])
        self.assertEqual(row['status'],'uncertain')
        self.assertEqual(row['committed_brl'],row['reserved_brl'])
        self.call(self.run_ids[0],post)
        self.assertEqual(post.call_count,1)

    def test_concurrent_shops_cannot_oversubscribe_global_budget(self):
        # Each reservation costs >.01 and <.04. Only one may fit under .04.
        os.environ['KEIPER_AI_MONTHLY_BRL']='.04'
        barrier=threading.Barrier(2)
        post=Mock(side_effect=TimeoutError())
        def invoke(run_id):
            barrier.wait(timeout=10)
            return self.call(run_id,post)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(invoke,self.run_ids))
        self.assertEqual(post.call_count,1)
        self.assertTrue(any('limite' in s for _,s in results))
        with closing(self.m.banco()) as conn, conn:
            self.assertLessEqual(budget_status(conn,self.m.consultar)['used'],Decimal('.04'))

    def test_month_boundary_and_overrun_block(self):
        response=Mock(json=lambda:dict(status='completed',usage=dict(input_tokens=10**8,output_tokens=1),output=[]))
        self.call(self.run_ids[0],Mock(return_value=response))
        row=self.usage(self.run_ids[0])
        self.assertEqual(row['status'],'overrun')
        with closing(self.m.banco()) as conn, conn:
            self.assertTrue(budget_status(conn,self.m.consultar)['blocked'])
            future=date(row['month'].year+1,1,1)
            self.assertFalse(budget_status(conn,self.m.consultar,future)['blocked'])

    def test_page_authorization_and_read_only_rendering(self):
        with closing(self.m.banco()) as conn, conn:
            self.m.executar(conn,"UPDATE keiper_ai_runs SET result=%s::jsonb,status='completed' WHERE id=%s",
                (json.dumps(self.result),self.run_ids[0]))
        client=self.m.app.test_client()
        with database_session(client) as session:
            session['usuario_id']=1; session['tipo']='cliente'; session['conexao_id']=self.ids[0]
        with patch('requests.post',side_effect=AssertionError('GET must not call APIs')):
            page=client.get('/ia-keiper/'+str(self.ids[0]))
            self.assertEqual(page.status_code,200)
            self.assertIn('Gasto em Ads',page.get_data(as_text=True))
            self.assertNotIn('todas as lojas',page.get_data(as_text=True))
            self.assertEqual(client.get('/ia-keiper/'+str(self.ids[1])).status_code,403)

    def test_runner_runs_once_and_isolates_store_failure(self):
        now=datetime(2026,10,24,10,tzinfo=SAO_PAULO).timestamp()
        original=self.m.consultar
        def query(conn,sql,params=None):
            if sql.startswith('SELECT c.id,c.cliente,c.status FROM conexoes c'):
                sql=sql.replace("WHERE c.status='ativa'", "WHERE c.id=ANY(%s) AND c.status='ativa'")
                params=(self.ids,)+params
            return original(conn,sql,params)
        good=dict(eligible=True,reasons=[],current=dict(revenue=700,orders=70),previous=dict(revenue=1400,orders=100))
        with patch.dict(os.environ,{'KEIPER_AI_PAID_ENABLED':'false'}),patch('overview.load_overview',side_effect=[RuntimeError('private'),dict(reports=[good])]) as load:
            for _ in range(3): run_one(self.m.banco,query,self.m.executar,Mock(),now)
            self.assertEqual(load.call_count,2)
        with closing(self.m.banco()) as conn, conn:
            rows=original(conn,'SELECT id,status,result FROM keiper_ai_runs WHERE conexao_id=ANY(%s) AND day=%s ORDER BY conexao_id',(self.ids,date(2026,10,24)))
            self.run_ids.extend(r['id'] for r in rows)
        self.assertEqual([r['status'] for r in rows],['failed','completed'])
        self.assertIsNotNone(rows[1]['result'])
