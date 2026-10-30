import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock
from sync_exclusion import store_sync_lock
from test_listing_details import main_function


class ExclusionTests(unittest.TestCase):
    def test_closes_session_on_collector_failure(self):
        conn = Mock()
        conn.cursor.return_value.__enter__ = Mock(return_value=Mock())
        conn.cursor.return_value.__exit__ = Mock(return_value=False)
        conn.cursor.return_value.__enter__.return_value.fetchone.return_value = (True,)
        with self.assertRaises(ValueError):
            with store_sync_lock(lambda: conn, 5):
                raise ValueError("collector failed")
        conn.close.assert_called_once()

    def test_busy_lock_skips_all_collectors(self):
        from contextlib import nullcontext
        collect = Mock()
        ns = dict(store_sync_lock=lambda connect,cid:nullcontext(False), banco=Mock(),
                  consultar=collect)
        self.assertFalse(main_function('executar_atualizacao',ns)(5))
        collect.assert_not_called()

    def test_legacy_reservation_failure_skips_collection_and_drains_queue(self):
        import threading
        collect = Mock()
        ns = dict(FILA_ATUALIZACAO=[5], LOCK_FILA=threading.Lock(), WORKER_VIVO=True,
                  ATUALIZANDO={5}, LOCK_ATUALIZACAO=threading.Lock(),
                  registrar_execucao_inicio=Mock(side_effect=RuntimeError('database')),
                  executar_atualizacao=collect, registrar_erro=Mock())
        main_function('processar_fila',ns)()
        collect.assert_not_called()
        self.assertFalse(ns['WORKER_VIVO'])
        self.assertEqual(ns['ATUALIZANDO'],set())


@unittest.skipUnless(os.getenv('KEIPER_TEST_DATABASE_URL'),'isolated PostgreSQL URL not configured')
class PostgresExclusionTests(unittest.TestCase):
    def test_two_sessions_cannot_collect_same_store_even_after_telemetry_expires(self):
        import psycopg2
        connect = lambda:psycopg2.connect(os.environ['KEIPER_TEST_DATABASE_URL'])
        with store_sync_lock(connect, 2147483600) as first:
            self.assertTrue(first)
            # No lease or telemetry timestamp can release a live session lock.
            def competing_session():
                with store_sync_lock(connect, 2147483600) as second:
                    return second
            with ThreadPoolExecutor(max_workers=1) as pool:
                self.assertFalse(pool.submit(competing_session).result())
            # The durable worker and its nested collection share ownership.
            with store_sync_lock(connect, 2147483600) as nested:
                self.assertTrue(nested)
            with store_sync_lock(connect, 2147483601) as other_store:
                self.assertTrue(other_store)
        with store_sync_lock(connect, 2147483600) as after_release:
            self.assertTrue(after_release)
