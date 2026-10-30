import os
import secrets
import time
import unittest
from unittest.mock import Mock,patch

from cryptography.fernet import Fernet
from flask import Flask,request,session,redirect
import pyotp
from account_mfa import (KEY_ENV, matching_step, encrypt_seed, decrypt_seed,
                         complete_login, issue_challenge, verify_challenge,
                         register_mfa, recovery_hash, MfaConfigurationError)


class MfaUnitTests(unittest.TestCase):
    def test_totp_window_and_replay_rejection(self):
        seed=pyotp.random_base32();now=1800000000
        code=pyotp.TOTP(seed).at(now)
        step=matching_step(seed,code,now=now)
        self.assertEqual(step,now//30)
        self.assertIsNone(matching_step(seed,code,last=step,now=now))
        self.assertIsNone(matching_step(seed,code,now=now+90))
        for bad in ('', '１２３４５６', 'a12345', '1234567'):
            self.assertIsNone(matching_step(seed,bad,now=now))

    def test_seed_encryption_uses_independent_key_and_rejects_corruption(self):
        seed=pyotp.random_base32()
        with patch.dict(os.environ,{KEY_ENV:Fernet.generate_key().decode()}):
            encrypted=encrypt_seed(seed)
            self.assertNotIn(seed,encrypted);self.assertEqual(decrypt_seed(encrypted),seed)
            with self.assertRaises(MfaConfigurationError):decrypt_seed(encrypted+'bad')
        with patch.dict(os.environ,{KEY_ENV:''}):
            with self.assertRaises(MfaConfigurationError):encrypt_seed(seed)

    def test_password_verified_challenge_does_not_grant_full_session(self):
        from contextlib import nullcontext
        app=Flask('pending-only');app.secret_key='test-pending-only'
        user=dict(id=7,auth_version=1,mfa_enabled=True)
        query=Mock(return_value=[user]);write=Mock()
        with app.test_request_context('/'):
            session.update(usuario_id=99,tipo='admin')
            self.assertTrue(issue_challenge(user,lambda:nullcontext(None),query,write))
            self.assertNotIn('usuario_id',session);self.assertNotIn('tipo',session)
            self.assertEqual(session['mfa_pending']['uid'],7)


@unittest.skipUnless(os.getenv('KEIPER_TEST_DATABASE_URL'),'isolated PostgreSQL not configured')
class MfaIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ['DATABASE_URL']=os.environ['KEIPER_TEST_DATABASE_URL']
        import main
        cls.m=main
        if main.scheduler.running:main.scheduler.shutdown(wait=False)
        cls.m.app.testing=True

    def setUp(self):
        from werkzeug.security import generate_password_hash
        self.config=patch.dict(os.environ,{KEY_ENV:Fernet.generate_key().decode()})
        self.config.start();self.addCleanup(self.config.stop)
        self.username='mfa-test-'+secrets.token_hex(6);self.password='synthetic-password-123'
        with self.m.banco() as conn:
            self.uid=self.m.consultar(conn,'''INSERT INTO usuarios(username,senha_hash,tipo)
                VALUES(%s,%s,'admin') RETURNING id''',(self.username,generate_password_hash(self.password)))[0]['id']
        self.client=self.m.app.test_client()
        self.login_password()

    def tearDown(self):
        with self.m.banco() as conn:
            self.m.executar(conn,'DELETE FROM usuarios WHERE id=%s',(self.uid,))

    def row(self):
        with self.m.banco() as conn:
            return self.m.consultar(conn,'SELECT * FROM usuarios WHERE id=%s',(self.uid,))[0]

    def post(self,path,data,client=None):
        c=client or self.client
        with c.session_transaction() as state:token=state['_csrf']
        return c.post(path,data=dict(_csrf=token,**data))

    def login_password(self,client=None):
        c=client or self.client;c.get('/login')
        return self.post('/login',dict(username=self.username,senha=self.password),c)

    def begin(self):
        response=self.post('/seguranca',dict(acao='iniciar',senha=self.password))
        self.assertEqual(response.status_code,200)
        self.seed=decrypt_seed(self.row()['mfa_pending_secret'])
        self.assertIn(self.seed,response.text)
        self.assertIn('<svg',response.text)
        return response

    def enable(self):
        self.begin()
        response=self.post('/seguranca',dict(acao='confirmar',codigo=pyotp.TOTP(self.seed).now()))
        self.assertEqual(response.status_code,200)
        import re
        self.codes=re.findall(r"class='recovery-code'>([^<]+)</code>",response.text)
        self.assertEqual(len(self.codes),10)
        self.assertTrue(self.row()['mfa_enabled'])
        return response

    def challenge(self,client=None):
        c=client or self.client;c.get('/logout')
        response=self.login_password(c)
        self.assertEqual(response.location,'/login/verificar')
        with c.session_transaction() as state:
            self.assertNotIn('usuario_id',state);self.assertNotIn('tipo',state)
        self.assertEqual(c.get('/painel').location,'/login')
        c.get('/login/verificar')
        return c.get_cookie('session').value

    def test_enrollment_requires_password_confirmation_and_same_browser(self):
        response=self.post('/seguranca',dict(acao='iniciar',senha='wrong'))
        self.assertIsNone(self.row()['mfa_pending_secret'])
        self.begin()
        other=self.m.app.test_client();self.login_password(other)
        self.assertNotIn(self.seed,other.get('/seguranca').text)
        self.assertNotIn('mfa-manual-key',other.get('/seguranca').text)
        self.assertFalse(self.row()['mfa_enabled'])
        self.assertNotIn('mfa_pending_secret',self.client.get_cookie('session').value)
        self.post('/seguranca',dict(acao='confirmar',codigo='invalid'))
        self.assertFalse(self.row()['mfa_enabled'])

    def test_recovery_codes_are_hashed_single_use_and_pending_cookie_cannot_replay(self):
        old_cookie=self.client.get_cookie('session').value
        self.enable()
        stale=self.m.app.test_client();stale.set_cookie('session',old_cookie)
        self.assertEqual(stale.get('/status').location,'/login')
        with self.m.banco() as conn:
            rows=self.m.consultar(conn,'SELECT code_hash FROM auth_mfa_recovery_codes WHERE usuario_id=%s',(self.uid,))
        self.assertEqual(len(rows),10)
        self.assertNotIn(self.codes[0],str(rows))
        pending_cookie=self.challenge()
        self.assertNotIn(self.codes[0],self.client.get('/seguranca').text)
        response=self.post('/login/verificar',dict(codigo=self.codes[0]))
        self.assertEqual(response.location,'/painel')
        self.assertEqual(self.client.get('/status').status_code,200)
        self.client.set_cookie('session',pending_cookie)
        response=self.post('/login/verificar',dict(codigo=self.codes[1]))
        self.assertNotEqual(response.location,'/painel')
        with self.client.session_transaction() as state:self.assertNotIn('usuario_id',state)
        self.challenge()
        response=self.post('/login/verificar',dict(codigo=self.codes[0]))
        self.assertNotEqual(response.location,'/painel')

    def test_totp_reuse_five_attempt_limit_and_challenge_version_are_enforced(self):
        self.enable();self.challenge()
        with self.m.banco() as conn:
            self.m.executar(conn,'UPDATE usuarios SET mfa_last_step=-1 WHERE id=%s',(self.uid,))
        code=pyotp.TOTP(self.seed).now()
        response=self.post('/login/verificar',dict(codigo=code))
        self.assertEqual(response.location,'/painel')
        self.challenge()
        self.assertNotEqual(self.post('/login/verificar',dict(codigo=code)).location,'/painel')
        self.challenge()
        for _ in range(5):self.post('/login/verificar',dict(codigo='invalid'))
        self.assertNotEqual(self.post('/login/verificar',dict(codigo=self.codes[0])).location,'/painel')
        self.challenge()
        with self.m.banco() as conn:self.m.executar(conn,'UPDATE usuarios SET auth_version=auth_version+1 WHERE id=%s',(self.uid,))
        self.assertNotEqual(self.post('/login/verificar',dict(codigo=self.codes[0])).location,'/painel')

    def test_disabling_requires_password_and_factor_and_revokes_sessions(self):
        self.enable()
        active=self.client.get_cookie('session').value
        self.post('/seguranca',dict(acao='desativar',senha='wrong',codigo=self.codes[0]))
        self.assertTrue(self.row()['mfa_enabled'])
        self.post('/seguranca',dict(acao='desativar',senha=self.password,codigo='invalid'))
        self.assertTrue(self.row()['mfa_enabled'])
        with patch.dict(os.environ,{KEY_ENV:''}):
            response=self.post('/seguranca',dict(acao='desativar',senha=self.password,codigo=self.codes[0]))
        self.assertEqual(response.location,'/login');self.assertFalse(self.row()['mfa_enabled'])
        self.client.set_cookie('session',active)
        self.assertEqual(self.client.get('/status').location,'/login')
        self.assertEqual(self.login_password().location,'/painel')


    def test_two_concurrent_challenges_cannot_reuse_the_same_recovery_code(self):
        from concurrent.futures import ThreadPoolExecutor
        self.enable()
        pending=[]
        for client in (self.client,self.m.app.test_client()):
            self.challenge(client)
            with client.session_transaction() as state:pending.append(dict(state['mfa_pending']))
        def verify(item):
            return verify_challenge(item,self.codes[0],self.m.banco,self.m.consultar,self.m.executar)
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(verify,pending))
        self.assertEqual(sum(result is not None for result in results),1)
