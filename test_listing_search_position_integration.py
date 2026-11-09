"""Exercise persistence and isolation with the disposable PostgreSQL database."""
import os
import unittest
from uuid import uuid4

from auth_test_support import database_session


@unittest.skipUnless(os.getenv('KEIPER_TEST_DATABASE_URL'), 'isolated PostgreSQL not configured')
class SearchPositionIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ['DATABASE_URL'] = os.environ['KEIPER_TEST_DATABASE_URL']
        import main
        cls.m = main
        if main.scheduler.running:
            main.scheduler.shutdown(wait=False)
        main.app.config['TESTING'] = True

    def test_observations_persist_once_and_are_scoped_to_store_and_listing(self):
        m = self.m
        ids = []
        try:
            with m.banco() as conn:
                for label in ('Posição A', 'Posição B'):
                    cid = m.consultar(conn, "INSERT INTO conexoes(cliente,status) VALUES(%s,'ativa') RETURNING id",
                                     (label,))[0]['id']
                    ids.append(cid)
                    for item in ('MLB123', 'MLB456'):
                        m.executar(conn, 'INSERT INTO anuncios(conexao_id,item_id,titulo) VALUES(%s,%s,%s)',
                                   (cid, item, label))
            client = m.app.test_client()
            with database_session(client) as s:
                s.update(usuario_id=781, tipo='admin')
            path = f'/anuncios/{ids[0]}/MLB123/posicao-busca'
            self.assertEqual(client.get(path).status_code, 200)
            with client.session_transaction() as s:
                csrf = s['_csrf']
            form = dict(_csrf=csrf, submission_key=uuid4().hex, keyword='Suporte de tela',
                        result='organic', page='2', slot='7', cep='01000-000')
            for _ in range(2):
                self.assertEqual(client.post(path, data=form).status_code, 303)
            text = client.get(path+'?q=SUPORTE+DE+TELA').get_data(as_text=True)
            self.assertEqual(text.count('Página 2 · 7ª posição · Orgânico'), 1)
            for other in (path.replace('MLB123', 'MLB456'), path.replace(f'/{ids[0]}/', f'/{ids[1]}/')):
                self.assertIn('Nenhuma observação', client.get(other).get_data(as_text=True))
            self.assertIn('Nenhuma observação', client.get(path+'?q=outro').get_data(as_text=True))
            with m.banco() as conn:
                rows = m.consultar(conn, 'SELECT actor_id,cep FROM listing_search_observations WHERE conexao_id=%s',
                                   (ids[0],))
            self.assertEqual(rows, [dict(actor_id=-900000781, cep='01000000')])
        finally:
            with m.banco() as conn:
                for cid in ids:
                    m.executar(conn, 'DELETE FROM listing_search_observations WHERE conexao_id=%s', (cid,))
                    m.executar(conn, 'DELETE FROM anuncios WHERE conexao_id=%s', (cid,))
                    m.executar(conn, 'DELETE FROM conexoes WHERE id=%s', (cid,))
