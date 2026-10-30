import contextlib
import os
import time
import unittest
from unittest.mock import Mock, patch

from cryptography.fernet import Fernet
from ml_token_crypto import (PREFIX, KEY_ENV, ENABLE_ENV, seal_token, reveal_token,
                             migrate_tokens, validate_token_config, TokenEncryptionError)


class TokenCryptoTests(unittest.TestCase):
    def setUp(self):
        self.key=Fernet.generate_key().decode()
        self.config=patch.dict(os.environ,{KEY_ENV:self.key,ENABLE_ENV:'1'})
        self.config.start();self.addCleanup(self.config.stop)

    def test_authenticated_encryption_is_random_and_preserves_credentials(self):
        token='synthetic-ML-token-123'
        first,second=seal_token(token),seal_token(token)
        self.assertNotEqual(first,second)
        self.assertTrue(first.startswith(PREFIX));self.assertNotIn(token,first)
        self.assertEqual(reveal_token(first),token)
        self.assertEqual(seal_token(first),first)
        self.assertIsNone(reveal_token(None));self.assertIsNone(seal_token(None))

    def test_corruption_and_wrong_or_missing_key_fail_without_secret_in_error(self):
        encrypted=seal_token('synthetic-secret')
        for value in (encrypted[:-3]+'BAD',PREFIX+'corrupted'):
            with self.assertRaises(TokenEncryptionError) as caught:reveal_token(value)
            self.assertNotIn(value,str(caught.exception))
        with patch.dict(os.environ,{KEY_ENV:Fernet.generate_key().decode()}):
            with self.assertRaises(TokenEncryptionError):reveal_token(encrypted)
        with patch.dict(os.environ,{KEY_ENV:''}):
            with self.assertRaises(TokenEncryptionError):seal_token('new-token')
            with self.assertRaises(TokenEncryptionError):validate_token_config()
            with self.assertRaises(TokenEncryptionError):reveal_token(encrypted)

    def test_compatibility_phase_reads_both_formats_without_rewriting(self):
        encrypted=seal_token('synthetic-token')
        with patch.dict(os.environ,{ENABLE_ENV:'0'}):
            self.assertEqual(seal_token('legacy-token'),'legacy-token')
            self.assertEqual(reveal_token(encrypted),'synthetic-token')
            self.assertEqual(migrate_tokens(Mock()),0)
        self.assertEqual(reveal_token('legacy-token'),'legacy-token')

    def test_actual_cached_and_refreshed_token_paths_use_decrypted_values(self):
        from test_listing_details import main_function
        write=Mock()
        env=dict(time=time,reveal_token=reveal_token,seal_token=seal_token,
                 renovar=Mock(return_value=dict(access_token='new-access',refresh_token='new-refresh',expires_in=3600)),
                 banco=lambda:contextlib.nullcontext(None),executar=write,registrar_erro=Mock())
        token=main_function('token_atual',env)
        row=dict(id=1,expires_at=int(time.time())+7200,access_token=seal_token('cached'),refresh_token=seal_token('refresh'))
        self.assertEqual(token(row),'cached');env['renovar'].assert_not_called()
        row['expires_at']=0
        self.assertEqual(token(row),'new-access')
        params=write.call_args.args[2]
        self.assertEqual(reveal_token(params[0]),'new-access')
        self.assertEqual(reveal_token(params[1]),'new-refresh')
        self.assertNotEqual(params[0],'new-access')
        http=Mock();http.post.return_value.json.return_value={}
        renew=main_function('renovar',dict(requests=http,reveal_token=reveal_token,
            TOKEN_URL='https://example.test/token',CLIENT_ID='test',CLIENT_SECRET='test'))
        renew(seal_token('refresh'))
        self.assertEqual(http.post.call_args.kwargs['data']['refresh_token'],'refresh')


@unittest.skipUnless(os.getenv('KEIPER_TEST_DATABASE_URL'),'isolated PostgreSQL not configured')
class TokenMigrationDatabaseTests(unittest.TestCase):
    def test_bounded_idempotent_migration_preserves_values_and_refreshes(self):
        import psycopg2
        import uuid
        schema='token_crypto_'+uuid.uuid4().hex
        url=os.environ['KEIPER_TEST_DATABASE_URL']
        config={KEY_ENV:Fernet.generate_key().decode(),ENABLE_ENV:'1'}
        def bank():return psycopg2.connect(url,options='-c search_path='+schema)
        with psycopg2.connect(url) as conn:
            with conn.cursor() as cur:
                cur.execute('CREATE SCHEMA '+schema)
                cur.execute('CREATE TABLE '+schema+'.conexoes(id INT PRIMARY KEY,access_token TEXT,refresh_token TEXT)')
                cur.execute('INSERT INTO '+schema+".conexoes VALUES(1,'a1','r1'),(2,NULL,'r2'),(3,NULL,NULL)")
        try:
            with patch.dict(os.environ,config):
                self.assertEqual(migrate_tokens(bank,limit=1),1)
                self.assertEqual(migrate_tokens(bank),1)
                self.assertEqual(migrate_tokens(bank),0)
                with bank() as conn:
                    with conn.cursor() as cur:
                        cur.execute('SELECT id,access_token,refresh_token FROM conexoes ORDER BY id')
                        rows=cur.fetchall()
                        self.assertEqual([(i,reveal_token(a),reveal_token(r)) for i,a,r in rows],[(1,'a1','r1'),(2,None,'r2'),(3,None,None)])
                        self.assertTrue(all(v.startswith(PREFIX) for _,a,r in rows for v in (a,r) if v))
                        cur.execute('UPDATE conexoes SET access_token=%s,refresh_token=%s WHERE id=1',
                                    (seal_token('fresh-a'),seal_token('fresh-r')))
                self.assertEqual(migrate_tokens(bank),0)
                # Compatibility workers may briefly write plaintext while draining.
                with bank() as conn:
                    with conn.cursor() as cur:cur.execute("UPDATE conexoes SET access_token='draining-worker' WHERE id=1")
                self.assertEqual(migrate_tokens(bank),1)
                with bank() as conn:
                    with conn.cursor() as cur:
                        cur.execute('SELECT access_token,refresh_token FROM conexoes WHERE id=1');a,r=cur.fetchone()
                self.assertEqual(reveal_token(a),'draining-worker');self.assertEqual(reveal_token(r),'fresh-r')
        finally:
            with psycopg2.connect(url) as conn:
                with conn.cursor() as cur:cur.execute('DROP SCHEMA '+schema+' CASCADE')
