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


if __name__ == '__main__':
    unittest.main()
