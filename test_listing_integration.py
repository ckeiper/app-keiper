"""Opt-in PostgreSQL tests; never use the production database URL."""
import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock


@unittest.skipUnless(os.getenv('KEIPER_TEST_DATABASE_URL'), 'isolated PostgreSQL URL not configured')
class ListingDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ['DATABASE_URL'] = os.environ['KEIPER_TEST_DATABASE_URL']
        import main
        cls.main = main
        if main.scheduler.running:
            main.scheduler.shutdown(wait=False)
        main.iniciar_banco()

    def test_additive_schema_snapshot_and_tenant_isolation(self):
        from listing_sync import sync_promotions
        main = self.main
        with main.banco() as conn:
            cid = main.consultar(conn, 'INSERT INTO conexoes (cliente) VALUES (%s) RETURNING id', ('Teste Anúncios',))[0]['id']
            main.executar(conn, 'INSERT INTO anuncios (conexao_id,item_id,pesos_json) VALUES (%s,%s,%s)',
                          (cid, 'MLBTEST', json.dumps({'item': [], 'variations': []})))
        try:
            request = Mock(return_value=SimpleNamespace(status_code=200, headers={}, json=lambda: []))
            self.assertTrue(sync_promotions(cid, 'fake', main.banco, main.consultar, main.executar,
                                            request, main.registrar_erro))
            with main.banco() as conn:
                row = main.consultar(conn, 'SELECT promocoes_json,pesos_json FROM anuncios WHERE conexao_id=%s', (cid,))[0]
                self.assertEqual(json.loads(row['promocoes_json'])['promotions'], [])
                self.assertEqual(json.loads(row['pesos_json'])['item'], [])
                self.assertFalse(main.consultar(conn, 'SELECT item_id FROM anuncios WHERE conexao_id=%s AND item_id=%s',
                                                (-cid, 'MLBTEST')))
        finally:
            with main.banco() as conn:
                for table in ('anuncios', 'erros'):
                    main.executar(conn, 'DELETE FROM ' + table + ' WHERE conexao_id=%s', (cid,))
                main.executar(conn, 'DELETE FROM conexoes WHERE id=%s', (cid,))
