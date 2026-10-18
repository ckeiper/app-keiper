import contextlib
import time
import unittest
from unittest.mock import Mock

import psycopg2
from test_listing_details import main_function


class DurableQueueTests(unittest.TestCase):
    def setUp(self):
        # Load production functions into an isolated namespace without importing
        # main.py (which starts the scheduler and connects to the database).
        self.conn = Mock()
        self.ns = {
            "banco": lambda: contextlib.nullcontext(self.conn),
            "consultar": Mock(),
            "executar": Mock(),
            "time": time,
            "psycopg2": psycopg2,
        }
        for name in (
            "reservar_tarefa_persistente",
            "recuperar_tarefas_persistentes",
            "reagendar_tarefa_persistente",
        ):
            main_function(name, self.ns)

    def test_duplicate_enqueue_returns_none(self):
        main_function("criar_tarefa_persistente", self.ns)
        self.ns["executar"].return_value.fetchone.return_value = None
        self.assertIsNone(self.ns["criar_tarefa_persistente"](5, agora=100))
        self.assertIn("ON CONFLICT DO NOTHING", self.ns["executar"].call_args.args[1])

    def test_claim_excludes_running_store(self):
        self.ns["consultar"].return_value = []
        self.ns["reservar_tarefa_persistente"](agora=100)
        query = self.ns["consultar"].call_args.args[1]
        self.assertIn("a.conexao_id=t.conexao_id", query)

    def test_claim_skips_empty_queue(self):
        self.ns["consultar"].return_value = []
        result = self.ns["reservar_tarefa_persistente"](agora=100)
        self.assertIsNone(result)
        self.ns["executar"].assert_not_called()

    def test_claim_increments_attempt_and_sets_lease(self):
        task = {"id": 12, "conexao_id": 5}
        self.ns["consultar"].return_value = [task]
        result = self.ns["reservar_tarefa_persistente"](agora=100, duracao_lease=300)
        self.assertEqual(result, task)
        args = self.ns["executar"].call_args.args
        self.assertIn("tentativas=tentativas+1", args[1])
        self.assertEqual(args[2], (100, 400, 12))

    def test_recovery_respects_retry_limit(self):
        self.ns["executar"].return_value.rowcount = 2
        result = self.ns["recuperar_tarefas_persistentes"](agora=500, max_tentativas=3)
        self.assertEqual(result, 2)
        sql, params = self.ns["executar"].call_args.args[1:]
        self.assertIn("lease_ate < %s", sql)
        self.assertEqual(params, (3, 3, 500, 3, 500, 500))

    def test_failure_truncates_error(self):
        self.ns["executar"].return_value.rowcount = 1
        result = self.ns["reagendar_tarefa_persistente"](7, "x" * 500, agora=600)
        self.assertEqual(result, 1)
        params = self.ns["executar"].call_args.args[2]
        self.assertEqual(len(params[-2]), 300)
        self.assertEqual(params[-1], 7)


if __name__ == "__main__":
    unittest.main()
