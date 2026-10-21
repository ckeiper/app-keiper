from auth_test_support import database_session
"""Opt-in PostgreSQL tests; never use the production database URL."""
import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch


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

    def test_listing_upsert_and_authenticated_page(self):
        main = self.main
        with main.banco() as conn:
            cid = main.consultar(conn, 'INSERT INTO conexoes (cliente) VALUES (%s) RETURNING id', ('Teste Pesos',))[0]['id']
            main.executar(conn, '''INSERT INTO anuncios (conexao_id,item_id,custo)
                                  VALUES (%s,%s,%s)''', (cid, 'MLBTEST', 25))
        try:
            def api(token, path, params, request_get):
                if path.endswith('/items/search'):
                    return {'results': ['MLBTEST'], 'paging': {'total': 1}}, None
                return [{'code': 200, 'body': {'id': 'MLBTEST', 'title': 'Produto de teste',
                         'price': 80, 'original_price': 100, 'status': 'active',
                         'attributes': [{'id': 'SELLER_PACKAGE_WEIGHT', 'value_name': '1500 g'}]}}], None
            with patch.object(main, 'get_json', side_effect=api):
                for _ in range(2):
                    main.puxar_anuncios(cid, 'fake', 1)
            with main.banco() as conn:
                rows = main.consultar(conn, 'SELECT * FROM anuncios WHERE conexao_id=%s', (cid,))
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]['peso'], 1.5)
                self.assertEqual(rows[0]['custo'], 25)
                self.assertIn('SELLER_PACKAGE_WEIGHT', rows[0]['pesos_json'])
            client = main.app.test_client()
            self.assertEqual(client.get('/anuncios/' + str(cid)).status_code, 302)
            with database_session(client) as session:
                session.update(usuario_id=1, tipo='cliente', conexao_id=cid + 1)
            self.assertIn('Acesso restrito', client.get('/anuncios/' + str(cid)).get_data(as_text=True))
            with database_session(client) as session:
                session.update(usuario_id=1, tipo='admin')
            with patch.object(main.requests, 'get', side_effect=AssertionError('GET during render')):
                response = client.get('/anuncios/' + str(cid))
            self.assertEqual(response.status_code, 200)
            output = response.get_data(as_text=True)
            self.assertIn('Peso cadastrado', output)
            self.assertIn('Peso logístico', output)
            self.assertIn('1.5 kg', output)
            self.assertNotIn('de R$ 100.00', output)
            with patch.object(main, 'token_atual', return_value='fake'), patch.object(
                    main, 'inspect_listing', return_value={'item_id': 'MLBTEST'}) as inspect:
                self.assertEqual(client.get('/diagnostico/anuncios/' + str(cid) + '/MLBTEST').status_code, 200)
                self.assertEqual(client.get('/diagnostico/anuncios/' + str(cid + 1) + '/MLBTEST').status_code, 404)
                self.assertEqual(inspect.call_count, 1)
                with database_session(client) as session:
                    session.update(tipo='cliente', conexao_id=cid)
                self.assertEqual(client.get('/diagnostico/anuncios/' + str(cid) + '/MLBTEST').status_code, 403)
        finally:
            with main.banco() as conn:
                for table in ('anuncios', 'erros'):
                    main.executar(conn, 'DELETE FROM ' + table + ' WHERE conexao_id=%s', (cid,))
                main.executar(conn, 'DELETE FROM conexoes WHERE id=%s', (cid,))

    def test_campaign_replacement_rolls_back_on_write_failure(self):
        from listing_sync import sync_campaign_cache
        main = self.main
        with main.banco() as conn:
            cid = main.consultar(conn, 'INSERT INTO conexoes (cliente) VALUES (%s) RETURNING id', ('Teste Rollback',))[0]['id']
            main.executar(conn, '''INSERT INTO promocoes (conexao_id,promocao_id,status)
                                  VALUES (%s,%s,%s)''', (cid, 'OLD', 'active'))
            main.executar(conn, '''INSERT INTO promocoes_itens (conexao_id,item_id,promocao_id)
                                  VALUES (%s,%s,%s)''', (cid, 'MLBOLD', 'OLD'))
        try:
            request_get = Mock(side_effect=[
                SimpleNamespace(status_code=200, headers={}, json=lambda: {'results': [
                    {'id': 'NEW', 'type': 'DEAL', 'status': 'started'}]}),
                SimpleNamespace(status_code=200, headers={}, json=lambda: {'results': [
                    {'id': 'MLBNEW', 'status': 'started', 'price': 80}]})])
            def fail_write(conn, sql, params=None):
                if 'INSERT INTO promocoes_itens' in sql:
                    raise RuntimeError('simulated write failure')
                main.executar(conn, sql, params)
            with self.assertRaises(RuntimeError):
                sync_campaign_cache(cid, 'fake', 1, main.banco, fail_write, request_get)
            with main.banco() as conn:
                campaigns = main.consultar(conn, 'SELECT promocao_id FROM promocoes WHERE conexao_id=%s', (cid,))
                items = main.consultar(conn, 'SELECT item_id FROM promocoes_itens WHERE conexao_id=%s', (cid,))
                self.assertEqual([p['promocao_id'] for p in campaigns], ['OLD'])
                self.assertEqual([p['item_id'] for p in items], ['MLBOLD'])
        finally:
            with main.banco() as conn:
                for table in ('promocoes_itens', 'promocoes'):
                    main.executar(conn, 'DELETE FROM ' + table + ' WHERE conexao_id=%s', (cid,))
                main.executar(conn, 'DELETE FROM conexoes WHERE id=%s', (cid,))
