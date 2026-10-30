import os
import unittest
from ads_official_metrics import init_schema, save_day, value


class OfficialSalesValuesTests(unittest.TestCase):
    def test_unknown_invalid_and_negative_counts_never_become_sales(self):
        for raw in (None, '', 'bad', -1, 1.5, float('nan'), float('inf'), True):
            self.assertIsNone(value({'count':raw},'count',integer=True))
        self.assertEqual(value({'count':0},'count',integer=True),0)
        self.assertEqual(value({'count':'7'},'count',integer=True),7)


@unittest.skipUnless(os.getenv('KEIPER_TEST_DATABASE_URL'), 'isolated PostgreSQL URL not configured')
class OfficialSalesStorageTests(unittest.TestCase):
    def test_nullable_migration_and_daily_campaign_upsert(self):
        import psycopg2
        with psycopg2.connect(os.environ['KEIPER_TEST_DATABASE_URL']) as conn:
            def execute(c, sql, params=None):
                cursor=c.cursor();cursor.execute(sql,params);return cursor
            execute(conn,'''CREATE TEMP TABLE ads_campanha_dia (
                conexao_id INTEGER, campanha_id TEXT, data TEXT, gasto REAL,
                faturamento REAL, atualizado_em BIGINT,
                PRIMARY KEY(conexao_id,campanha_id,data)) ON COMMIT DROP''')
            execute(conn,"INSERT INTO ads_campanha_dia VALUES (1,'a','2026-10-20',10,50,1)")
            init_schema(conn,execute);init_schema(conn,execute)
            self.assertEqual(execute(conn,'SELECT vendas_atribuidas,outras_vendas FROM ads_campanha_dia').fetchone(),(None,None))
            save_day(conn,execute,1,'a','2026-10-20',10,50,{'advertising_items_quantity':3,'organic_items_quantity':7,'organic_units_amount':40},2)
            save_day(conn,execute,1,'b','2026-10-20',2,5,{'advertising_items_quantity':1,'organic_items_quantity':0},2)
            rows=execute(conn,'SELECT campanha_id,vendas_atribuidas,outras_vendas,faturamento_sem_ads FROM ads_campanha_dia ORDER BY campanha_id').fetchall()
            self.assertEqual(rows,[('a',3,7,40.0),('b',1,0,None)])
            save_day(conn,execute,1,'a','2026-10-20',12,60,{},3)
            self.assertEqual(execute(conn,"SELECT COUNT(*) FROM ads_campanha_dia WHERE campanha_id='a'").fetchone()[0],1)
            self.assertEqual(execute(conn,"SELECT vendas_atribuidas,outras_vendas FROM ads_campanha_dia WHERE campanha_id='a'").fetchone(),(None,None))
