"""Financeiro request and PostgreSQL checks against an isolated test schema."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import date
import os
import re
import unittest
from unittest.mock import patch
from uuid import uuid4

from flask import Flask
import psycopg2
from psycopg2.extras import RealDictCursor

from financeiro_routes import register_financeiro
from financeiro_service import import_integrated_clients, sync_finance, consolidate_account
from financeiro_store import init_finance_schema
from home_sidebar import render_home_sidebar
from web_security import install_security


def execute(conn, sql, params=()):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, params)
        return cur.fetchall() if cur.description else None


def app_for(bank):
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY='test-only')
    install_security(app)
    register_financeiro(app, bank, execute, lambda title, body: '<html><head></head><body>' + body + '</body></html>')
    return app


class AccessTests(unittest.TestCase):
    def test_login_admin_sidebar_and_csrf(self):
        def no_bank():
            self.fail('Blocked request reached the database')

        client = app_for(no_bank).test_client()
        self.assertEqual(client.get('/financeiro').location, '/login')
        with client.session_transaction() as session:
            session.update(usuario_id=7, tipo='cliente', _csrf='csrf-test')
        self.assertEqual(client.get('/financeiro').status_code, 403)
        self.assertEqual(client.post('/financeiro/clientes', data={'_csrf': 'csrf-test'}).status_code, 403)
        with client.session_transaction() as session:
            session['tipo'] = 'admin'
        self.assertEqual(client.post('/financeiro/pagamentos').status_code, 400)
        self.assertNotIn('/financeiro', render_home_sidebar(admin=False))
        self.assertIn("href='/financeiro' aria-current='page'", render_home_sidebar(admin=True, active='financeiro'))


@unittest.skipUnless(os.getenv('KEIPER_TEST_DATABASE_URL'), 'isolated PostgreSQL URL not configured')
class FinanceDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.url = os.environ['KEIPER_TEST_DATABASE_URL']
        self.schema = 'fin_test_' + uuid4().hex
        with closing(psycopg2.connect(self.url)) as conn, conn:
            execute(conn, 'CREATE SCHEMA ' + self.schema)
        self.addCleanup(self.drop_schema)
        with closing(self.bank()) as conn, conn:
            execute(conn, 'CREATE TABLE conexoes (id SERIAL PRIMARY KEY, cliente TEXT NOT NULL)')
            execute(conn, "INSERT INTO conexoes(cliente) VALUES ('Mesma loja'),('Mesma loja')")
            for _ in range(2):
                init_finance_schema(conn, execute)
        self.client = app_for(self.bank).test_client()
        with self.client.session_transaction() as session:
            session.update(usuario_id=7, tipo='admin', _csrf='csrf-test')

    def bank(self):
        return psycopg2.connect(self.url, options='-c search_path=' + self.schema)

    def drop_schema(self):
        with closing(psycopg2.connect(self.url)) as conn, conn:
            execute(conn, 'DROP SCHEMA ' + self.schema + ' CASCADE')

    def post(self, action, **data):
        with self.client.session_transaction() as session:
            data['_csrf'] = session['_csrf']
        return self.client.post('/financeiro/' + action, data=data)

    def test_concurrent_import_and_consolidation(self):
        def import_once(_):
            with closing(self.bank()) as conn, conn:
                return import_integrated_clients(conn)

        with ThreadPoolExecutor(2) as pool:
            self.assertEqual(sorted(pool.map(import_once, range(2))), [0, 2])
        with closing(self.bank()) as conn, conn:
            links = execute(conn, 'SELECT * FROM financeiro_vinculos ORDER BY conexao_id')
            self.assertNotEqual(links[0]['cliente_id'], links[1]['cliente_id'])
            consolidate_account(conn, links[0]['cliente_id'], links[1]['conexao_id'])
            self.assertEqual(len(execute(conn, 'SELECT * FROM financeiro_clientes')), 1)
            self.assertEqual(import_integrated_clients(conn), 0)

    @patch('financeiro_service.today_br', return_value=date(2026, 11, 6))
    @patch('financeiro_routes.today_br', return_value=date(2026, 11, 6))
    def test_receivables_and_payments(self, _routes_day, _service_day):
        self.assertEqual(self.post('clientes', nome='Cliente <avulso>').status_code, 303)
        with closing(self.bank()) as conn, conn:
            cid = execute(conn, 'SELECT id FROM financeiro_clientes')[0]['id']
        self.assertEqual(self.post('contratos', cliente_id=cid, valor='1500,00', inicio='2026-10-20').status_code, 303)
        with closing(self.bank()) as conn, conn:
            sync_finance(conn)
            rows = execute(conn, 'SELECT * FROM financeiro_mensalidades ORDER BY competencia')
            self.assertEqual([r['vencimento'] for r in rows], [date(2026, 10, 5), date(2026, 11, 5)])
        page = self.client.get('/financeiro').get_data(as_text=True)
        self.assertIn('Cliente &lt;avulso&gt;', page)
        self.assertIn('R$ 1.500,00', page)
        key = re.search(r'name="chave" value="([a-f0-9-]+)"', page)[1]
        data = dict(mensalidade_id=rows[1]['id'], valor='500', data_pagamento='2026-11-06', meio='pix', chave=key)
        self.assertEqual(self.post('pagamentos', **data).status_code, 303)
        self.assertEqual(self.post('pagamentos', **data).status_code, 303)
        self.assertEqual(self.post('pagamentos', **dict(data, valor='1000.01', chave=str(uuid4()))).status_code, 400)
        page = self.client.get('/financeiro').get_data(as_text=True)
        self.assertIn('parcial atrasado', page)
        self.assertIn('R$ 1.000,00', page)
        self.assertEqual(self.post('pagamentos', **dict(data, valor='1000', meio='transferencia', chave=str(uuid4()))).status_code, 303)
        with closing(self.bank()) as conn, conn:
            history = execute(conn, 'SELECT * FROM financeiro_pagamentos ORDER BY id')
            self.assertEqual([(p['valor_centavos'], p['meio'], p['registrado_por']) for p in history],
                             [(50000, 'pix', 7), (100000, 'transferencia', 7)])
