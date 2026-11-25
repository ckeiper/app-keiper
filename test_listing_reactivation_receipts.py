"""Exercise the real route and receipt transactions in isolated PostgreSQL."""
import os
import unittest
from unittest.mock import Mock

from flask import Flask
from listing_reactivation_routes import register_reactivation
from test_listing_reactivation_write import response, item


@unittest.skipUnless(os.getenv('KEIPER_TEST_DATABASE_URL'), 'isolated PostgreSQL not configured')
class ReactivationReceiptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ['DATABASE_URL'] = os.environ['KEIPER_TEST_DATABASE_URL']
        import main
        cls.m = main
        if main.scheduler.running:
            main.scheduler.shutdown(wait=False)
        main.iniciar_banco()

    def setUp(self):
        m = self.m
        with m.banco() as conn:
            self.cid = m.consultar(conn, """INSERT INTO conexoes(cliente,status,user_id)
                VALUES('Reactivation Receipt Test','ativa','7') RETURNING id""")[0]['id']
            m.executar(conn, """INSERT INTO anuncios(conexao_id,item_id,titulo,status,quantidade)
                VALUES(%s,'MLB1','Receipt Test','paused',10)""", (self.cid,))
        self.app = Flask(__name__)
        self.app.secret_key = 'test-only'
        self.get = Mock()
        self.put = Mock(return_value=response({}))
        register_reactivation(
            self.app, lambda f: f, lambda cid: cid == self.cid,
            m.banco, m.consultar, m.executar, lambda *args: args[-1],
            resolve_token=lambda shop: 'test-token', request_get=self.get, request_put=self.put,
        )
        self.client = self.app.test_client()
        with self.client.session_transaction() as session:
            session.update(tipo='admin', usuario_id=1, _csrf='csrf')
        self.path = f'/anuncios/{self.cid}/MLB1/reativacao'
        self.form = dict(_csrf='csrf', action='reativar_anuncio',
                         confirmar_reativacao='sim', request_key='r'*32)

    def tearDown(self):
        with self.m.banco() as conn:
            self.m.executar(conn, 'DELETE FROM anuncios WHERE conexao_id=%s', (self.cid,))
            self.m.executar(conn, 'DELETE FROM conexoes WHERE id=%s', (self.cid,))

    def test_repeated_confirmed_post_reuses_history_without_second_command(self):
        self.get.side_effect = [
            response({'id': 7}), item(), item('active'),
            response({'id': 7}), item('active'),
        ]
        for _ in range(2):
            result = self.client.post(self.path, data=self.form)
            self.assertEqual(result.status_code, 200)
            self.assertIn('Comparar antes e depois', result.text)
        self.put.assert_called_once()
        with self.m.banco() as conn:
            events = self.m.consultar(conn, 'SELECT id FROM listing_interventions WHERE conexao_id=%s', (self.cid,))
            receipts = self.m.consultar(conn, 'SELECT history_id FROM listing_reactivation_requests WHERE conexao_id=%s', (self.cid,))
        self.assertEqual(len(events), 1)
        self.assertEqual(receipts[0]['history_id'], events[0]['id'])

    def test_receipt_after_uncertain_send_recovers_by_reading_status(self):
        import requests
        self.put.side_effect = requests.Timeout()
        self.get.side_effect = [
            response({'id': 7}), item(), item(),
            response({'id': 7}), item('active'),
        ]
        self.assertEqual(self.client.post(self.path, data=self.form).status_code, 409)
        self.assertEqual(self.client.post(self.path, data=self.form).status_code, 200)
        self.put.assert_called_once()

    def test_preflight_rejection_does_not_become_reactivation_on_retry(self):
        self.get.side_effect = [response({'id': 7}), item('active')]
        self.assertEqual(self.client.post(self.path, data=self.form).status_code, 409)
        self.assertEqual(self.client.post(self.path, data=self.form).status_code, 409)
        self.put.assert_not_called()
        with self.m.banco() as conn:
            events = self.m.consultar(conn, 'SELECT id FROM listing_interventions WHERE conexao_id=%s', (self.cid,))
        self.assertEqual(events, [])

    def test_marketplace_rejection_cannot_be_reclassified_by_later_external_activation(self):
        self.get.side_effect = [response({'id': 7}), item()]
        self.put.return_value = response({'error': 'blocked'}, 403)
        self.assertEqual(self.client.post(self.path, data=self.form).status_code, 409)
        self.assertEqual(self.client.post(self.path, data=self.form).status_code, 409)
        self.put.assert_called_once()
        self.assertEqual(self.get.call_count, 2)
        with self.m.banco() as conn:
            events = self.m.consultar(conn, 'SELECT id FROM listing_interventions WHERE conexao_id=%s', (self.cid,))
        self.assertEqual(events, [])
