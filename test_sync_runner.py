import contextlib
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from test_listing_details import main_function
from sync_runner import run_stages


class SyncRunnerTests(unittest.TestCase):
    def test_stage_exception_does_not_stop_sales_or_other_stages(self):
        log,resolve=Mock(),Mock()
        sales=Mock(return_value=True)
        ads=Mock(return_value=False)
        bad=Mock(side_effect=IndexError('tuple index out of range secret-token'))
        self.assertFalse(run_stages(5,[('anuncios',bad),('pedidos',sales),('ads',ads)],log,resolve,lambda:100))
        sales.assert_called_once()
        ads.assert_called_once()
        log.assert_called_once_with(5,'anuncios','Falha na coleta: IndexError')
        resolve.assert_called_once_with(5,'pedidos',100)

    def test_none_is_not_success_evidence(self):
        resolve=Mock()
        self.assertFalse(run_stages(5,[('envios',lambda:None)],Mock(),resolve,lambda:100))
        resolve.assert_not_called()

    def test_main_orchestration_uses_existing_ads_collector_once(self):
        collectors={name:Mock(return_value=True) for name in
                    ('conta','anuncios','pedidos','perguntas','envios','promocoes','ads')}
        namespace=dict(banco=lambda:contextlib.nullcontext(None),
                       store_sync_lock=lambda connect,cid:contextlib.nullcontext(True),
                       consultar=Mock(return_value=[dict(id=5,user_id=99)]),
                       token_atual=lambda c:'fake',time=SimpleNamespace(time=lambda:100),
                       registrar_erro=Mock(),resolver_erro=Mock(),run_stages=run_stages,
                       gravar_historico=Mock())
        namespace.update({'puxar_'+name:mock for name,mock in collectors.items()})
        self.assertTrue(main_function('executar_atualizacao',namespace)(5))
        for mock in collectors.values(): mock.assert_called_once()

    def test_worker_drains_remaining_shops_even_if_error_logging_fails(self):
        queue=[5,6]
        collect=Mock(side_effect=[IndexError('simulated'),True])
        namespace=dict(FILA_ATUALIZACAO=queue,LOCK_FILA=threading.Lock(),WORKER_VIVO=True,
                       ATUALIZANDO={5,6},LOCK_ATUALIZACAO=threading.Lock(),
                       registrar_execucao_inicio=Mock(side_effect=[11,12]),
                       registrar_execucao_fim=Mock(),
                       executar_atualizacao=collect,registrar_erro=Mock(side_effect=RuntimeError('database unavailable')))
        main_function('processar_fila',namespace)()
        self.assertEqual([c.args[0] for c in collect.call_args_list],[5,6])
        self.assertEqual(queue,[])
        self.assertEqual(namespace["ATUALIZANDO"],set())
        self.assertFalse(namespace['WORKER_VIVO'])

    def test_scheduler_enqueues_all_active_shops_without_running_network_calls(self):
        enqueue=Mock()
        namespace=dict(banco=lambda:contextlib.nullcontext(None),
                       consultar=Mock(return_value=[dict(id=5),dict(id=6)]),enfileirar_atualizacao=enqueue)
        main_function('job_dados',namespace)()
        self.assertEqual([c.args[0] for c in enqueue.call_args_list],[5,6])

    def test_queue_and_direct_collection_share_exclusion_guard(self):
        queue=[]
        active={5}
        thread=Mock()
        namespace=dict(FILA_ATUALIZACAO=queue,LOCK_FILA=threading.Lock(),WORKER_VIVO=False,
                       ATUALIZANDO=active,LOCK_ATUALIZACAO=threading.Lock(),
                       threading=SimpleNamespace(Thread=thread),processar_fila=Mock(),
                       loja_habilitada_fila_persistente=lambda cid:False)
        enqueue=main_function('enfileirar_atualizacao',namespace)
        self.assertFalse(enqueue(5))
        self.assertTrue(enqueue(6))
        self.assertFalse(enqueue(6))
        self.assertEqual(queue,[6])
        self.assertEqual(active,{5,6})
        thread.assert_called_once()

    def test_durable_worker_success_finalizes_job(self):
        finish=Mock()
        retry=Mock()
        collect=Mock(return_value=True)
        end=Mock()
        namespace=dict(store_sync_lock=lambda connect,cid:contextlib.nullcontext(True),
                       banco=Mock(),encerrar_execucoes_abandonadas=Mock(),
                       reservar_tarefa_persistente=lambda:dict(id=12,conexao_id=5),
                       registrar_execucao_inicio=lambda cid:33,
                       iniciar_heartbeat_tarefa=lambda tarefa_id, execucao_id:Mock(),
                       executar_atualizacao=collect,registrar_execucao_fim=end,
                       finalizar_tarefa_persistente=finish,reagendar_tarefa_persistente=retry)
        self.assertTrue(main_function('processar_tarefa_persistente_uma',namespace)())
        collect.assert_called_once_with(5)
        end.assert_called_once_with(33,'concluida')
        finish.assert_called_once_with(12,True)
        retry.assert_not_called()

    def test_durable_worker_without_job_does_not_collect(self):
        namespace=dict(store_sync_lock=lambda connect,cid:contextlib.nullcontext(True),
                       banco=Mock(),encerrar_execucoes_abandonadas=Mock(),
                       reservar_tarefa_persistente=lambda:None)
        self.assertFalse(main_function('processar_tarefa_persistente_uma',namespace)())

    def test_durable_worker_busy_store_retries_without_collection(self):
        retry=Mock()
        collect=Mock()
        namespace=dict(store_sync_lock=lambda connect,cid:contextlib.nullcontext(True),
                       banco=Mock(),encerrar_execucoes_abandonadas=Mock(),
                       reservar_tarefa_persistente=lambda:dict(id=12,conexao_id=5),
                       registrar_execucao_inicio=lambda cid:None,
                       executar_atualizacao=collect,reagendar_tarefa_persistente=retry)
        self.assertFalse(main_function('processar_tarefa_persistente_uma',namespace)())
        collect.assert_not_called()
        retry.assert_called_once_with(12,'Loja ja em execucao')

    def test_durable_scheduler_is_disabled_by_default(self):
        from unittest.mock import patch
        worker=Mock()
        namespace=dict(os=SimpleNamespace(getenv=lambda name,default='':default),
                       processar_tarefa_persistente_uma=worker,app=SimpleNamespace(logger=Mock()))
        main_function('job_fila_persistente',namespace)()
        worker.assert_not_called()

    def test_durable_scheduler_runs_once_when_enabled(self):
        worker=Mock()
        namespace=dict(os=SimpleNamespace(getenv=lambda name,default='':'true'),
                       processar_tarefa_persistente_uma=worker,app=SimpleNamespace(logger=Mock()))
        main_function('job_fila_persistente',namespace)()
        worker.assert_called_once_with()

    def test_durable_scheduler_logs_worker_failure_without_raising(self):
        logger=Mock()
        worker=Mock(side_effect=RuntimeError('database unavailable'))
        namespace=dict(os=SimpleNamespace(getenv=lambda name,default='':'true'),
                       processar_tarefa_persistente_uma=worker,app=SimpleNamespace(logger=logger))
        main_function('job_fila_persistente',namespace)()
        logger.exception.assert_called_once_with('Falha no worker da fila persistente')

    def test_durable_worker_failed_collection_is_retried(self):
        finish=Mock()
        retry=Mock()
        end=Mock()
        namespace=dict(store_sync_lock=lambda connect,cid:contextlib.nullcontext(True),
                       banco=Mock(),encerrar_execucoes_abandonadas=Mock(),
                       reservar_tarefa_persistente=lambda:dict(id=12,conexao_id=5),
                       registrar_execucao_inicio=lambda cid:33,
                       iniciar_heartbeat_tarefa=lambda tarefa_id, execucao_id:Mock(),
                       executar_atualizacao=Mock(return_value=False),
                       registrar_execucao_fim=end,
                       finalizar_tarefa_persistente=finish,reagendar_tarefa_persistente=retry)
        self.assertFalse(main_function('processar_tarefa_persistente_uma',namespace)())
        end.assert_called_once_with(33,'falhou')
        retry.assert_called_once_with(12,'Atualizacao retornou False')
        finish.assert_not_called()

    def test_durable_worker_exception_retries_and_marks_execution_failed(self):
        retry=Mock()
        end=Mock()
        namespace=dict(store_sync_lock=lambda connect,cid:contextlib.nullcontext(True),
                       banco=Mock(),encerrar_execucoes_abandonadas=Mock(),
                       reservar_tarefa_persistente=lambda:dict(id=12,conexao_id=5),
                       registrar_execucao_inicio=lambda cid:33,
                       iniciar_heartbeat_tarefa=lambda tarefa_id, execucao_id:Mock(),
                       executar_atualizacao=Mock(side_effect=ValueError('secret')),
                       registrar_execucao_fim=end,
                       reagendar_tarefa_persistente=retry)
        self.assertFalse(main_function('processar_tarefa_persistente_uma',namespace)())
        end.assert_called_once_with(33,'falhou','ValueError')
        retry.assert_called_once_with(12,'ValueError')

    def test_expired_durable_lease_is_recovered_with_retry_cap(self):
        statements=[]
        cursor=SimpleNamespace(rowcount=2)
        def execute(conn,sql,params):
            statements.append((sql,params))
            return cursor
        namespace=dict(banco=lambda:contextlib.nullcontext(None),executar=execute,
                       time=SimpleNamespace(time=lambda:10000))
        recovered=main_function('recuperar_tarefas_persistentes',namespace)(agora=10000,max_tentativas=3)
        self.assertEqual(recovered,2)
        sql,params=statements[0]
        self.assertIn("status='executando' AND lease_ate < %s",sql)
        self.assertIn("tentativas >= %s",sql)
        self.assertIn("'falhou' ELSE 'pendente'",sql)
        self.assertIn("lease_ate=NULL",sql)
        self.assertEqual(params,(3,3,10000,3,10000,10000))

    def test_durable_retry_caps_attempts_and_clears_lease(self):
        statements=[]
        cursor=SimpleNamespace(rowcount=1)
        def execute(conn,sql,params):
            statements.append((sql,params))
            return cursor
        namespace=dict(banco=lambda:contextlib.nullcontext(None),executar=execute,
                       time=SimpleNamespace(time=lambda:10000))
        count=main_function('reagendar_tarefa_persistente',namespace)(12,'network error',agora=10000,max_tentativas=3)
        self.assertEqual(count,1)
        sql,params=statements[0]
        self.assertIn("WHERE id=%s AND status='executando'",sql)
        self.assertIn("lease_ate=NULL",sql)
        self.assertIn("'falhou' ELSE 'pendente'",sql)
        self.assertEqual(params,(3,3,10000,3,10000,'network error',12))
