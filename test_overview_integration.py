from auth_test_support import database_session
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
        from overview_cache import invalidate_overview_cache
        invalidate_overview_cache()
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
        with database_session(self.client) as session:
            session['usuario_id']=1
            session['tipo']='admin'
        self.url='/painel/analise?periodo=personalizado&inicio=2026-10-10&fim=2026-10-11'

    def tearDown(self):
        with self.m.banco() as conn:
            for table in ('pedidos_itens','pedidos','vendas_cobertura','erros'):
                self.m.executar(conn,'DELETE FROM '+table+' WHERE conexao_id=ANY(%s)',(self.ids,))
            self.m.executar(conn,'DELETE FROM conexoes WHERE id=ANY(%s)',(self.ids,))

    def test_landing_directory_skips_sales_and_visits_queries(self):
        m = self.m
        calls = []
        original = m.consultar
        def query(conn, sql, params=None):
            calls.append(sql)
            return original(conn, sql, params)
        with patch.object(m, 'consultar', side_effect=query), \
             patch.object(m, 'load_overview', side_effect=AssertionError('sales overview on directory')), \
             patch('visits_overview.load_visits_card', side_effect=AssertionError('visits on directory')), \
             patch.object(m, 'HOME_WIDGET', '<section id="crm-below-cards-test"></section>'):
            response = self.client.get('/painel')
        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn('Suas lojas', page)
        self.assertIn('Buscar loja ou cliente', page)
        self.assertIn("href='/painel/" + str(self.ids[0]) + "'", page)
        self.assertIn("href='/crm'", page)
        self.assertLess(page.index("href='/painel/" + str(self.ids[0]) + "'"),
                        page.index('id="crm-below-cards-test"'))
        self.assertIn("href='/painel/analise'", page)
        self.assertFalse(any('FROM pedidos' in sql or 'FROM visitas' in sql for sql in calls))

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
        auth_calls = [sql for sql in calls if 'FROM usuarios WHERE id=%s' in sql]
        self.assertEqual(len(auth_calls), 1)
        self.assertEqual(len(calls), 6)  # Five report reads plus one account validation.
        view=response.get_data(as_text=True)
        self.assertIn('2 de 3 lojas na consolidação',view)
        self.assertIn('R$ 400,00',view)
        self.assertIn('Anterior: R$ 550,00',view)
        self.assertIn('Faturamento caiu 60.0%',view)
        self.assertIn('Pedidos caíram 60.0% (15 pedidos)',view)
        self.assertIn('Visitas · últimos 7 dias',view)
        self.assertIn('Indisponível',view)
        self.assertNotIn('conversão',view)
        self.assertIn('/painel/legado',view)
        self.assertIn("aria-label='Contas conectadas'", view)
        self.assertIn("href='/painel/" + str(self.ids[0]) + "'", view)

    def test_slow_overview_cancels_without_partial_totals_and_recovers(self):
        original = self.m.consultar
        def slow(conn, sql, params=None):
            if 'LEFT(criado_em, 10) BETWEEN' in sql:
                return original(conn, 'SELECT pg_sleep(1)', ())
            return original(conn, sql, params)
        with patch('overview_read.READ_SECONDS', .05), patch.object(self.m, 'consultar', side_effect=slow):
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        view = response.get_data(as_text=True)
        self.assertIn('Nenhum total parcial', view)
        self.assertIn("aria-label='Contas conectadas'", view)
        self.assertNotIn('R$ 400,00', view)
        self.assertIn('R$ 400,00', self.client.get(self.url).get_data(as_text=True))

    def test_customer_only_reads_and_sees_assigned_shop(self):
        with database_session(self.client) as session:
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
        self.assertIn("aria-label='Contas conectadas'", view)
        self.assertNotIn("href='/painel/" + str(self.ids[1]) + "'", view)
        self.assertIn('1 de 1 lojas na consolidação',view)
        auth_calls = [(sql,params) for sql,params in calls if 'FROM usuarios WHERE id=%s' in sql]
        self.assertEqual(len(auth_calls), 1)
        with database_session(self.client) as state:
            self.assertEqual(auth_calls[0][1], (state['usuario_id'],))
        report_calls = [(sql,params) for sql,params in calls if 'FROM usuarios WHERE id=%s' not in sql]
        self.assertTrue(all(params[0]==[self.ids[0]] for sql,params in report_calls[1:]))
        self.assertNotIn('/usuarios',view)

    def test_anonymous_and_unassigned_users_do_not_access_other_shops(self):
        self.assertEqual(self.m.app.test_client().get('/painel').status_code,302)
        with database_session(self.client) as session:
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

    def test_large_history_preserves_complete_totals_and_shop_isolation(self):
        from overview import load_overview
        from decimal import Decimal
        m=self.m
        with m.banco() as conn:
            # Over 20k selected orders and 30k irrelevant historical orders per shop.
            for cid in self.ids[:2]:
                m.executar(conn, '''INSERT INTO pedidos
                    (conexao_id,pedido_id,status,total,moeda,criado_em,pagamentos_json,
                     unidades,vendas_verificado_em,vendas_dia_coleta)
                    SELECT %s,'bulk-'||n,'paid',1,'BRL',
                      CASE WHEN n<=21000 THEN '2026-10-10T12:00:00-03:00'
                           ELSE '2020-01-01T12:00:00-03:00' END,
                      '[{"status":"approved"}]'::jsonb,1,1,'2026-10-10'
                    FROM generate_series(1,51000) n''',(cid,))
        counts=[]
        def query(conn,sql,params):
            rows=m.consultar(conn,sql,params)
            counts.append(len(rows))
            return rows
        shops=[dict(id=self.ids[0],cliente='A',status='ativa')]
        data=load_overview(shops,dict(periodo='personalizado',inicio='2026-10-10',fim='2026-10-11'),m.banco,query)
        self.assertEqual(data['included'],1)
        self.assertEqual(data['totals']['current']['revenue'],Decimal(21100))
        self.assertEqual(data['totals']['current']['orders'],21010)
        self.assertLessEqual(max(counts),4000)
        with m.banco() as conn:
            m.executar(conn,'ANALYZE pedidos')
            plan=m.consultar(conn, '''EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON)
                SELECT conexao_id FROM pedidos WHERE conexao_id=%s
                AND vendas_verificado_em IS NOT NULL
                AND keiper_overview_day_v1(criado_em) IS NOT NULL
                AND keiper_overview_day_v1(criado_em) BETWEEN '2026-10-08' AND '2026-10-09' ''',(self.ids[0],))
            encoded=json.dumps(plan,default=str)
            self.assertIn('idx_overview_orders_day',encoded)
            print('Overview selective PostgreSQL plan:',encoded)

    def test_sql_and_streamed_exception_summaries_match_sales_classifier(self):
        from overview import load_overview
        from sales_metrics import summarize, period
        m=self.m
        cid=self.ids[0]
        args=dict(periodo='personalizado',inicio='2026-10-10',fim='2026-10-11')
        bounds=period(args)
        cases=[
            ('2026-10-10T03:00:00Z','paid',2.35,'BRL',[{'status':'approved'}],2),
            ('2026-10-10T02:59:59.999999Z','paid',3,'BRL',[{'status':'approved'}],None),
            ('20261010T120000-0300','paid',4,'BRL',[{'status':'approved'}],1),
            ('2026-10-10T12:00:00','paid',4,'BRL',[{'status':'approved'}],1),
            ('2026-10-10T12:00:00-03:00','cancelled',10,'BRL',None,1),
            ('2026-10-10T12:00:00-03:00','paid',10,'USD',[{'status':'approved'}],1),
            ('2026-10-10T12:00:00-03:00','paid',-1,'BRL',[{'status':'approved'}],1),
            ('2026-10-10T12:00:00-03:00','paid',10,'BRL',[{'status':False}],1),
            ('2026-10-10T12:00:00-03:00','paid',10,'BRL',[{'status':[]}],1),
            ('2026-10-10T12:00:00-03:00','paid',10,'BRL',[{'status':'pending'}],1),
            ('2026-10-10T12:00:00-03:00','paid',10,'BRL',{'status':'approved'},1),
            ('not-a-date','paid',10,'BRL',[{'status':'approved'}],1),
            ('2026-02-30T12:00:00-03:00','paid',10,'BRL',[{'status':'approved'}],1),
        ]
        with m.banco() as conn:
            for i,(stamp,status,total,currency,payments,units) in enumerate(cases):
                m.executar(conn,'''INSERT INTO pedidos
                    (conexao_id,pedido_id,criado_em,status,total,moeda,pagamentos_json,
                     unidades,vendas_verificado_em,vendas_dia_coleta)
                    VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb,%s,1,NULL)''',
                    (cid,'case-'+str(i),stamp,status,total,currency,json.dumps(payments),units))
            rows=m.consultar(conn,'SELECT * FROM pedidos WHERE conexao_id=%s',(cid,))
            covered={r['dia']:r['atualizado_em'] for r in m.consultar(conn,
                'SELECT * FROM vendas_cobertura WHERE conexao_id=%s',(cid,))}
        # Force several pages, including batches ending exactly at the boundary.
        with patch('overview.EXCEPTION_BATCH_SIZE',2):
            data=load_overview([dict(id=cid,cliente='A',status='ativa')],args,m.banco,m.consultar)
        for label,a,b in [('current',bounds[0],bounds[1]),('previous',bounds[2],bounds[3])]:
            self.assertEqual(data['reports'][0][label],summarize(rows,a,b,covered))
        self.assertEqual(data['included'],0)

    def test_sql_classifier_parity_for_each_payment_and_amount_shape(self):
        from overview_store import DAILY_SQL
        from overview import daily_summary
        from sales_metrics import summarize, created_day
        from datetime import date
        m=self.m
        cid=self.ids[2]
        day=date(2026,10,10)
        covered={day.isoformat():int(time.time())}
        shapes=[None,[],{},[None],[1],[{}],[{'status':False}],[{'status':0}],
                [{'status':[]}],[{'status':{}}],[{'status':''}],[{'status':'pending'}],
                [{'status':'approved'}],[{'status':'approved'},{'status':None}]]
        with m.banco() as conn:
            for i,payments in enumerate(shapes):
                with self.subTest(payments=payments):
                    m.executar(conn,'DELETE FROM pedidos WHERE conexao_id=%s',(cid,))
                    m.executar(conn,'''INSERT INTO pedidos
                        (conexao_id,pedido_id,status,total,moeda,criado_em,pagamentos_json,
                         unidades,vendas_verificado_em) VALUES(%s,%s,'paid',2.35,'BRL',
                         '2026-10-10T12:00:00-03:00',%s::jsonb,2,1)''',(cid,str(i),json.dumps(payments)))
                    raw=m.consultar(conn,'SELECT * FROM pedidos WHERE conexao_id=%s',(cid,))
                    facts=m.consultar(conn,DAILY_SQL,([cid],day,day))
                    self.assertEqual(daily_summary(facts,day,day,covered),summarize(raw,day,day,covered))
            for total in ('NaN','Infinity','-Infinity','-1','0','21.251'):
                m.executar(conn,"UPDATE pedidos SET total=%s,pagamentos_json='[{\"status\":\"approved\"}]'::jsonb WHERE conexao_id=%s",(total,cid))
                raw=m.consultar(conn,'SELECT * FROM pedidos WHERE conexao_id=%s',(cid,))
                self.assertEqual(daily_summary(m.consultar(conn,DAILY_SQL,([cid],day,day)),day,day,covered),summarize(raw,day,day,covered))
            for stamp in ('2026-10-10T03:00:00Z','2026-10-10T02:59:59.999999Z',
                          '2026-10-10T00:00:00+23:59','2026-10-10T23:59:59-23:59',
                          '2026-02-30T00:00:00Z','0001-01-01T00:00:00Z',
                          '9999-12-31T23:59:59-23:59'):
                self.assertEqual(m.consultar(conn,'SELECT keiper_overview_day_v1(%s) AS day',(stamp,))[0]['day'],created_day(stamp))

    def test_error_history_is_bounded_without_losing_old_unresolved_or_null_errors(self):
        from overview_store import LATEST_ERRORS_SQL
        from overview import load_overview
        m=self.m
        cid=self.ids[0]
        now=int(time.time())
        # Shadow the live per-category table with a large historical fixture.
        # Production's PK already bounds it to one row/category; no migration of it.
        with m.banco() as conn:
            m.executar(conn,'CREATE TEMP TABLE erros (conexao_id integer,categoria text,quando bigint) ON COMMIT DROP')
            m.executar(conn,'''INSERT INTO erros SELECT %s,'pedidos',%s-n
                               FROM generate_series(1,30000) n''',(cid,now-10000))
            m.executar(conn,"INSERT INTO erros VALUES(%s,'token',%s),(%s,'ads',%s)",
                       (cid,now-100,self.ids[1],now+1000))
            m.executar(conn,'''CREATE INDEX ON erros(conexao_id,quando DESC NULLS FIRST)
                WHERE categoria IN ('pedidos','atualizacao','refresh','token')''')
            errors=m.consultar(conn,LATEST_ERRORS_SQL,(self.ids,))
            self.assertEqual(errors,[dict(conexao_id=cid,quando=now-100)])
            m.executar(conn,"INSERT INTO erros VALUES(%s,'refresh',NULL)",(cid,))
            self.assertEqual(m.consultar(conn,LATEST_ERRORS_SQL,([cid],)),[dict(conexao_id=cid,quando=None)])
        # A partial success cannot clear even an old unresolved error.
        with m.banco() as conn:
            m.executar(conn,"INSERT INTO erros(conexao_id,categoria,mensagem,quando) VALUES(%s,'pedidos','old unresolved',%s)",(cid,now-200))
            m.executar(conn,"UPDATE vendas_cobertura SET atualizado_em=%s WHERE conexao_id=%s AND dia='2026-10-08'",(now-300,cid))
        args=dict(periodo='personalizado',inicio='2026-10-10',fim='2026-10-11')
        shops=[dict(id=cid,cliente='A',status='ativa')]
        data=load_overview(shops,args,m.banco,m.consultar)
        self.assertEqual(data['included'],0)
        self.assertIn('Erro de sincronização sem resolução confirmada',data['reports'][0]['reasons'])
        with m.banco() as conn:
            m.executar(conn,'UPDATE vendas_cobertura SET atualizado_em=%s WHERE conexao_id=%s',(now,cid))
        self.assertEqual(load_overview(shops,args,m.banco,m.consultar)['included'],1)

    def test_aggregation_coverage_errors_and_exception_pages_share_snapshot(self):
        from overview import load_overview
        m=self.m
        cid=self.ids[0]
        updated=False
        def query(conn,sql,params):
            nonlocal updated
            rows=m.consultar(conn,sql,params)
            if not updated:
                updated=True
                with m.banco() as writer:
                    m.executar(writer,"INSERT INTO erros(conexao_id,categoria,mensagem,quando) VALUES(%s,'pedidos','concurrent',%s)",(cid,int(time.time())+10))
                    m.executar(writer,'''INSERT INTO pedidos
                        (conexao_id,pedido_id,status,total,moeda,criado_em,vendas_verificado_em)
                        VALUES(%s,'concurrent','paid',100,'BRL','unknown',1)''',(cid,))
            return rows
        shops=[dict(id=cid,cliente='A',status='ativa')]
        args=dict(periodo='personalizado',inicio='2026-10-10',fim='2026-10-11')
        first=load_overview(shops,args,m.banco,query)
        self.assertEqual(first['included'],1)
        self.assertEqual(first['reports'][0]['current']['unallocated_dates'],0)
        second=load_overview(shops,args,m.banco,m.consultar)
        self.assertEqual(second['included'],0)
        self.assertEqual(second['reports'][0]['current']['unallocated_dates'],1)

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
        with database_session(self.client) as state:
            csrf = state['_csrf']
        renamed=self.client.post(f'/renomear/{cid}',headers={'X-CSRF-Token':csrf},data={'cliente':'Loja renomeada <teste>'})
        self.assertEqual(renamed.status_code,200)
        self.assertTrue(renamed.get_json()['ok'])
        view=self.client.get(self.url).get_data(as_text=True)
        self.assertIn(f"id='nome-{cid}'>Loja renomeada &lt;teste&gt;",view)
        with database_session(self.client) as session:
            session['tipo']='cliente'
            session['conexao_id']=cid
        self.assertEqual(self.client.post(f'/renomear/{self.ids[1]}',headers={'X-CSRF-Token':csrf},data={'cliente':'Negado'}).status_code,403)

    def test_legacy_dashboard_and_invalid_filters_remain_accessible(self):
        with patch.object(self.m,'enfileirar_atualizacao',return_value=True):
            legacy=self.client.get('/painel/legado')
            self.assertEqual(legacy.status_code,200)
            self.assertIn('/painel/legado?r=1',legacy.get_data(as_text=True))
        response=self.client.get('/painel/analise?periodo=invalid')
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
                from overview_cache import invalidate_overview_cache
                invalidate_overview_cache()
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
                sales = self.client.get(self.url.replace('/painel/analise?', f'/vendas/{cid}?'))
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
                with database_session(self.client) as session:
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
