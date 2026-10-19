import json
import os
import unittest
from unittest.mock import Mock
from freight_store import save_report, report_history


class FreightStoreTests(unittest.TestCase):
    def test_scoped_fingerprint_and_no_customer_rows(self):
        summary = dict(rows=1, invalid_date_rows=0, period_start='2026-10-01')
        query = Mock(return_value=[{'id': 1}])
        self.assertTrue(save_report(None, query, 7, b'synthetic', summary))
        params = query.call_args.args[2]
        self.assertEqual(params[0], 7)
        self.assertEqual(len(params[1]), 64)
        self.assertEqual(json.loads(params[2]), summary)
        query.return_value = []
        self.assertFalse(save_report(None, query, 7, b'synthetic', summary))
        report_history(None, query, 8)
        self.assertEqual(query.call_args.args[2], (8,))

    def test_invalid_dates_prevent_persistence(self):
        query = Mock()
        with self.assertRaises(ValueError):
            save_report(None, query, 7, b'synthetic', dict(invalid_date_rows=1))
        query.assert_not_called()


@unittest.skipUnless(os.getenv('KEIPER_TEST_DATABASE_URL'), 'isolated PostgreSQL URL not configured')
class FreightStoreIntegrationTests(unittest.TestCase):
    def test_real_upsert_store_isolation_and_rollback(self):
        import psycopg2
        from psycopg2.extras import RealDictCursor
        from freight_store import init_freight_schema
        conn = psycopg2.connect(os.environ['KEIPER_TEST_DATABASE_URL'])
        def query(conn, sql, params=None):
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, params)
                return cur.fetchall()
        def execute(conn, sql):
            with conn.cursor() as cur:
                cur.execute(sql)
        try:
            # Temporary tables shadow production names even if a URL is misconfigured.
            execute(conn, 'CREATE TEMP TABLE conexoes (id INTEGER PRIMARY KEY)')
            execute(conn, 'INSERT INTO conexoes VALUES (7),(8)')
            execute(conn, '''CREATE TEMP TABLE frete_importacoes (
                id BIGSERIAL PRIMARY KEY, conexao_id INTEGER REFERENCES conexoes(id),
                arquivo_sha256 CHAR(64), importado_em TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                resumo JSONB, UNIQUE(conexao_id, arquivo_sha256))''')
            init_freight_schema(conn, execute)
            summary = dict(rows=1, invalid_date_rows=0, period_start='2026-10-01')
            self.assertTrue(save_report(conn, query, 7, b'synthetic', summary))
            self.assertFalse(save_report(conn, query, 7, b'synthetic', summary))
            self.assertEqual(report_history(conn, query, 8), [])
            self.assertTrue(save_report(conn, query, 8, b'synthetic', summary))
            self.assertEqual(len(report_history(conn, query, 7)), 1)
        finally:
            conn.rollback()
            conn.close()
