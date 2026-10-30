import contextlib
import os
import time
import unittest
from unittest.mock import Mock, patch

import psycopg2
from test_listing_details import main_function


class DurableQueueTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"DURABLE_QUEUE_STORE_IDS": "5"})
        self.env.start()
        self.addCleanup(self.env.stop)
        # Load production functions into an isolated namespace without importing
        # main.py (which starts the scheduler and connects to the database).
        self.conn = Mock()
        self.ns = {
            "store_sync_lock": lambda connect,cid:contextlib.nullcontext(True),
            "encerrar_execucoes_abandonadas": Mock(),
            "banco": lambda: contextlib.nullcontext(self.conn),
            "consultar": Mock(),
            "executar": Mock(),
            "time": time,
            "os": os,
            "recuperar_tarefas_sem_coletor": Mock(),
            "psycopg2": psycopg2,
            "iniciar_heartbeat_tarefa": Mock(return_value=Mock()),
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

    def test_claim_is_scoped_to_active_pilot_store(self):
        self.ns["consultar"].return_value = []
        self.ns["reservar_tarefa_persistente"](agora=100)
        query, params = self.ns["consultar"].call_args.args[1:]
        self.assertIn("t.conexao_id = ANY(%s)", query)
        self.assertIn("c.status='ativa'", query)
        self.assertEqual(params, (100, [5]))

    def test_claim_without_allowlist_never_touches_database(self):
        with patch.dict(os.environ, {"DURABLE_QUEUE_STORE_IDS": ""}):
            self.assertIsNone(self.ns["reservar_tarefa_persistente"]())
        self.ns["consultar"].assert_not_called()

    def test_exception_stops_heartbeat_and_sanitizes_retry_reason(self):
        main_function("processar_tarefa_persistente_uma", self.ns)
        self.ns.update(reservar_tarefa_persistente=Mock(return_value={"id": 10, "conexao_id": 5}),
                       registrar_execucao_inicio=Mock(return_value=20),
                       executar_atualizacao=Mock(side_effect=ValueError("secret-token")),
                       registrar_execucao_fim=Mock(), reagendar_tarefa_persistente=Mock())
        self.assertFalse(self.ns["processar_tarefa_persistente_uma"]())
        self.ns["iniciar_heartbeat_tarefa"].return_value.set.assert_called_once()
        self.ns["reagendar_tarefa_persistente"].assert_called_once_with(10, "ValueError")

    def test_reservation_failure_never_starts_collection(self):
        main_function("processar_tarefa_persistente_uma", self.ns)
        self.ns.update(reservar_tarefa_persistente=Mock(return_value={"id": 10, "conexao_id": 5}),
                       registrar_execucao_inicio=Mock(side_effect=RuntimeError("database")),
                       executar_atualizacao=Mock(), reagendar_tarefa_persistente=Mock())
        self.assertFalse(self.ns["processar_tarefa_persistente_uma"]())
        self.ns["executar_atualizacao"].assert_not_called()

    def test_busy_full_collection_lock_never_retires_telemetry_or_collects(self):
        main_function("processar_tarefa_persistente_uma", self.ns)
        self.ns.update(reservar_tarefa_persistente=Mock(return_value={"id": 10, "conexao_id": 5}),
                       store_sync_lock=lambda connect,cid:contextlib.nullcontext(False),
                       executar_atualizacao=Mock(), reagendar_tarefa_persistente=Mock())
        self.assertFalse(self.ns["processar_tarefa_persistente_uma"]())
        self.ns["encerrar_execucoes_abandonadas"].assert_not_called()
        self.ns["executar_atualizacao"].assert_not_called()

    def test_worker_empty_queue_does_not_run_sync(self):
        main_function("processar_tarefa_persistente_uma", self.ns)
        self.ns["reservar_tarefa_persistente"] = Mock(return_value=None)
        self.ns["executar_atualizacao"] = Mock()
        self.assertFalse(self.ns["processar_tarefa_persistente_uma"]())
        self.ns["executar_atualizacao"].assert_not_called()

    def test_worker_success_finalizes_job(self):
        main_function("processar_tarefa_persistente_uma", self.ns)
        self.ns["reservar_tarefa_persistente"] = Mock(return_value={"id": 10, "conexao_id": 5})
        self.ns["registrar_execucao_inicio"] = Mock(return_value=20)
        self.ns["executar_atualizacao"] = Mock(return_value=True)
        self.ns["registrar_execucao_fim"] = Mock()
        self.ns["finalizar_tarefa_persistente"] = Mock()
        self.ns["reagendar_tarefa_persistente"] = Mock()
        self.assertTrue(self.ns["processar_tarefa_persistente_uma"]())
        self.ns["finalizar_tarefa_persistente"].assert_called_once_with(10, True)
        self.ns["reagendar_tarefa_persistente"].assert_not_called()

    def test_worker_failed_sync_is_retried(self):
        main_function("processar_tarefa_persistente_uma", self.ns)
        self.ns["reservar_tarefa_persistente"] = Mock(return_value={"id": 10, "conexao_id": 5})
        self.ns["registrar_execucao_inicio"] = Mock(return_value=20)
        self.ns["executar_atualizacao"] = Mock(return_value=False)
        self.ns["registrar_execucao_fim"] = Mock()
        self.ns["finalizar_tarefa_persistente"] = Mock()
        self.ns["reagendar_tarefa_persistente"] = Mock()
        self.assertFalse(self.ns["processar_tarefa_persistente_uma"]())
        self.ns["reagendar_tarefa_persistente"].assert_called_once_with(10, "Atualizacao retornou False")
        self.ns["finalizar_tarefa_persistente"].assert_not_called()

    def test_worker_busy_store_does_not_sync(self):
        main_function("processar_tarefa_persistente_uma", self.ns)
        self.ns["reservar_tarefa_persistente"] = Mock(return_value={"id": 10, "conexao_id": 5})
        self.ns["registrar_execucao_inicio"] = Mock(return_value=None)
        self.ns["executar_atualizacao"] = Mock()
        self.ns["reagendar_tarefa_persistente"] = Mock()
        self.assertFalse(self.ns["processar_tarefa_persistente_uma"]())
        self.ns["executar_atualizacao"].assert_not_called()
        self.ns["reagendar_tarefa_persistente"].assert_called_once()

    def test_optin_disabled_without_environment(self):
        main_function("loja_habilitada_fila_persistente", self.ns)
        import os
        from unittest.mock import patch
        self.ns["os"] = os
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(self.ns["loja_habilitada_fila_persistente"](5))

    def test_optin_only_selected_store(self):
        main_function("loja_habilitada_fila_persistente", self.ns)
        import os
        from unittest.mock import patch
        self.ns["os"] = os
        with patch.dict(os.environ, {"DURABLE_QUEUE_STORE_IDS": "5, 9"}):
            self.assertTrue(self.ns["loja_habilitada_fila_persistente"](5))
            self.assertFalse(self.ns["loja_habilitada_fila_persistente"](6))

    def test_scheduler_worker_disabled_by_default(self):
        main_function("job_fila_persistente", self.ns)
        import os
        from unittest.mock import patch
        self.ns["os"] = os
        self.ns["processar_tarefa_persistente_uma"] = Mock()
        with patch.dict(os.environ, {}, clear=True):
            self.ns["job_fila_persistente"]()
        self.ns["processar_tarefa_persistente_uma"].assert_not_called()

    def test_scheduler_worker_enabled_explicitly(self):
        main_function("job_fila_persistente", self.ns)
        import os
        from unittest.mock import patch
        self.ns["os"] = os
        self.ns["processar_tarefa_persistente_uma"] = Mock()
        with patch.dict(os.environ, {"DURABLE_QUEUE_WORKER_ENABLED": "true"}):
            self.ns["job_fila_persistente"]()
        self.ns["processar_tarefa_persistente_uma"].assert_called_once_with()

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

    def test_recovery_checks_existing_pending_task(self):
        self.ns["recuperar_tarefas_persistentes"](agora=500)
        sql = self.ns["executar"].call_args.args[1]
        self.assertIn("outra.status='pendente'", sql)
        self.assertIn("outra.conexao_id=sincronizacao_tarefas.conexao_id", sql)

    def test_retry_checks_existing_pending_task(self):
        self.ns["reagendar_tarefa_persistente"](7, "erro", agora=500)
        sql = self.ns["executar"].call_args.args[1]
        self.assertIn("outra.status='pendente'", sql)
        self.assertIn("outra.id<>sincronizacao_tarefas.id", sql)

    def test_failure_truncates_error(self):
        self.ns["executar"].return_value.rowcount = 1
        result = self.ns["reagendar_tarefa_persistente"](7, "x" * 500, agora=600)
        self.assertEqual(result, 1)
        params = self.ns["executar"].call_args.args[2]
        self.assertEqual(len(params[-2]), 300)
        self.assertEqual(params[-1], 7)


if __name__ == "__main__":
    unittest.main()
