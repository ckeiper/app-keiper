"""Exercise production claim SQL on isolated PostgreSQL, without importing main."""
import os
import time
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from unittest.mock import Mock
from sync_exclusion import store_sync_lock

import psycopg2
from psycopg2.extras import RealDictCursor
from test_listing_details import main_function


@unittest.skipUnless(os.getenv('KEIPER_TEST_DATABASE_URL'),'isolated PostgreSQL URL not configured')
class DurablePostgresTests(unittest.TestCase):
    def setUp(self):
        self.schema = 'queue_test_' + uuid.uuid4().hex
        self.url = os.environ['KEIPER_TEST_DATABASE_URL']
        with psycopg2.connect(self.url) as conn:
            with conn.cursor() as cur:
                cur.execute('CREATE SCHEMA ' + self.schema)
                cur.execute('SET search_path TO ' + self.schema)
                cur.execute("CREATE TABLE conexoes(id integer primary key,status text)")
                cur.execute("""CREATE TABLE sincronizacao_execucoes(
                    id bigserial primary key,conexao_id integer,status text,
                    inicio_em bigint,fim_em bigint,heartbeat_em bigint,detalhe text)""")
                cur.execute("INSERT INTO conexoes VALUES(5,'ativa'),(6,'ativa'),(7,'inativa')")
                cur.execute("""CREATE TABLE sincronizacao_tarefas(
                    id bigserial primary key,conexao_id integer,status text default 'pendente',
                    tentativas integer default 0,disponivel_em bigint,criada_em bigint,
                    iniciada_em bigint,lease_ate bigint,concluida_em bigint,ultimo_erro text)""")
                for status in ('pendente','executando'):
                    cur.execute("CREATE UNIQUE INDEX one_"+status+" ON sincronizacao_tarefas(conexao_id) WHERE status='"+status+"'")
        self.env = patch.dict(os.environ, {'DURABLE_QUEUE_STORE_IDS':'5,7'})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.ns = dict(banco=self.connect, consultar=self.query, executar=self.execute,
                       time=time,os=os,psycopg2=psycopg2)
        for name in ('criar_tarefa_persistente','reservar_tarefa_persistente',
                     'reagendar_tarefa_persistente','recuperar_tarefas_persistentes'):
            main_function(name,self.ns)

    def connect(self):
        return psycopg2.connect(self.url,options='-c search_path='+self.schema)

    @staticmethod
    def execute(conn,sql,params=None):
        cur=conn.cursor()
        cur.execute(sql,params)
        return cur

    @staticmethod
    def query(conn,sql,params=None):
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql,params)
            return cur.fetchall()

    def tearDown(self):
        with psycopg2.connect(self.url) as conn:
            with conn.cursor() as cur:
                cur.execute('DROP SCHEMA '+self.schema+' CASCADE')

    def test_only_selected_active_store_is_claimed_and_enqueue_deduplicates(self):
        enqueue=self.ns['criar_tarefa_persistente']
        enqueue(6,agora=100)
        enqueue(7,agora=100)
        expected=enqueue(5,agora=100)
        self.assertIsNone(enqueue(5,agora=100))
        self.assertEqual(self.ns['reservar_tarefa_persistente'](agora=100)['id'],expected)
        self.assertIsNone(self.ns['reservar_tarefa_persistente'](agora=100))

    def test_two_workers_claim_only_one_job(self):
        self.ns['criar_tarefa_persistente'](5,agora=100)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:self.ns['reservar_tarefa_persistente'](agora=100),range(2)))
        self.assertEqual(sum(result is not None for result in results),1)

    def test_worker_recovers_abandoned_telemetry_and_excludes_legacy_collector(self):
        self.ns['criar_tarefa_persistente'](5,agora=100)
        with self.connect() as conn:
            self.execute(conn,"INSERT INTO sincronizacao_execucoes(conexao_id,status,inicio_em) VALUES(5,'executando',100)")
        for name in ('encerrar_execucoes_abandonadas','registrar_execucao_inicio',
                     'registrar_execucao_fim','finalizar_tarefa_persistente',
                     'processar_tarefa_persistente_uma'):
            main_function(name,self.ns)
        legacy_collect=Mock()
        legacy_ns=dict(store_sync_lock=store_sync_lock,banco=self.connect,consultar=legacy_collect)
        legacy=main_function('executar_atualizacao',legacy_ns)
        def collect(cid):
            with store_sync_lock(self.connect,cid) as nested:
                self.assertTrue(nested)
            with ThreadPoolExecutor(max_workers=1) as pool:
                self.assertFalse(pool.submit(legacy,cid).result())
            legacy_collect.assert_not_called()
            return True
        self.ns.update(store_sync_lock=store_sync_lock,iniciar_heartbeat_tarefa=Mock(return_value=Mock()),
                       executar_atualizacao=collect)
        self.assertTrue(self.ns['processar_tarefa_persistente_uma']())
        with self.connect() as conn:
            rows=self.query(conn,'SELECT status FROM sincronizacao_execucoes ORDER BY id')
            tasks=self.query(conn,'SELECT status FROM sincronizacao_tarefas')
        self.assertEqual([r['status'] for r in rows],['interrompida','concluida'])
        self.assertEqual(tasks[0]['status'],'concluida')

    def test_retry_backoff_and_cap_on_real_sql(self):
        task=self.ns['criar_tarefa_persistente'](5,agora=100)
        claim=self.ns['reservar_tarefa_persistente']
        retry=self.ns['reagendar_tarefa_persistente']
        for attempt in range(1,4):
            now=1000*attempt
            self.assertIsNotNone(claim(agora=now))
            self.assertEqual(retry(task,'failure',agora=now),1)
            with self.connect() as conn:
                row=self.query(conn,'SELECT * FROM sincronizacao_tarefas WHERE id=%s',(task,))[0]
            self.assertEqual(row['tentativas'],attempt)
            self.assertEqual(row['status'],'falhou' if attempt==3 else 'pendente')
            self.assertIsNone(row['lease_ate'])
            self.assertIsNone(claim(agora=now+1))
