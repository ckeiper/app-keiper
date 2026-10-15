"""Opt-in checks: KEIPER_TEST_DATABASE_URL must point at a disposable database."""
import os
import unittest


@unittest.skipUnless(os.getenv('KEIPER_TEST_DATABASE_URL'), 'isolated PostgreSQL URL not configured')
class DatabaseIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ['DATABASE_URL'] = os.environ['KEIPER_TEST_DATABASE_URL']
        import main
        cls.app_module = main
        if main.scheduler.running:
            main.scheduler.shutdown(wait=False)
        main.iniciar_banco()  # Second initialization verifies additive/idempotent DDL.

    def setUp(self):
        app = self.app_module
        with app.banco() as conn:
            self.cid = app.consultar(conn, "INSERT INTO conexoes (cliente) VALUES (%s) RETURNING id",
                                     ('Teste Vendas Etapa 1',))[0]['id']

    def tearDown(self):
        app = self.app_module
        with app.banco() as conn:
            for table in ('vendas_cobertura', 'pedidos_itens', 'pedidos'):
                app.executar(conn, 'DELETE FROM ' + table + ' WHERE conexao_id=%s', (self.cid,))
            app.executar(conn, 'DELETE FROM conexoes WHERE id=%s', (self.cid,))

    def test_sync_real_sql_and_authenticated_flask_view(self):
        from sales_metrics import reporting_today
        from sales_sync import sync_orders
        app = self.app_module
        today = reporting_today()
        def api(token, path, params=None):
            day = params['order.date_created.from'][:10]
            orders = [] if day != today.isoformat() else [{
                'id': 9999, 'date_created': day + 'T12:00:00-03:00',
                'date_closed': day + 'T13:00:00-03:00', 'status': 'paid',
                'currency_id': 'BRL', 'total_amount': 120,
                'payments': [{'id': 1, 'status': 'approved'}],
                'order_items': [{'item': {'id': 'MLBTEST'}, 'quantity': 3, 'unit_price': 40}]}]
            return {'results': orders, 'paging': {'total': len(orders)}}, None
        for _ in range(2):  # Upserts must not duplicate orders or items.
            self.assertTrue(sync_orders(self.cid, 'fake', 1, app.banco, app.consultar,
                                        app.executar, api, app.registrar_erro))
        with app.banco() as conn:
            orders = app.consultar(conn, 'SELECT * FROM pedidos WHERE conexao_id=%s', (self.cid,))
            items = app.consultar(conn, 'SELECT * FROM pedidos_itens WHERE conexao_id=%s', (self.cid,))
        self.assertEqual(len(orders), 1)
        self.assertEqual(len(items), 1)
        self.assertEqual(orders[0]['unidades'], 3)
        self.assertEqual(orders[0]['pagamentos_json'][0]['status'], 'approved')
        self.assertEqual(orders[0]['vendas_dia_coleta'], today.isoformat())
        app.app.config['TESTING'] = True
        client = app.app.test_client()
        self.assertEqual(client.get('/vendas/' + str(self.cid)).status_code, 302)
        with client.session_transaction() as session:
            session['usuario_id'] = 1
            session['tipo'] = 'cliente'
            session['conexao_id'] = self.cid + 1
        denied = client.get('/vendas/' + str(self.cid)).get_data(as_text=True)
        self.assertIn('Acesso restrito', denied)
        self.assertNotIn('Indicadores de vendas pagas', denied)
        with client.session_transaction() as session:
            session['usuario_id'] = 1
            session['tipo'] = 'admin'
        response = client.get('/vendas/' + str(self.cid) + '?periodo=7')
        self.assertEqual(response.status_code, 200)
        self.assertIn('R$ 120,00', response.get_data(as_text=True))
        self.assertIn('Ticket médio por pedido', response.get_data(as_text=True))
        self.assertEqual(client.get('/exportar_vendas/' + str(self.cid)).status_code, 200)

    def seed_date_regression(self, broken_date, origin=None):
        app = self.app_module
        with app.banco() as conn:
            for oid, created, value, collected in (
                    ('current', '2026-10-10T12:00:00-03:00', 120, '2026-10-10'),
                    ('previous', '2026-10-08T12:00:00-03:00', 80, '2026-10-08'),
                    ('broken', broken_date, 900, origin)):
                app.executar(conn, """INSERT INTO pedidos
                    (conexao_id, pedido_id, status, total, moeda, criado_em, unidades,
                     pagamentos_json, vendas_verificado_em, vendas_dia_coleta, fechado_em)
                    VALUES (%s,%s,'paid',%s,'BRL',%s,2,
                            '[{"status":"approved"}]'::jsonb,1,%s,'2026-10-10T12:00:00-03:00')""",
                    (self.cid, oid, value, created, collected))
            for i in range(1, 12):
                app.executar(conn, "INSERT INTO vendas_cobertura VALUES (%s,%s,1)",
                             (self.cid, f'2026-10-{i:02}'))

    def report(self, start='2026-10-10', end='2026-10-11'):
        from sales_view import render_sales
        app = self.app_module
        return render_sales(self.cid, {'periodo':'personalizado', 'inicio':start, 'fim':end},
                            app.banco, app.consultar)

    def test_unlocated_legacy_and_malformed_rows_keep_verified_totals_visible(self):
        self.seed_date_regression(None)
        app = self.app_module
        with app.banco() as conn:
            # The SQL query must not silently drop arbitrary malformed strings.
            app.executar(conn, """INSERT INTO pedidos
                (conexao_id, pedido_id, status, criado_em, vendas_verificado_em)
                VALUES (%s,'malformed','paid','not-a-date',1),
                       (%s,'legacy','paid',NULL,NULL)""", (self.cid, self.cid))
        view = self.report()
        self.assertIn('R$ 120,00', view)
        self.assertIn('Anterior: R$ 80,00', view)
        self.assertIn('2 pedido(s) sem data de criação utilizável', view)
        self.assertIn('1 pedido(s) antigos ainda não revalidados', view)
        self.assertNotIn('Histórico incompleto', view)
        self.assertNotIn('Período atual: 1 pedido(s)', view)

    def test_old_invalid_rows_do_not_poison_custom_intervals(self):
        self.seed_date_regression('2020-01-01Tbroken')
        for start, end in (('2026-10-10', '2026-10-11'), ('2026-10-10', '2026-10-10'),
                           ('2026-10-08', '2026-10-11')):
            with self.subTest(start=start, end=end):
                view = self.report(start, end)
                self.assertNotIn('com campos não verificáveis', view)
                self.assertNotIn('Histórico incompleto', view)
        self.assertIn('R$ 200,00', self.report('2026-10-08', '2026-10-11'))

    def test_origin_scopes_missing_date_and_coverage_remains_independent(self):
        self.seed_date_regression(None, '2026-10-09')
        view = self.report()
        self.assertIn('R$ 120,00', view)
        self.assertIn('Anterior: Indisponível', view)
        self.assertIn('Período anterior: 1 pedido(s)', view)
        self.assertNotIn('Período atual: 1 pedido(s)', view)
        self.assertIn('Período atual: 1 pedido(s)', self.report('2026-10-08', '2026-10-09'))
        app = self.app_module
        with app.banco() as conn:
            app.executar(conn, "DELETE FROM vendas_cobertura WHERE conexao_id=%s AND dia='2026-10-11'", (self.cid,))
        self.assertIn('Histórico incompleto', self.report())

    def test_sync_retains_origin_when_detail_cannot_repair_date(self):
        from sales_metrics import reporting_today, summarize
        from sales_sync import sync_orders
        app = self.app_module
        today = reporting_today()
        order = {'id': 77, 'date_created': 'not-a-date', 'status': 'paid',
                 'currency_id': 'BRL', 'total_amount': 120,
                 'payments': [{'status': 'approved'}],
                 'order_items': [{'item': {'id': 'MLBTEST'}, 'quantity': 3, 'unit_price': 40}]}
        def api(token, path, params=None):
            if path == '/orders/77':
                return order, None
            results = [order] if params['order.date_created.from'][:10] == today.isoformat() else []
            return {'results': results, 'paging': {'total':len(results)}}, None
        self.assertTrue(sync_orders(self.cid, 'fake', 1, app.banco, app.consultar,
                                    app.executar, api, app.registrar_erro))
        with app.banco() as conn:
            orders = app.consultar(conn, 'SELECT * FROM pedidos WHERE conexao_id=%s', (self.cid,))
            coverage = app.consultar(conn, 'SELECT dia FROM vendas_cobertura WHERE conexao_id=%s', (self.cid,))
        self.assertEqual(orders[0]['vendas_dia_coleta'], today.isoformat())
        result = summarize(orders, today, today, {r['dia'] for r in coverage})
        self.assertTrue(result['complete'])
        self.assertIsNone(result['revenue'])
        self.assertEqual(result['invalid_dates'], 1)
        self.assertEqual(result['unallocated_dates'], 0)


if __name__ == '__main__':
    unittest.main()
