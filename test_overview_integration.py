"""Real PostgreSQL/Flask checks, on the same disposable database as sales CI."""
import os
import json
import time
import unittest
from unittest.mock import patch


@unittest.skipUnless(os.getenv('KEIPER_TEST_DATABASE_URL'), 'isolated PostgreSQL URL not configured')
class OverviewIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ['DATABASE_URL']=os.environ['KEIPER_TEST_DATABASE_URL']
        import main
        cls.m=main
        if main.scheduler.running:
            main.scheduler.shutdown(wait=False)
        main.iniciar_banco()
        main.app.config['TESTING']=True

    def setUp(self):
        m=self.m
        self.ids=[]
        with m.banco() as conn:
            for name in ('Overview A','Overview B','Overview Incompleta'):
                cid=m.consultar(conn,"INSERT INTO conexoes(cliente,status) VALUES(%s,'ativa') RETURNING id",(name,))[0]['id']
                self.ids.append(cid)
            for cid,ncur,nprev in ((self.ids[0],10,25),(self.ids[1],30,30)):
                for tag,day,n in [('c','2026-10-10',ncur),('p','2026-10-08',nprev)]:
                    for i in range(n):
                        m.executar(conn,"""INSERT INTO pedidos
                            (conexao_id,pedido_id,status,total,moeda,criado_em,pagamentos_json,
                             unidades,vendas_verificado_em,vendas_dia_coleta)
                            VALUES(%s,%s,'paid',10,'BRL',%s,'[{"status":"approved"}]'::jsonb,1,1,%s)""",
                            (cid,f'{tag}{i}',day+'T12:00:00-03:00',day))
                for d in range(8,12):
                    m.executar(conn,'INSERT INTO vendas_cobertura VALUES(%s,%s,%s)',
                               (cid,f'2026-10-{d:02}',int(time.time())))
        self.client=m.app.test_client()
        with self.client.session_transaction() as session:
            session['usuario_id']=1
            session['tipo']='admin'
        self.url='/painel?periodo=personalizado&inicio=2026-10-10&fim=2026-10-11'

    def tearDown(self):
        with self.m.banco() as conn:
            for table in ('pedidos_itens','pedidos','vendas_cobertura','erros'):
                self.m.executar(conn,'DELETE FROM '+table+' WHERE conexao_id=ANY(%s)',(self.ids,))
            self.m.executar(conn,'DELETE FROM conexoes WHERE id=ANY(%s)',(self.ids,))

    def test_admin_metrics_alerts_and_constant_number_of_queries(self):
        calls=[]
        original=self.m.consultar
        def query(conn,sql,params=None):
            calls.append(sql)
            return original(conn,sql,params)
        with patch.object(self.m,'consultar',side_effect=query),patch.object(self.m,'enfileirar_atualizacao') as enqueue:
            response=self.client.get(self.url)
            enqueue.assert_not_called()
        self.assertEqual(response.status_code,200)
        self.assertEqual(len(calls),4)
        view=response.get_data(as_text=True)
        self.assertIn('2 de 3 lojas na consolidação',view)
        self.assertIn('R$ 400,00',view)
        self.assertIn('Anterior: R$ 550,00',view)
        self.assertIn('Faturamento caiu 60.0%',view)
        self.assertIn('Pedidos caíram 60.0% (15 pedidos)',view)
        self.assertNotIn('Visitas',view)
        self.assertNotIn('conversão',view)
        self.assertIn('/painel/legado',view)

    def test_customer_only_reads_and_sees_assigned_shop(self):
        with self.client.session_transaction() as session:
            session['tipo']='cliente'
            session['conexao_id']=self.ids[0]
        calls=[]
        original=self.m.consultar
        def query(conn,sql,params=None):
            calls.append((sql,params))
            return original(conn,sql,params)
        with patch.object(self.m,'consultar',side_effect=query):
            view=self.client.get(self.url).get_data(as_text=True)
        self.assertIn('Overview A',view)
        self.assertNotIn('Overview B',view)
        self.assertNotIn('Overview Incompleta',view)
        self.assertIn('1 de 1 lojas na consolidação',view)
        self.assertTrue(all(params[0]==[self.ids[0]] for sql,params in calls[1:]))
        self.assertNotIn('/usuarios',view)

    def test_anonymous_and_unassigned_users_do_not_access_other_shops(self):
        self.assertEqual(self.m.app.test_client().get('/painel').status_code,302)
        with self.client.session_transaction() as session:
            session['tipo']='cliente'
            session['conexao_id']=None
        view=self.client.get(self.url).get_data(as_text=True)
        self.assertIn('Nenhuma loja disponível',view)
        self.assertNotIn('Overview A',view)

    def test_coverage_gap_and_sync_error_suppress_drops(self):
        with self.m.banco() as conn:
            self.m.executar(conn,"DELETE FROM vendas_cobertura WHERE conexao_id=%s AND dia='2026-10-08'",(self.ids[0],))
            self.m.executar(conn,"""INSERT INTO erros(conexao_id,categoria,mensagem,quando)
                VALUES(%s,'pedidos','simulated',%s)""",(self.ids[1],int(time.time())+1))
        view=self.client.get(self.url).get_data(as_text=True)
        self.assertIn('0 de 3 lojas na consolidação',view)
        self.assertIn('Cobertura incompleta',view)
        self.assertIn('Erro de sincronização',view)
        self.assertNotIn('Faturamento caiu',view)
        self.assertNotIn('Pedidos caíram',view)

    def test_postgresql_row_cap_does_not_become_partial_consolidation(self):
        with patch('overview.MAX_ORDERS',2):
            view=self.client.get(self.url).get_data(as_text=True)
        self.assertIn('0 de 3 lojas na consolidação',view)
        self.assertIn('Limite de leitura atingido',view)
        self.assertNotIn('Faturamento caiu',view)
        self.assertNotIn('R$ 20,00',view)

    def test_fresh_external_day_does_not_unblock_stale_selection(self):
        from overview import HISTORICAL_STALE_SECONDS
        with self.m.banco() as conn:
            self.m.executar(conn,'UPDATE vendas_cobertura SET atualizado_em=%s WHERE conexao_id=ANY(%s)',
                            (int(time.time())-HISTORICAL_STALE_SECONDS-1,self.ids[:2]))
            for cid in self.ids[:2]:
                self.m.executar(conn,"INSERT INTO vendas_cobertura VALUES(%s,'2026-10-15',%s)",
                                (cid,int(time.time())))
        view=self.client.get(self.url).get_data(as_text=True)
        self.assertIn('0 de 3 lojas na consolidação',view)
        self.assertIn('Sincronização dos períodos desatualizada',view)
        self.assertNotIn('Faturamento caiu',view)
        self.assertNotIn('Pedidos caíram',view)

    def test_rename_dom_contract_persistence_and_permissions(self):
        cid=self.ids[0]
        view=self.client.get(self.url).get_data(as_text=True)
        self.assertIn(f"id='nome-{cid}'",view)
        self.assertIn(f'editarNome({cid})',view)
        self.assertIn("document.getElementById('nome-' + id)",view)
        renamed=self.client.post(f'/renomear/{cid}',data={'cliente':'Loja renomeada <teste>'})
        self.assertEqual(renamed.status_code,200)
        self.assertTrue(renamed.get_json()['ok'])
        view=self.client.get(self.url).get_data(as_text=True)
        self.assertIn(f"id='nome-{cid}'>Loja renomeada &lt;teste&gt;",view)
        with self.client.session_transaction() as session:
            session['tipo']='cliente'
            session['conexao_id']=cid
        self.assertEqual(self.client.post(f'/renomear/{self.ids[1]}',data={'cliente':'Negado'}).status_code,403)

    def test_legacy_dashboard_and_invalid_filters_remain_accessible(self):
        with patch.object(self.m,'enfileirar_atualizacao',return_value=True):
            legacy=self.client.get('/painel/legado')
            self.assertEqual(legacy.status_code,200)
            self.assertIn('/painel/legado?r=1',legacy.get_data(as_text=True))
        response=self.client.get('/painel?periodo=invalid')
        self.assertEqual(response.status_code,200)
        self.assertIn('Selecione 7, 15, 30, 60 ou 90 dias',response.get_data(as_text=True))

    def test_fifteen_percent_alert_boundary_through_home_dashboard(self):
        cid = self.ids[0]
        # Previous: 25 x R$10 = R$250; current: 10 x R$21.25 = R$212.50.
        for unit_total, expected in [('21.25', True), ('21.251', False)]:
            with self.subTest(unit_total=unit_total):
                with self.m.banco() as conn:
                    self.m.executar(conn, "UPDATE pedidos SET total=%s WHERE conexao_id=%s AND pedido_id LIKE %s",
                                    (unit_total, cid, 'c%'))
                with patch.object(self.m.requests, 'get', side_effect=AssertionError('unexpected API read')), \
                     patch.object(self.m, 'enfileirar_atualizacao') as enqueue:
                    response = self.client.get(self.url)
                    enqueue.assert_not_called()
                self.assertEqual(response.status_code, 200)
                view = response.get_data(as_text=True)
                self.assertEqual('Faturamento caiu 15.0%' in view, expected)
                self.assertIn('pelo menos 15%', view)

    def test_home_sales_listings_and_promotions_coexist_after_main_update(self):
        from listing_details import normalize_promotions, registered_weights
        m, cid = self.m, self.ids[0]
        weights = registered_weights({'attributes': [
            {'id': 'PACKAGE_WEIGHT', 'value_name': '1000 g'},
            {'id': 'SELLER_PACKAGE_WEIGHT', 'value_name': '1250 g'}]})
        snapshot = {'checked_at': int(time.time()), 'error': None,
                    'promotions': normalize_promotions([{'id': 'MERGE-PROMO', 'type': 'SELLER_CAMPAIGN',
                        'status': 'started', 'price': 80, 'original_price': 100}]),
                    'sale_price': {'checked_at': int(time.time()), 'error': None,
                        'data': {'amount': 80, 'regular_amount': 100, 'currency_id': 'BRL',
                                 'metadata': {'promotion_id': 'MERGE-OFFER'}}}}
        with m.banco() as conn:
            m.executar(conn, '''INSERT INTO anuncios
                (conexao_id,item_id,titulo,preco,status,peso,pesos_json,promocoes_json,quantidade)
                VALUES (%s,%s,%s,100,'active',1.25,%s,%s,5)''',
                (cid, 'MLBMERGE', 'Anúncio integrado', json.dumps(weights), json.dumps(snapshot)))
            m.executar(conn, '''INSERT INTO promocoes (conexao_id,promocao_id,tipo,nome,status)
                VALUES (%s,'MERGE-PROMO','SELLER_CAMPAIGN','Campanha integrada','active')''', (cid,))
            m.executar(conn, '''INSERT INTO promocoes_itens
                (conexao_id,item_id,promocao_id,preco_promocional)
                VALUES (%s,'MLBMERGE','MERGE-PROMO',80)''', (cid,))
        try:
            with patch.object(m.requests, 'get', side_effect=AssertionError('unexpected API read')), \
                 patch.object(m.requests, 'post', side_effect=AssertionError('unexpected API write')), \
                 patch.object(m, 'enfileirar_atualizacao', return_value=True):
                home = self.client.get('/')
                self.assertEqual(home.status_code, 302)
                self.assertEqual(home.headers['Location'], '/painel')
                initial = self.client.get(self.url)
                self.assertEqual(initial.status_code, 200)
                self.assertIn('Visão Geral 2.0', initial.get_data(as_text=True))
                self.assertEqual(self.client.get('/painel/legado').status_code, 200)
                sales = self.client.get(self.url.replace('/painel?', f'/vendas/{cid}?'))
                self.assertEqual(sales.status_code, 200)
                self.assertIn('R$ 100,00', sales.get_data(as_text=True))
                listing = self.client.get(f'/anuncios/{cid}')
                self.assertEqual(listing.status_code, 200)
                listing_html = listing.get_data(as_text=True)
                for value in ('Peso cadastrado', 'Peso logístico', 'PACKAGE_WEIGHT',
                              'SELLER_PACKAGE_WEIGHT', 'Por R$ 80,00', 'Anúncio: 1 kg', 'Anúncio: 1.25 kg'):
                    self.assertIn(value, listing_html)
                self.assertNotIn('<details open', listing_html)
                campaigns = self.client.get(f'/promocoes/{cid}')
                self.assertEqual(campaigns.status_code, 200)
                self.assertIn('Campanha integrada', campaigns.get_data(as_text=True))
                for path in (self.url, f'/vendas/{cid}', f'/anuncios/{cid}', f'/promocoes/{cid}'):
                    self.assertEqual(m.app.test_client().get(path).status_code, 302)
                with self.client.session_transaction() as session:
                    session.update(tipo='cliente', conexao_id=self.ids[1])
                for path in (f'/vendas/{cid}', f'/anuncios/{cid}', f'/promocoes/{cid}'):
                    denied = self.client.get(path).get_data(as_text=True)
                    self.assertIn('Acesso restrito', denied)
                    self.assertNotIn('Anúncio integrado', denied)
        finally:
            with m.banco() as conn:
                for table in ('promocoes_itens', 'promocoes', 'anuncios'):
                    m.executar(conn, 'DELETE FROM ' + table + ' WHERE conexao_id=%s', (cid,))


if __name__=='__main__':
    unittest.main()
