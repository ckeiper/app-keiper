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
