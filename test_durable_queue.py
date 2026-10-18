import contextlib
import unittest
from unittest.mock import Mock
from test_listing_details import main_function


class DurableQueueTests(unittest.TestCase):
    def setUp(self):
        self.ns = main_function.__globals__
        self.old_banco = self.ns["banco"]
        self.old_consultar = self.ns["consultar"]
        self.old_executar = self.ns["executar"]
        self.conn = Mock()
        self.ns["banco"] = lambda: contextlib.nullcontext(self.conn)
        self.ns["consultar"] = Mock()
        self.ns["executar"] = Mock()

    def tearDown(self):
        self.ns["banco"] = self.old_banco
        self.ns["consultar"] = self.old_consultar
        self.ns["executar"] = self.old_executar

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
