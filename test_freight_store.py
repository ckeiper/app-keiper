import json
import os
import unittest
from unittest.mock import Mock
from freight_store import save_report, report_history
from freight_store import confirmed_days, consolidate_report, consolidated_history


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

    def test_daily_update_requires_complete_window_and_preserves_missing(self):
        from freight_reconciliation import empty_day
        summary = dict(invalid_date_rows=0, daily={'2026-10-01': empty_day()})
        for start, end, confirmed in [('2026-10-01','2026-10-02',False),
                                      ('2026-10-02','2026-10-03',True),
                                      ('invalid','2026-10-02',True),
                                      ('2026-09-01','2026-10-02',True)]:
            query = Mock()
            with self.assertRaises(ValueError):
                consolidate_report(None,query,7,b'synthetic',summary,start,end,confirmed)
            query.assert_not_called()
        days = confirmed_days(summary,'2026-10-01','2026-10-02',True)
        self.assertEqual(len(days),2)
        self.assertEqual(days['2026-10-02']['rows'],0)
        summary['daily']['2026-10-01']['rows'] = 3
        self.assertEqual(days['2026-10-02']['rows'],0)


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
                cur.execute(sql.replace('CREATE TABLE IF NOT EXISTS',
                                       'CREATE TEMP TABLE IF NOT EXISTS'))
        try:
            # Temporary tables shadow production names even if a URL is misconfigured.
            execute(conn, 'CREATE TEMP TABLE conexoes (id INTEGER PRIMARY KEY)')
            execute(conn, 'INSERT INTO conexoes VALUES (7),(8)')
            init_freight_schema(conn, execute)
            init_freight_schema(conn, execute)
            summary = dict(rows=1, invalid_date_rows=0, period_start='2026-10-01')
            self.assertTrue(save_report(conn, query, 7, b'synthetic', summary))
            self.assertFalse(save_report(conn, query, 7, b'synthetic', summary))
            self.assertEqual(report_history(conn, query, 8), [])
            self.assertTrue(save_report(conn, query, 8, b'synthetic', summary))
            self.assertEqual(len(report_history(conn, query, 7)), 1)
            from freight_reconciliation import inspect_sales_reconciliation
            from test_freight_reconciliation import SalesReconciliationTests
            make = SalesReconciliationTests().workbook
            payload1 = make([dict(operation_date='01/10/2026'),
                             dict(operation_date='02/10/2026')])
            summary1 = inspect_sales_reconciliation('synthetic.xlsx',payload1)
            self.assertTrue(consolidate_report(conn,query,7,payload1,summary1,
                                               '2026-10-01','2026-10-02',True))
            payload2 = make([dict(operation_date='02/10/2026',gross_shipping=40,
                                 seller_shipping=35)])
            summary2 = inspect_sales_reconciliation('synthetic.xlsx',payload2)
            # A previously imported report may be consolidated exactly once.
            save_report(conn,query,7,payload2,summary2)
            self.assertTrue(consolidate_report(conn,query,7,payload2,summary2,
                                               '2026-10-02','2026-10-03',True))
            # Replaying an old report cannot roll back newer daily indicators.
            self.assertFalse(consolidate_report(conn,query,7,payload1,summary1,
                                                '2026-10-01','2026-10-02',True))
            rows = query(conn,'SELECT dia,resumo FROM frete_dias WHERE conexao_id=7 ORDER BY dia')
            self.assertEqual(len(rows),3)
            self.assertEqual([r['resumo']['seller_shipping_total'] for r in rows],
                             ['15.00','35.00','0.00'])
            self.assertEqual(query(conn,'SELECT dia FROM frete_dias WHERE conexao_id=8'),[])
            # Failure midway rolls back the report claim and all daily changes.
            execute(conn,'SAVEPOINT before_import')
            payload3 = make([dict(operation_date='01/10/2026',gross_shipping=50,
                                 seller_shipping=45)])
            summary3 = inspect_sales_reconciliation('synthetic.xlsx',payload3)
            count = 0
            def fail_query(conn,sql,params=None):
                nonlocal count
                if 'INSERT INTO frete_dias' in sql:
                    count += 1
                    if count == 2:
                        raise RuntimeError('synthetic failure')
                return query(conn,sql,params)
            with self.assertRaises(RuntimeError):
                consolidate_report(conn,fail_query,7,payload3,summary3,
                                   '2026-10-01','2026-10-02',True)
            execute(conn,'ROLLBACK TO SAVEPOINT before_import')
            self.assertEqual(query(conn,'SELECT resumo FROM frete_dias WHERE conexao_id=7 ORDER BY dia')[0]['resumo']['seller_shipping_total'],'15.00')
        finally:
            conn.rollback()
            conn.close()
