"""Regression for deleting a store with daily visits and other dependencies."""
import os
import unittest

import psycopg2

from test_listing_details import main_function


@unittest.skipUnless(os.getenv("KEIPER_TEST_DATABASE_URL"), "isolated PostgreSQL URL not configured")
class StoreDeletionTests(unittest.TestCase):
    tables = (
        "item_visits_daily", "atualizacoes_secao", "sincronizacao_tarefas",
        "vendas_destinos", "full_observations", "dados_conta", "anuncios", "pedidos",
        "pedidos_itens", "metricas", "desempenho_historico", "perguntas", "envios",
        "promocoes", "promocoes_itens", "ads_campanhas", "ads_metricas", "ads_dia",
        "ads_campanha_dia", "erros",
    )

    def setUp(self):
        self.conn = psycopg2.connect(os.environ["KEIPER_TEST_DATABASE_URL"])
        self.addCleanup(self.conn.close)
        with self.conn:
            self.execute(self.conn, "CREATE TEMP TABLE conexoes (id INTEGER PRIMARY KEY)")
            self.execute(self.conn, "INSERT INTO conexoes VALUES (5), (6)")
            for table in self.tables:
                self.execute(self.conn, f"CREATE TEMP TABLE {table} "
                             "(conexao_id INTEGER REFERENCES conexoes(id))")
                self.execute(self.conn, f"INSERT INTO {table} VALUES (5), (6)")
        ns = dict(executar=self.execute, consultar=self.query)
        main_function("remover_dados_loja", ns)
        self.remove = ns["remover_dados_loja"]

    @staticmethod
    def execute(conn, sql, params=None):
        with conn.cursor() as cursor:
            cursor.execute(sql, params)

    @staticmethod
    def query(conn, sql, params=None):
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.fetchall()

    def test_removes_only_requested_store_and_handles_repeat(self):
        with self.conn:
            self.assertTrue(self.remove(self.conn, 5))
            self.assertFalse(self.remove(self.conn, 5))
            self.assertEqual(self.query(self.conn, "SELECT id FROM conexoes"), [(6,)])
            for table in self.tables:
                self.assertEqual(self.query(self.conn, f"SELECT conexao_id FROM {table}"), [(6,)])

    def test_rolls_back_all_tables_if_final_delete_fails(self):
        with self.conn:
            self.execute(self.conn, "CREATE TEMP TABLE dependency (id INTEGER REFERENCES conexoes(id))")
            self.execute(self.conn, "INSERT INTO dependency VALUES (5)")
        with self.assertRaises(psycopg2.errors.ForeignKeyViolation):
            with self.conn:
                self.remove(self.conn, 5)
        with self.conn:
            self.assertEqual(self.query(self.conn, "SELECT id FROM conexoes ORDER BY id"), [(5,), (6,)])
            for table in self.tables:
                self.assertEqual(self.query(self.conn, f"SELECT conexao_id FROM {table} ORDER BY 1"),
                                 [(5,), (6,)])
