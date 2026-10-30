import contextlib
import os
import unittest
from unittest.mock import Mock,patch
from visits_refresh import DUE_STORE_SQL,REFRESH_HOURS


class VisitsRefreshJobTests(unittest.TestCase):
    def test_actual_job_refreshes_a_due_store_and_releases_its_lock(self):
        from test_listing_details import main_function
        cur=Mock();cur.fetchone.side_effect=[(True,),(42,)]
        conn=Mock();conn.cursor.return_value=contextlib.nullcontext(cur)
        app=Mock()
        provider=Mock(return_value='fake')
        query=Mock(return_value=[{'id':42}])
        job=main_function('job_visitas_todas_contas',dict(os=os,app=app,banco=lambda:contextlib.nullcontext(None),consultar=query,token_atual=provider))
        with patch.dict(os.environ,{'VISITS_AUTO_ENABLED':'1','DATABASE_URL':'isolated'}),patch('psycopg2.connect',return_value=conn),patch('copas_visits_store.collect',return_value={}) as collect:
            job()
        collect.assert_called_once_with(limit=40,connection_id=42,rotate=True)
        provider.assert_called_once_with({'id':42})
        cur.execute.assert_any_call(DUE_STORE_SQL,(REFRESH_HOURS,))
        cur.execute.assert_any_call('SELECT pg_advisory_unlock(%s)',(880142,))
        conn.close.assert_called_once()
        app.logger.exception.assert_not_called()

    def test_no_collection_when_token_cannot_be_refreshed(self):
        from test_listing_details import main_function
        cur=Mock();cur.fetchone.side_effect=[(True,),(42,)]
        conn=Mock();conn.cursor.return_value=contextlib.nullcontext(cur)
        app=Mock()
        job=main_function('job_visitas_todas_contas',dict(os=os,app=app,
            banco=lambda:contextlib.nullcontext(None),consultar=Mock(return_value=[{'id':42}]),token_atual=Mock(return_value=None)))
        with patch.dict(os.environ,{'VISITS_AUTO_ENABLED':'1','DATABASE_URL':'isolated'}),patch('psycopg2.connect',return_value=conn),patch('copas_visits_store.collect') as collect:
            job()
        collect.assert_not_called()
        cur.execute.assert_any_call('SELECT pg_advisory_unlock(%s)',(880142,))
        app.logger.warning.assert_called_once()

    def test_failed_batch_is_visible_in_warning_logs(self):
        from test_listing_details import main_function
        cur=Mock();cur.fetchone.side_effect=[(True,),(42,)]
        conn=Mock();conn.cursor.return_value=contextlib.nullcontext(cur)
        app=Mock()
        job=main_function('job_visitas_todas_contas',dict(os=os,app=app,
            banco=lambda:contextlib.nullcontext(None),consultar=Mock(return_value=[{'id':42}]),token_atual=Mock(return_value='fake')))
        with patch.dict(os.environ,{'VISITS_AUTO_ENABLED':'1','DATABASE_URL':'isolated'}),patch('psycopg2.connect',return_value=conn),patch('copas_visits_store.collect',return_value={'falhas':2}):
            job()
        app.logger.warning.assert_called_once_with('visits_batch_result %s',{'falhas':2})

    def test_kill_switch_preserved(self):
        from test_listing_details import main_function
        job=main_function('job_visitas_todas_contas',dict(os=os,app=Mock()))
        with patch.dict(os.environ,{'VISITS_AUTO_ENABLED':'0'}),patch('copas_visits_store.collect') as collect:
            job()
        collect.assert_not_called()


class VisitsFailureRotationTests(unittest.TestCase):
    def test_failed_request_records_attempt_without_overwriting_daily_history(self):
        from copas_visits_store import _save_attempt
        cur=Mock();conn=Mock();conn.cursor.return_value=contextlib.nullcontext(cur)
        _save_attempt(conn,42,'MLB1',[],'HTTP 403')
        self.assertEqual(cur.execute.call_count,1)
        self.assertIn('INSERT INTO item_visits_checked',cur.execute.call_args.args[0])
        self.assertEqual(cur.execute.call_args.args[1],(42,'MLB1'))

    def test_success_records_only_returned_days_then_rotates(self):
        from copas_visits_store import _save_attempt
        from datetime import date
        cur=Mock();conn=Mock();conn.cursor.return_value=contextlib.nullcontext(cur)
        _save_attempt(conn,42,'MLB1',[(date(2026,10,20),0)],None)
        self.assertEqual(cur.execute.call_count,2)
        self.assertIn('INSERT INTO item_visits_daily',cur.execute.call_args_list[0].args[0])
        self.assertEqual(cur.execute.call_args_list[0].args[1],(42,'MLB1',date(2026,10,20),0))


@unittest.skipUnless(os.getenv('KEIPER_TEST_DATABASE_URL'),'isolated PostgreSQL URL not configured')
class VisitsRefreshSQLTests(unittest.TestCase):
    def test_refreshes_old_stores_even_when_all_items_previously_checked(self):
        import psycopg2
        with psycopg2.connect(os.environ['KEIPER_TEST_DATABASE_URL']) as conn:
            with conn.cursor() as cur:
                cur.execute("CREATE TEMP TABLE conexoes (id integer,status text,access_token text)")
                cur.execute("CREATE TEMP TABLE anuncios (conexao_id integer,item_id text,status text)")
                cur.execute("CREATE TEMP TABLE item_visits_checked (conexao_id integer,item_id text,consultado_em timestamptz)")
                cur.execute("INSERT INTO conexoes VALUES (1,'ativa','fake'),(2,'ativa','fake'),(3,'ativa','fake'),(4,'inativa','fake')")
                cur.execute("INSERT INTO anuncios VALUES (1,'MLB1','active'),(2,'MLB2','active'),(3,'INVALID','active'),(4,'MLB4','active')")
                cur.execute("INSERT INTO item_visits_checked VALUES (1,'MLB1',NOW()-INTERVAL '7 hours'),(2,'MLB2',NOW()-INTERVAL '1 hour')")
                cur.execute(DUE_STORE_SQL,(REFRESH_HOURS,));self.assertEqual(cur.fetchone(),(1,))
                cur.execute("UPDATE item_visits_checked SET consultado_em=NOW() WHERE conexao_id=1")
                cur.execute(DUE_STORE_SQL,(REFRESH_HOURS,));self.assertIsNone(cur.fetchone())
                cur.execute("INSERT INTO anuncios VALUES (2,'MLB22','active')")
                cur.execute(DUE_STORE_SQL,(REFRESH_HOURS,));self.assertEqual(cur.fetchone(),(2,))

if __name__=='__main__':
    unittest.main()
