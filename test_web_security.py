"""Adversarial requests against production security hooks and real auth handlers."""
import contextlib
from functools import wraps
import hashlib
import html
import os
import re
import secrets
import time
import unittest
from unittest.mock import Mock, patch

from flask import Flask, request, session, redirect
from werkzeug.security import generate_password_hash, check_password_hash
from test_listing_details import main_function
from web_security import install_security, session_key, auth_attempt_allowed


class BrowserSecurityTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.secret_key = 'isolated-security-test-key'
        self.app.config['TESTING'] = True
        install_security(self.app)
        self.writes = Mock(return_value='saved')
        self.app.add_url_rule('/write', view_func=lambda:self.writes(), endpoint='write', methods=['POST'])
        self.app.add_url_rule('/form', view_func=lambda: '''<html><head></head><body>
            <form method="post" action="/write"><input name="name"></form>
            <form method="POST" enctype="multipart/form-data"></form>
            <form method="get"></form><form method="post" action="https://other.test/write"></form>
            <script>let literal="<form method='post'>";</script></body></html>''')
        self.client = self.app.test_client()

    def token(self):
        response = self.client.get('/form')
        with self.client.session_transaction() as state:
            return response, state['_csrf']

    def test_forms_fetch_and_security_headers(self):
        response, token = self.token()
        self.assertEqual(response.text.count("name='_csrf'"), 2)
        self.assertIn('X-CSRF-Token', response.text)
        self.assertIn('let literal="<form method=\'post\'>";', response.text)
        self.assertIn('Secure', response.headers['Set-Cookie'])
        self.assertIn('HttpOnly', response.headers['Set-Cookie'])
        self.assertIn('SameSite=Lax', response.headers['Set-Cookie'])
        for key, value in {'X-Frame-Options':'DENY', 'X-Content-Type-Options':'nosniff',
                           'Cache-Control':'no-store', 'Referrer-Policy':'strict-origin-when-cross-origin'}.items():
            self.assertEqual(response.headers[key], value)
        self.assertEqual(self.client.post('/write', data={'_csrf':token}).status_code, 200)
        self.assertEqual(self.client.post('/write', headers={'X-CSRF-Token':token}).status_code, 200)

    def test_missing_forged_unicode_cross_browser_and_cross_origin_tokens_never_write(self):
        _, token = self.token()
        for data in ({}, {'_csrf':'forged'}, {'_csrf':'inválido'}):
            self.assertEqual(self.client.post('/write', data=data).status_code, 400)
        other = self.app.test_client()
        self.assertEqual(other.post('/write', data={'_csrf':token}).status_code, 400)
        for headers in ({'Origin':'https://evil.test'}, {'Sec-Fetch-Site':'cross-site'}):
            self.assertEqual(self.client.post('/write', data={'_csrf':token}, headers=headers).status_code, 400)
        self.writes.assert_not_called()

    def test_body_limit_and_no_token_in_external_form(self):
        self.assertEqual(self.client.post('/write', data=b'x'*(10*1024*1024+1)).status_code,413)
        response,_ = self.token()
        self.assertIn('action="https://other.test/write"></form>', response.text)

    def test_production_hosts_and_no_default_key(self):
        with patch.dict(os.environ, {'RENDER':'true','SECRET_KEY':'troque-esta-chave'}):
            with self.assertRaises(RuntimeError): session_key()
            app=Flask('production');app.secret_key='private-test-key';install_security(app)
            app.add_url_rule('/',view_func=lambda:'ok')
            client=app.test_client()
            self.assertEqual(client.get('/',base_url='https://evil.test').status_code,400)
            response=client.get('/',base_url='https://app.keiperconsultoria.com.br')
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.headers['Strict-Transport-Security'],'max-age=31536000')


class AuthRouteSecurityTests(unittest.TestCase):
    def setUp(self):
        self.app=Flask('auth-test');self.app.secret_key='isolated-auth-test-key'
        install_security(self.app)
        self.query=Mock(return_value=[dict(id=7,username='owner',nome='Owner',tipo='admin',
                          conexao_id=None,auth_version=1,senha_hash=generate_password_hash('safe-test-password'))])
        self.write=Mock()
        self.allowed=Mock(return_value=True)
        self.env=dict(app=self.app,request=request,session=session,redirect=redirect,
                      time=time,secrets=secrets,hashlib=hashlib,esc=html.escape,wraps=wraps,
                      check_password_hash=check_password_hash,generate_password_hash=generate_password_hash,
                      DUMMY_PASSWORD_HASH=generate_password_hash('dummy-test-password'),
                      auth_attempt_allowed=self.allowed,banco=lambda:contextlib.nullcontext(None),
                      consultar=self.query,executar=self.write,
                      pagina=lambda title,body:body,img_logo=lambda size:'')
        for name in ['login_required','admin_required','form_login','login','usuarios_excluir','usuarios_criar','redefinir']:
            fn=main_function(name,self.env)
            if name=='login': self.app.add_url_rule('/login',view_func=fn,methods=['GET','POST'])
            if name=='usuarios_excluir': self.app.add_url_rule('/usuarios/excluir/<int:uid>',view_func=self.env['admin_required'](fn),methods=['GET','POST'])
            if name=='usuarios_criar': self.app.add_url_rule('/usuarios/criar',view_func=self.env['admin_required'](fn),methods=['POST'])
            if name=='redefinir': self.app.add_url_rule('/redefinir/<token>',view_func=fn,methods=['GET','POST'])
        self.client=self.app.test_client()

    def prepare(self):
        self.client.get('/login')
        with self.client.session_transaction() as state:return state['_csrf']

    def test_login_rotates_session_and_blocked_attempt_does_not_check_database(self):
        token=self.prepare()
        with self.client.session_transaction() as state: state['untrusted']='old'
        response=self.client.post('/login',data=dict(username='owner',senha='safe-test-password',_csrf=token))
        self.assertEqual(response.location,'/painel')
        with self.client.session_transaction() as state:
            self.assertNotIn('untrusted',state);self.assertTrue(state.permanent)
        token=self.prepare();self.allowed.return_value=False;self.query.reset_mock()
        self.assertEqual(self.client.post('/login',data=dict(username='owner',senha='x',_csrf=token)).status_code,429)
        self.query.assert_not_called()

    def test_public_domain_form_login_preserves_browser_origin(self):
        base = 'https://app.keiperconsultoria.com.br'
        response = self.client.get('/login', base_url=base)
        # This policy preserves Origin on same-origin browser form navigations.
        self.assertEqual(response.headers['Referrer-Policy'], 'strict-origin-when-cross-origin')
        token = re.search(r"name='_csrf' value='([^']+)'", response.text).group(1)
        response = self.client.post('/login', base_url=base,
            headers={'Origin':base, 'Sec-Fetch-Site':'same-origin'},
            data={'username':'owner', 'senha':'safe-test-password', '_csrf':token})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, '/painel')

    def test_opaque_origin_remains_rejected_even_with_valid_form_token(self):
        token = self.prepare()
        response = self.client.post('/login', headers={'Origin':'null'},
            data={'username':'owner', 'senha':'safe-test-password', '_csrf':token})
        self.assertEqual(response.status_code, 400)
        self.query.assert_not_called()

    def test_user_deletion_get_confirms_post_requires_token_and_admin(self):
        token=self.prepare()
        with self.client.session_transaction() as state:state.update(usuario_id=7,tipo='admin')
        self.assertIn('Confirmar exclusão',self.client.get('/usuarios/excluir/8').text)
        self.write.assert_not_called()
        self.assertEqual(self.client.post('/usuarios/excluir/8').status_code,400)
        self.write.assert_not_called()
        self.assertEqual(self.client.post('/usuarios/excluir/8',data={'_csrf':token}).status_code,302)
        self.assertIn('DELETE FROM usuarios',self.write.call_args.args[1])

    def test_new_weak_password_is_rejected_without_write(self):
        token=self.prepare()
        with self.client.session_transaction() as state:state.update(usuario_id=7,tipo='admin')
        response=self.client.post('/usuarios/criar',data=dict(username='new',senha='short',_csrf=token))
        self.assertEqual(response.status_code,302);self.write.assert_not_called()

    def test_consumed_reset_token_cannot_be_reused(self):
        token=self.prepare()
        self.query.side_effect=[[dict(expira_em=int(time.time())+30,usuario_id=7)], [{'id':7}], []]
        response=self.client.post('/redefinir/synthetic',data=dict(senha='new-safe-password',_csrf=token))
        self.assertEqual(response.status_code,400);self.write.assert_not_called()


class RateLimitTests(unittest.TestCase):
    def test_shared_atomic_counters_hash_identities_and_reject_threshold(self):
        app=Flask(__name__)
        execute=Mock();execute.return_value.fetchone.side_effect=[(21,), (1,)]
        with app.test_request_context('/'):
            self.assertFalse(auth_attempt_allowed(lambda:contextlib.nullcontext(None),execute,'login','PrivateUser'))
        calls=execute.call_args_list
        self.assertIn('ON CONFLICT',calls[1].args[1])
        self.assertNotIn('PrivateUser',str(calls))


@unittest.skipUnless(os.getenv('KEIPER_TEST_DATABASE_URL'), 'isolated PostgreSQL not configured')
class PersistentRateLimitTests(unittest.TestCase):
    def test_schema_idempotence_and_concurrent_limit_across_connections(self):
        import uuid
        import psycopg2
        from concurrent.futures import ThreadPoolExecutor
        from web_security import init_security_schema
        app = Flask('persistent-rate-test')
        scope = 'test-' + uuid.uuid4().hex
        bank = lambda: psycopg2.connect(os.environ['KEIPER_TEST_DATABASE_URL'])
        def execute(conn, sql, params=None):
            cur = conn.cursor(); cur.execute(sql, params or ()); return cur
        with bank() as conn:
            init_security_schema(conn, execute)
            init_security_schema(conn, execute)
        def attempt(_):
            with app.test_request_context('/'):
                return auth_attempt_allowed(bank, execute, scope, 'synthetic-user')
        with ThreadPoolExecutor(max_workers=5) as pool:
            results = list(pool.map(attempt, range(25)))
        self.assertEqual(sum(results), 20)
        key = hashlib.sha256((scope + ':identity:synthetic-user').encode()).hexdigest()
        with bank() as conn:
            row = execute(conn, 'SELECT attempts FROM auth_rate_limits WHERE bucket=%s', (key,)).fetchone()
        self.assertEqual(row[0], 25)
