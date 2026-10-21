"""Replay real signed cookies after account changes, including role-change reversal."""
from contextlib import nullcontext
import os
import unittest
from unittest.mock import Mock

from flask import Flask, session
from session_security import init_session_schema, install_session_guard
from web_security import install_security


class SessionGuardTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask('session-revocation')
        self.app.secret_key = 'isolated-session-revocation-test'
        self.user = dict(id=7,tipo='admin',conexao_id=None,auth_version=1)
        self.load = Mock(side_effect=lambda uid: dict(self.user) if self.user else None)
        install_session_guard(self.app,self.load)
        install_security(self.app)
        self.writes = Mock(return_value='saved')
        self.app.add_url_rule('/private',endpoint='private',view_func=lambda:'private',methods=['GET'])
        self.app.add_url_rule('/save',endpoint='save',view_func=lambda:self.writes(),methods=['POST'])
        self.app.add_url_rule('/login',endpoint='login',view_func=lambda:'login',methods=['GET','POST'])
        self.client=self.app.test_client()
        with self.client.session_transaction() as state:
            state.update(usuario_id=7,tipo='admin',conexao_id=None,auth_version=1,_csrf='test-token')
        self.cookie=self.client.get_cookie('session').value

    def replay(self,**change):
        self.user.update(change)
        self.client.set_cookie('session',self.cookie)
        return self.client.get('/private')

    def test_active_session_checks_database_on_every_request(self):
        for _ in range(2):self.assertEqual(self.client.get('/private').status_code,200)
        self.assertEqual(self.load.call_count,2)

    def test_version_change_rejects_replayed_cookie_on_multiple_browsers(self):
        self.user['auth_version']=2
        for client in (self.client,self.app.test_client()):
            client.set_cookie('session',self.cookie)
            response=client.get('/private')
            self.assertEqual(response.location,'/login')
            with client.session_transaction() as state:self.assertNotIn('usuario_id',state)

    def test_deleted_user_and_changed_permissions_reject_old_cookie(self):
        for changes in ({'tipo':'cliente'},{'conexao_id':88}):
            self.user=dict(id=7,tipo='admin',conexao_id=None,auth_version=1)
            self.assertEqual(self.replay(**changes).location,'/login')
        self.user=None;self.client.set_cookie('session',self.cookie)
        self.assertEqual(self.client.get('/private').location,'/login')

    def test_legacy_sessions_require_login_but_public_login_is_available(self):
        with self.client.session_transaction() as state:state.pop('auth_version')
        self.assertEqual(self.client.get('/private').location,'/login')
        self.assertEqual(self.client.get('/login').status_code,200)

    def test_revoked_write_never_runs_even_with_previous_valid_csrf(self):
        self.user['auth_version']=2
        response=self.client.post('/save',data={'_csrf':'test-token'})
        self.assertEqual(response.location,'/login');self.writes.assert_not_called()

    def test_database_failure_does_not_grant_access_or_destroy_valid_session(self):
        self.load.side_effect=RuntimeError('synthetic failure')
        self.assertEqual(self.client.get('/private').status_code,503)
        with self.client.session_transaction() as state:self.assertEqual(state['usuario_id'],7)
        self.assertEqual(self.client.get('/login').status_code,200)


@unittest.skipUnless(os.getenv('KEIPER_TEST_DATABASE_URL'),'isolated PostgreSQL not configured')
class SessionRevisionDatabaseTests(unittest.TestCase):
    def test_password_role_store_changes_and_reversal_revoke_sessions(self):
        import psycopg2
        from psycopg2.extras import RealDictCursor
        url=os.environ['KEIPER_TEST_DATABASE_URL']
        with psycopg2.connect(url) as conn:
            def execute(conn,sql,params=None):
                cur=conn.cursor(cursor_factory=RealDictCursor);cur.execute(sql,params or ());return cur
            # Use an isolated schema so this test cannot mutate other fixtures.
            execute(conn,'CREATE SCHEMA session_revision_fixture')
            try:
                execute(conn,'SET LOCAL search_path TO session_revision_fixture')
                execute(conn,'CREATE TABLE usuarios(id INT PRIMARY KEY,senha_hash TEXT,tipo TEXT,conexao_id INT,nome TEXT)')
                init_session_schema(conn,execute);init_session_schema(conn,execute)
                execute(conn,"INSERT INTO usuarios VALUES(7,'first-password-hash','admin',NULL,'Owner',1)")
                def version():return execute(conn,'SELECT auth_version FROM usuarios WHERE id=7').fetchone()['auth_version']
                self.assertEqual(version(),1)
                execute(conn,"UPDATE usuarios SET nome='Other name' WHERE id=7")
                execute(conn,"UPDATE usuarios SET tipo='admin' WHERE id=7")
                self.assertEqual(version(),1)
                for expected,sql in enumerate([
                    "UPDATE usuarios SET senha_hash='changed-hash' WHERE id=7",
                    "UPDATE usuarios SET tipo='cliente' WHERE id=7",
                    "UPDATE usuarios SET tipo='admin' WHERE id=7",
                    "UPDATE usuarios SET conexao_id=22 WHERE id=7",
                    "UPDATE usuarios SET conexao_id=NULL WHERE id=7"],2):
                    execute(conn,sql);self.assertEqual(version(),expected)
            finally:
                execute(conn,'SET LOCAL search_path TO public')
                execute(conn,'DROP SCHEMA session_revision_fixture CASCADE')


@unittest.skipUnless(os.getenv('KEIPER_TEST_DATABASE_URL'),'isolated PostgreSQL not configured')
class SessionLifecycleIntegrationTests(unittest.TestCase):
    def test_real_login_password_change_relogin_and_deletion(self):
        import main
        import secrets
        from werkzeug.security import generate_password_hash
        username='session-lifecycle-'+secrets.token_hex(8)
        password='isolated-password-123'
        if main.scheduler.running:main.scheduler.shutdown(wait=False)
        with main.banco() as conn:
            uid=main.consultar(conn, '''INSERT INTO usuarios(username,senha_hash,tipo)
                VALUES(%s,%s,'admin') RETURNING id''',(username,generate_password_hash(password)))[0]['id']
        client=main.app.test_client()
        def login(secret):
            client.get('/login')
            with client.session_transaction() as state:token=state['_csrf']
            response=client.post('/login',data=dict(username=username,senha=secret,_csrf=token))
            self.assertEqual(response.status_code,302)
            self.assertEqual(client.get('/status').status_code,200)
        try:
            login(password)
            original_cookie=client.get_cookie('session').value
            new_password='new-isolated-password-456'
            with main.banco() as conn:
                main.executar(conn,'UPDATE usuarios SET senha_hash=%s WHERE id=%s',(generate_password_hash(new_password),uid))
            client.set_cookie('session',original_cookie)
            self.assertEqual(client.get('/status').location,'/login')
            login(new_password)
            current_cookie=client.get_cookie('session').value
            # Reverting the account permissions must not revive an old cookie.
            with main.banco() as conn:
                main.executar(conn,"UPDATE usuarios SET tipo='cliente' WHERE id=%s",(uid,))
                main.executar(conn,"UPDATE usuarios SET tipo='admin' WHERE id=%s",(uid,))
            client.set_cookie('session',current_cookie)
            self.assertEqual(client.get('/status').location,'/login')
            login(new_password)
            with main.banco() as conn:main.executar(conn,'DELETE FROM usuarios WHERE id=%s',(uid,))
            self.assertEqual(client.get('/status').location,'/login')
        finally:
            with main.banco() as conn:main.executar(conn,'DELETE FROM usuarios WHERE id=%s',(uid,))
