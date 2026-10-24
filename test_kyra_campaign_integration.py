"""Campaign persistence/scheduling/auth using a disposable PostgreSQL only."""
import os
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from unittest.mock import Mock, patch

from auth_test_support import database_session
from kyra_campaign_store import run_one
import test_kyra_campaigns as fixtures


@unittest.skipUnless(os.getenv('KEIPER_TEST_DATABASE_URL'),'isolated PostgreSQL URL not configured')
class CampaignIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ['DATABASE_URL']=os.environ['KEIPER_TEST_DATABASE_URL']
        import main
        cls.m=main
        if main.scheduler.running:main.scheduler.shutdown(wait=False)
        main.iniciar_banco()
        main.app.config['TESTING']=True

    def setUp(self):
        self.fixture=fixtures.CampaignRulesTests();self.fixture.setUp();self.fixture.add(revenue=0)
        self.ids=[]
        with closing(self.m.banco()) as conn,conn:
            for i in range(2):
                cid=self.m.consultar(conn,"INSERT INTO conexoes(cliente,status) VALUES('Campaign test','ativa') RETURNING id")[0]['id']
                self.ids.append(cid)
                self.m.executar(conn,"INSERT INTO ads_campanhas(conexao_id,campanha_id,nome,status,orcamento,roas_objetivo,atualizado_em) VALUES(%s,'a','Campaign test','active',150,10,%s)",(cid,int(self.fixture.now)))
                for row in self.fixture.rows:
                    self.m.executar(conn,'''INSERT INTO ads_campanha_dia(conexao_id,campanha_id,data,gasto,faturamento,atualizado_em,vendas_atribuidas,faturamento_sem_ads,metricas_vendas_coletadas_em)
                        VALUES(%s,'a',%s,%s,%s,%s,%s,%s,%s)''',
                        (cid,row['data'],row['gasto'],row['faturamento'],int(row['atualizado_em']),row['vendas_atribuidas'],row['faturamento_sem_ads'],int(row['metricas_vendas_coletadas_em'])))

    def tearDown(self):
        with closing(self.m.banco()) as conn,conn:
            self.m.executar(conn,'DELETE FROM ads_campanha_dia WHERE conexao_id=ANY(%s)',(self.ids,))
            self.m.executar(conn,'DELETE FROM ads_campanhas WHERE conexao_id=ANY(%s)',(self.ids,))
            self.m.executar(conn,'DELETE FROM conexoes WHERE id=ANY(%s)',(self.ids,))

    def query(self,conn,sql,params=None):
        if sql.startswith('SELECT c.id FROM conexoes c'):
            sql=sql.replace("WHERE c.status='ativa'","WHERE c.id=ANY(%s) AND c.status='ativa'")
            params=(self.ids,)+params
        return self.m.consultar(conn,sql,params)

    def runs(self):
        with closing(self.m.banco()) as conn,conn:
            return self.m.consultar(conn,'SELECT * FROM keiper_ai_campaign_runs WHERE conexao_id=ANY(%s) ORDER BY conexao_id',(self.ids,))

    def tick(self):
        return run_one(self.m.banco,self.query,self.m.executar,Mock(),self.fixture.now)

    def test_daily_runner_persists_each_store_once_without_external_calls(self):
        with patch.dict(os.environ,{'KEIPER_AI_DAILY_ENABLED':'true','KEIPER_AI_CAMPAIGNS_ENABLED':'true'}),patch('requests.post',side_effect=AssertionError('No external calls')):
            for _ in range(3):self.tick()
        runs=self.runs()
        self.assertEqual(len(runs),2)
        self.assertTrue(all(r['status']=='completed' for r in runs))
        self.assertTrue(all(r['result']['recommendations'][0]['code']=='spend_without_revenue' for r in runs))
        self.assertEqual(runs[0]['result']['recommendations'][0]['current']['spend'],700)
        self.assertEqual(runs[0]['result']['active'],1)

    def test_failure_is_durable_and_not_retried_same_day(self):
        with patch.dict(os.environ,{'KEIPER_AI_DAILY_ENABLED':'true','KEIPER_AI_CAMPAIGNS_ENABLED':'true'}),patch('kyra_campaign_store.analyze',side_effect=RuntimeError('private')) as analyze:
            for _ in range(3):self.tick()
        self.assertEqual(analyze.call_count,2)
        self.assertEqual([r['status'] for r in self.runs()],['failed','failed'])
        self.assertTrue(all(r['result'] is None for r in self.runs()))

    def test_concurrent_ticks_do_not_duplicate_store_day(self):
        barrier=threading.Barrier(2)
        def tick(_):
            barrier.wait(timeout=10)
            return self.tick()
        with patch.dict(os.environ,{'KEIPER_AI_DAILY_ENABLED':'true','KEIPER_AI_CAMPAIGNS_ENABLED':'true'}),ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(tick,range(2)))
        runs=self.runs()
        self.assertTrue(runs)
        self.assertEqual(len(runs),len({(r['conexao_id'],r['day']) for r in runs}))

    def test_get_is_read_only_and_other_store_is_forbidden(self):
        self.tick();client=self.m.app.test_client()
        with database_session(client) as session:
            session['usuario_id']=1;session['tipo']='cliente';session['conexao_id']=self.ids[0]
        before=self.runs()
        with patch('requests.post',side_effect=AssertionError('No API calls')),patch('kyra_campaign_store.run_one',side_effect=AssertionError('No analysis on GET')):
            page=client.get('/ia-keiper/'+str(self.ids[0]))
            self.assertEqual(page.status_code,200)
            html=page.get_data(as_text=True)
            self.assertIn('Investigar gasto sem receita atribuída',html)
            self.assertIn('/ads/'+str(self.ids[0])+'/campanha/a',html)
            self.assertNotIn('todas as lojas',html)
            self.assertEqual(client.get('/ia-keiper/'+str(self.ids[1])).status_code,403)
        self.assertEqual(before,self.runs())

    def test_kill_switch_stops_new_campaign_work(self):
        with patch.dict(os.environ,{'KEIPER_AI_CAMPAIGNS_ENABLED':'false'}):self.tick()
        self.assertEqual(self.runs(),[])
