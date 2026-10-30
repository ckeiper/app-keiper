from auth_test_support import database_session
import json
import os
import time
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock, patch
from sales_metrics import SAO_PAULO
from full_monitor import full_metadata, sync_full


@unittest.skipUnless(os.getenv('KEIPER_TEST_DATABASE_URL'), 'isolated PostgreSQL not configured')
class FullIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ['DATABASE_URL'] = os.environ['KEIPER_TEST_DATABASE_URL']
        import main
        cls.m = main
        if main.scheduler.running:
            main.scheduler.shutdown(wait=False)
        main.app.config['TESTING'] = True

    def setUp(self):
        self.ids = []
        m = self.m
        with m.banco() as conn:
            for name in ('Full A','Full B'):
                cid = m.consultar(conn,"INSERT INTO conexoes(cliente,status) VALUES(%s,'ativa') RETURNING id",(name,))[0]['id']
                self.ids.append(cid)
                m.executar(conn,"INSERT INTO anuncios(conexao_id,item_id,titulo) VALUES(%s,'MLBFULL',%s)",(cid,name))
        self.client = m.app.test_client()
        with database_session(self.client) as session:
            session.update(usuario_id=1,tipo='cliente',conexao_id=self.ids[0])
        self.url = '/full/' + str(self.ids[0]) + '?item_id=MLBFULL&periodo=personalizado&inicio=2026-01-02&fim=2026-01-03'

    def tearDown(self):
        with self.m.banco() as conn:
            for table in ('full_observations','anuncios','pedidos_itens','pedidos','vendas_cobertura','erros'):
                self.m.executar(conn,'DELETE FROM '+table+' WHERE conexao_id=ANY(%s)',(self.ids,))
            self.m.executar(conn,'DELETE FROM conexoes WHERE id=ANY(%s)',(self.ids,))

    def test_permissions_anonymous_foreign_store_and_foreign_item(self):
        self.assertEqual(self.m.app.test_client().get(self.url).status_code,302)
        self.assertEqual(self.client.get('/full/'+str(self.ids[1])).status_code,403)
        self.assertEqual(self.client.get('/full?loja='+str(self.ids[1])).status_code,403)
        self.assertEqual(self.client.get('/full/'+str(self.ids[0])+'?item_id=OTHER').status_code,404)

    def test_report_no_network_no_backfill_and_store_filter_is_scoped(self):
        with patch.object(self.m.requests,'get',side_effect=AssertionError('network during report')):
            response = self.client.get(self.url)
        self.assertEqual(response.status_code,200)
        body = response.get_data(as_text=True)
        self.assertIn('Ainda não há coletas Full',body)
        self.assertIn('Full A',body)
        self.assertNotIn('Full B',body)
        self.assertIn("name='item_id'",body)
        self.assertIn('Indisponível',body)
        self.assertEqual(self.client.get('/full/'+str(self.ids[0])+'?periodo=personalizado&inicio=2025-01-01&fim=2026-01-01').status_code,200)

    def test_history_is_scoped_even_for_same_item_in_other_store(self):
        stamp = int(datetime(2026,1,2,12,tzinfo=SAO_PAULO).timestamp())
        with self.m.banco() as conn:
            for cid,state,qty,marker in ((self.ids[0],'empty',0,'own_inventory'),(self.ids[1],'available',99,'foreign_inventory')):
                self.m.executar(conn,'''INSERT INTO full_observations VALUES(%s,'MLBFULL',%s,%s,%s,'fulfillment',%s::jsonb)''',
                                (cid,stamp,state,qty,json.dumps(dict(reason=marker))))
        body = self.client.get(self.url).get_data(as_text=True)
        self.assertIn('own_inventory',body)
        self.assertNotIn('foreign_inventory',body)
        self.assertIn('Sem estoque Full',body)
        self.assertIn('Primeira confirmação',body)

    def test_collector_persists_official_variation_stock_and_rotation(self):
        now = int(time.time())
        meta = full_metadata(dict(seller_id=5,shipping={'logistic_type':'fulfillment'},
                                  variations=[dict(id=1,inventory_id='A'),dict(id=2,inventory_id='B')]),5,now)
        with self.m.banco() as conn:
            self.m.executar(conn,'UPDATE anuncios SET full_metadata_json=%s::jsonb WHERE conexao_id=%s',
                            (json.dumps(meta),self.ids[0]))
        getter = Mock(side_effect=[SimpleNamespace(status_code=200,json=lambda:dict(inventory_id='A',available_quantity=0)),
                                   SimpleNamespace(status_code=200,json=lambda:dict(inventory_id='B',available_quantity=2))])
        self.assertTrue(sync_full(self.ids[0],'test',self.m.banco,self.m.consultar,self.m.executar,getter))
        with self.m.banco() as conn:
            rows = self.m.consultar(conn,'SELECT * FROM full_observations WHERE conexao_id=%s',(self.ids[0],))
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['state'],'available')
        self.assertEqual(rows[0]['quantity'],2)
        self.assertEqual(len(rows[0]['evidence']['inventories']),2)
        self.assertNotIn('test',json.dumps(rows[0]['evidence']))

    def test_full_stage_is_called_by_normal_sync_without_changing_other_stages(self):
        m = self.m
        names = ('conta','pedidos','anuncios','full','perguntas','envios','promocoes','ads')
        mocks = {}
        with m.banco() as conn:
            m.executar(conn,'UPDATE conexoes SET user_id=5 WHERE id=%s',(self.ids[0],))
        from contextlib import ExitStack
        with ExitStack() as stack:
            for name in names:
                mocks[name] = stack.enter_context(patch.object(m,'puxar_'+name,return_value=True))
            stack.enter_context(patch.object(m,'token_atual',return_value='test'))
            stack.enter_context(patch.object(m,'gravar_historico'))
            self.assertTrue(m.executar_atualizacao(self.ids[0]))
        for mock in mocks.values():
            mock.assert_called_once()
