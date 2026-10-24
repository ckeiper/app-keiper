import contextlib
import os
import uuid
import unittest
from unittest.mock import Mock
import psycopg2
from startup_schema import schema_executor,initialize_with_retry


class DatabaseError(psycopg2.Error):
    def __init__(self,code):self.code=code
    @property
    def pgcode(self):return self.code


class StartupSchemaTests(unittest.TestCase):
    def test_existing_column_does_not_take_an_exclusive_ddl_lock(self):
        cursor=Mock();cursor.fetchone.return_value=(1,)
        execute=Mock(return_value=cursor)
        schema_executor(execute)(None,'ALTER TABLE competitor_targets ADD COLUMN IF NOT EXISTS own_item_id TEXT')
        self.assertEqual(execute.call_count,1)
        self.assertIn('pg_attribute',execute.call_args.args[1])
        self.assertEqual(execute.call_args.args[2],('competitor_targets','own_item_id'))

    def test_missing_column_and_other_statements_keep_original_sql(self):
        cursor=Mock();cursor.fetchone.return_value=None
        execute=Mock(return_value=cursor);run=schema_executor(execute)
        sql='ALTER TABLE competitor_targets ADD COLUMN IF NOT EXISTS own_item_id TEXT'
        run(None,sql)
        self.assertEqual(execute.call_count,2)
        self.assertEqual(execute.call_args.args,(None,sql,None))
        execute.reset_mock();run(None,'SELECT %s',(7,))
        execute.assert_called_once_with(None,'SELECT %s',(7,))

    def test_transient_failures_retry_the_entire_initializer_with_bounded_backoff(self):
        for code in ('40P01','55P03','40001'):
            init=Mock(side_effect=[DatabaseError(code),DatabaseError(code),'ready'])
            logger=Mock();sleep=Mock()
            self.assertEqual(initialize_with_retry(init,logger,sleep),'ready')
            self.assertEqual(init.call_count,3)
            self.assertEqual([c.args[0] for c in sleep.call_args_list],[1,2])
            self.assertNotIn('database message',str(logger.warning.call_args_list))

    def test_permanent_errors_are_not_hidden_or_retried_forever(self):
        for code,attempts in [('42601',1),('40P01',4)]:
            init=Mock(side_effect=DatabaseError(code));sleep=Mock()
            with self.assertRaises(DatabaseError):initialize_with_retry(init,Mock(),sleep)
            self.assertEqual(init.call_count,attempts)
            self.assertEqual(sleep.call_count,attempts-1)


@unittest.skipUnless(os.getenv('KEIPER_TEST_DATABASE_URL'),'isolated PostgreSQL not configured')
class StartupSchemaDatabaseTests(unittest.TestCase):
    def test_lock_timeout_rolls_back_whole_attempt_and_retries_without_data_loss(self):
        table='test_schema_retry_'+uuid.uuid4().hex
        url=os.environ['KEIPER_TEST_DATABASE_URL']
        def execute(conn,sql,params=None):
            cur=conn.cursor();cur.execute(sql,params or ());return cur
        with contextlib.closing(psycopg2.connect(url)) as setup:
            with setup:execute(setup,'CREATE TABLE '+table+'(id INTEGER)');execute(setup,'INSERT INTO '+table+' VALUES(1)')
        blocker=psycopg2.connect(url)
        try:
            execute(blocker,'SELECT * FROM '+table)
            calls=[]
            def initialize():
                calls.append(1)
                with contextlib.closing(psycopg2.connect(url)) as conn:
                    with conn:
                        execute(conn,'INSERT INTO '+table+' VALUES(2)')
                        execute(conn,"SET LOCAL lock_timeout='50ms'")
                        execute(conn,'ALTER TABLE '+table+' ADD COLUMN IF NOT EXISTS note TEXT')
            sleep=Mock(side_effect=lambda delay:blocker.rollback())
            initialize_with_retry(initialize,Mock(),sleep)
            self.assertEqual(len(calls),2)
            with contextlib.closing(psycopg2.connect(url)) as conn:
                with conn:
                    self.assertEqual(execute(conn,'SELECT id FROM '+table+' ORDER BY id').fetchall(),[(1,),(2,)])
                    # With an existing column, a shared lock must not block a
                    # repeated startup DDL that has no actual schema work.
                    execute(blocker,'SELECT * FROM '+table)
                    execute(conn,"SET LOCAL lock_timeout='50ms'")
                    schema_executor(execute)(conn,'ALTER TABLE '+table+' ADD COLUMN IF NOT EXISTS note TEXT')
        finally:
            blocker.rollback();blocker.close()
            with contextlib.closing(psycopg2.connect(url)) as conn:
                with conn:execute(conn,'DROP TABLE '+table)
