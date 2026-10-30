"""Database-backed session fixture; used only with the disposable test database."""
from contextlib import contextmanager
import os


@contextmanager
def database_session(client):
    import main
    if not os.getenv('KEIPER_TEST_DATABASE_URL') or main.DATABASE_URL != os.environ['KEIPER_TEST_DATABASE_URL']:
        raise RuntimeError('Session fixtures require the isolated test database.')
    with client.session_transaction() as state:
        yield state
        if 'usuario_id' not in state:
            return
        uid = state['usuario_id']
        uid = uid if uid < 0 else -900000000 - uid
        with main.banco() as conn:
            rows = main.consultar(conn, '''INSERT INTO usuarios(id,username,senha_hash,tipo,conexao_id)
                VALUES(%s,%s,'synthetic-session-fixture',%s,%s)
                ON CONFLICT(id) DO UPDATE SET tipo=EXCLUDED.tipo,conexao_id=EXCLUDED.conexao_id
                RETURNING auth_version''', (uid, 'session-fixture-' + str(-uid), state.get('tipo','cliente'),state.get('conexao_id')))
        state.update(usuario_id=uid,auth_version=rows[0]['auth_version'])
