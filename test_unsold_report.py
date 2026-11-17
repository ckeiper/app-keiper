from datetime import date, timedelta
from io import BytesIO
import os
import unittest
from unittest.mock import patch

from flask import Flask, session
from openpyxl import load_workbook

from report_routes import PATH, register
from unsold_report import classify, sales_evidence


END = date(2026, 11, 16)
START = END - timedelta(days=6)


def listing(iid, day=START, **extra):
    return dict(item_id=iid, publicado_em=f'{day}T12:00:00-03:00' if day else None,
                full_metadata_json={'logistic_type': 'self_service'}, **extra)


def paid(iid, day):
    return dict(pedido_id=iid, conexao_id=1, criado_em=f'{day}T12:00:00-03:00', status='paid',
                moeda='BRL', total=40, unidades=1, pagamentos_json=[{'status': 'approved'}])


class UnsoldEvidenceTests(unittest.TestCase):
    def test_window_requires_coverage_only_since_publication(self):
        coverage = [str(START + timedelta(days=i)) for i in range(1, 7)]
        sold, gap = sales_evidence([], [], coverage, START, END)
        rows, insufficient = classify(
            [listing('old'), listing('recent', END), listing('unknown', None), listing('future', END + timedelta(days=1))],
            sold, gap, START, END)
        self.assertEqual([r['item_id'] for r in rows], ['recent'])
        self.assertTrue(rows[0]['recent'])
        self.assertEqual(rows[0]['logistics'], 'Flex')
        self.assertEqual(insufficient, 2)

    def test_paid_order_excludes_sold_listing_and_missing_mapping_blocks_day(self):
        coverage = [str(START + timedelta(days=i)) for i in range(7)]
        orders = [paid('p', START), paid('unmapped', END), dict(paid('c', END), status='cancelled')]
        items = [{'pedido_id': 'p', 'item_id': 'MLB1', 'quantidade': 1}]
        sold, gap = sales_evidence(orders, items, coverage, START, END)
        self.assertEqual(sold, {'MLB1'})
        self.assertEqual(gap, END)
        self.assertEqual(classify([listing('MLB1'), listing('MLB2')], sold, gap, START, END), ([], 1))
        sold, gap = sales_evidence(orders[:1] + orders[2:], items, coverage, START, END)
        self.assertIsNone(gap)
        self.assertEqual([r['item_id'] for r in classify([listing('MLB1'), listing('MLB2')],
                                                       sold, gap, START, END)[0]], ['MLB2'])


class UnsoldRouteTests(unittest.TestCase):
    def setUp(self):
        from contextlib import nullcontext
        app = Flask(__name__)
        app.secret_key = 'test'
        register(app, lambda f: f, lambda cid: session.get('conexao_id') == cid,
                 lambda: nullcontext(), lambda *_: [{'id': 1, 'cliente': 'Loja A'}],
                 lambda title, body: body, lambda title, cid, shop, section, body: body)
        self.client = app.test_client()
        with self.client.session_transaction() as sess:
            sess.update(tipo='cliente', conexao_id=1)
        self.row = dict(titulo='=HYPERLINK(1)', item_id='MLB1', sku='<item>', categoria_id='MLB123',
                        logistics='Full', preco=9.9, quantidade=0, thumbnail='javascript:alert(1)',
                        recent=True, last_sale=None, visits=0, ads=None)

    def test_store_scope_and_excel_uses_filters_and_literal_strings(self):
        with patch('report_routes.read_report', return_value=([self.row], 2, 3)) as report:
            self.assertEqual(self.client.get(PATH + '/2?formato=xlsx').status_code, 403)
            self.assertEqual(self.client.get(PATH + '?loja=2').status_code, 403)
            report.assert_not_called()
            view = self.client.get(PATH + '/1?estoque=zero')
            self.assertEqual(view.status_code, 200)
            text = view.get_data(as_text=True)
            self.assertIn('&lt;item&gt;', text)
            self.assertNotIn('javascript:', text)
            self.assertIn('dados insuficientes', text)
            self.assertEqual(self.client.get(PATH + '/1?estoque=sim&formato=xlsx').status_code, 422)
            export = self.client.get(PATH + '/1?estoque=zero&formato=xlsx')
        self.assertEqual(export.status_code, 200)
        book = load_workbook(BytesIO(export.data), read_only=True)
        self.addCleanup(book.close)
        row = list(book['Anúncios'].iter_rows())[1]
        self.assertEqual((row[0].value, row[0].data_type), ('=HYPERLINK(1)', 's'))
        self.assertEqual(row[8].value, 0)
        self.assertIsNone(row[9].value)

    def test_empty_catalog(self):
        with patch('report_routes.read_report', return_value=([], 0, 0)):
            self.assertIn('Nenhum anúncio ativo disponível', self.client.get(PATH + '/1').get_data(as_text=True))


@unittest.skipUnless(os.getenv('KEIPER_TEST_DATABASE_URL'), 'isolated PostgreSQL URL not configured')
class UnsoldDatabaseTests(unittest.TestCase):
    def test_catalog_orders_visits_and_ads_are_store_scoped(self):
        from overview_store import DAY_FUNCTION
        from unsold_report import read_report
        from psycopg2 import connect
        from psycopg2.extras import RealDictCursor

        conn = connect(os.environ['KEIPER_TEST_DATABASE_URL'])
        self.addCleanup(conn.close)
        with conn.cursor() as cursor:
            cursor.execute(DAY_FUNCTION)
            cursor.execute("""
                CREATE TEMP TABLE anuncios (conexao_id int,item_id text,titulo text,sku text,preco real,
                    quantidade int,thumbnail text,categoria_id text,publicado_em text,full_metadata_json jsonb,status text);
                CREATE TEMP TABLE pedidos (conexao_id int,pedido_id text,status text,moeda text,total real,
                    criado_em text,pagamentos_json jsonb,unidades int,vendas_dia_coleta text,vendas_verificado_em bigint);
                CREATE TEMP TABLE pedidos_itens (conexao_id int,pedido_id text,item_id text,
                    quantidade int,atualizado_em bigint);
                CREATE TEMP TABLE vendas_cobertura (conexao_id int,dia text);
                CREATE TEMP TABLE item_visits_daily (conexao_id int,item_id text,dia date,visitas int);
                CREATE TEMP TABLE ads_metricas (conexao_id int,item_id text,atualizado_em bigint);
                INSERT INTO anuncios VALUES
                    (1,'MLB1','A',NULL,19,0,NULL,'MLB123','2026-11-16T12:00:00-03:00',
                     '{"logistic_type":"fulfillment"}','active'),
                    (1,'MLB2','B',NULL,12,4,NULL,NULL,'2026-11-01T12:00:00-03:00',NULL,'active'),
                    (2,'MLB3','C',NULL,40,4,NULL,NULL,'2026-11-01T12:00:00-03:00',NULL,'active');
                INSERT INTO pedidos VALUES
                    (1,'a','paid','BRL',12,'2026-11-16T12:00:00-03:00',
                     '[{"status":"approved"}]',1,'2026-11-16',100),
                    (2,'a','paid','BRL',19,'2026-11-16T12:00:00-03:00',
                     '[{"status":"approved"}]',1,'2026-11-16',100);
                INSERT INTO pedidos_itens VALUES (1,'a','MLB2',1,100),(2,'a','MLB1',1,100);
                INSERT INTO vendas_cobertura VALUES (1,'2026-11-16');
                INSERT INTO item_visits_daily VALUES (1,'MLB1','2026-11-16',0),(2,'MLB1','2026-11-16',40);
                INSERT INTO ads_metricas VALUES (2,'MLB1',100);
            """)
        conn.commit()

        def query(connection, sql, params):
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(sql, params)
                return cursor.fetchall()

        rows, insufficient, active = read_report(lambda: conn, query, 1, START, END)
        self.assertEqual((insufficient, active), (0, 2))
        self.assertEqual([r['item_id'] for r in rows], ['MLB1'])
        self.assertEqual(rows[0]['visits'], 0)
        self.assertIsNone(rows[0]['ads'])
        self.assertEqual(rows[0]['logistics'], 'Full')
