import contextlib
import unittest
from unittest.mock import Mock

import requests
from flask import Flask

from listing_reactivation_routes import register_reactivation
from listing_reactivation_write import reactivate
from test_listing_reactivation import fixture


def response(payload, status=200):
    return Mock(status_code=status, json=Mock(return_value=payload))


def item(status='paused', seller=7, codes=None):
    return response(dict(id='MLB1', seller_id=seller, site_id='MLB',
                         status=status, sub_status=codes or []))


class ReactivationWriteTests(unittest.TestCase):
    def test_owned_pause_updates_only_status_and_verifies(self):
        get = Mock(side_effect=[response({'id': 7}), item(), item('active')])
        put = Mock(return_value=response({}))
        message, status = reactivate('test-token', 7, 'MLB1', get, put)
        self.assertEqual(status, 200)
        self.assertIn('confirmado', message)
        put.assert_called_once()
        self.assertEqual(put.call_args.args[0], 'https://api.mercadolibre.com/items/MLB1')
        self.assertEqual(put.call_args.kwargs['json'], {'status': 'active'})
        self.assertEqual(get.call_count, 3)

    def test_ineligible_or_wrong_seller_never_writes(self):
        for snapshot in (item('closed'), item(seller=8), item(codes=['out_of_stock'])):
            with self.subTest(snapshot=snapshot):
                get = Mock(side_effect=[response({'id': 7}), snapshot])
                put = Mock()
                self.assertEqual(reactivate('test-token', 7, 'MLB1', get, put)[1], 409)
                put.assert_not_called()

    def test_timeout_is_verified_without_repeating_write(self):
        get = Mock(side_effect=[response({'id': 7}), item(), item()])
        put = Mock(side_effect=requests.Timeout())
        self.assertIn('ainda não confirmou', reactivate('test-token', 7, 'MLB1', get, put)[0])
        put.assert_called_once()
        self.assertEqual(get.call_count, 3)

    def test_rejection_shows_reason_without_token(self):
        get = Mock(side_effect=[response({'id': 7}), item()])
        put = Mock(return_value=response({'message': 'Restrição test-token', 'error': 'blocked'}, 403))
        message, status = reactivate('test-token', 7, 'MLB1', get, put)
        self.assertEqual(status, 409)
        self.assertIn('blocked', message)
        self.assertNotIn('test-token', message)

    def test_route_requires_confirmation_and_uses_verified_connection(self):
        app = Flask(__name__)
        app.secret_key = 'test'
        get = Mock(side_effect=[response({'id': 7}), item(), item('active')])
        put = Mock(return_value=response({}))
        data = [[fixture()['shop']], [{'n': 0}], [], []]
        query = Mock(side_effect=data + data + [[{'user_id': 7}]])
        register_reactivation(
            app, lambda f: f, lambda cid: cid == 7, lambda: contextlib.nullcontext(None),
            query, Mock(), lambda *args: args[-1], resolve_token=lambda shop: 'test-token',
            request_get=get, request_put=put,
        )
        client = app.test_client()
        with client.session_transaction() as session:
            session.update(tipo='admin', usuario_id=1, _csrf='csrf')
        path = '/anuncios/7/MLB1/reativacao'
        form = {'_csrf': 'csrf', 'action': 'reativar_anuncio'}
        self.assertEqual(client.post(path, data=form).status_code, 400)
        put.assert_not_called()
        result = client.post(path, data={**form, 'confirmar_reativacao': 'sim'})
        self.assertEqual(result.status_code, 200)
        self.assertIn('Status confirmado', result.get_data(as_text=True))
        put.assert_called_once()
