import contextlib
import unittest
from unittest.mock import Mock

from flask import Flask
from listing_workspace import GROUPS, navigation, register


class ListingWorkspaceTests(unittest.TestCase):
    def test_shared_navigation_follows_listing_and_store(self):
        for group, name, actions in GROUPS:
            for target, label, restricted in actions:
                path = target.format(cid=7, item='MLB123').split('?')[0]
                html = navigation(7, 'MLB123', path, True)
                self.assertIn('href="/anuncios/7/MLB123?aba='+group+'" aria-current', html)
                self.assertIn(label, html)
                self.assertNotIn('/anuncios/8/', html)

    def test_client_navigation_and_untrusted_title(self):
        html = navigation(7, 'MLB123', '/diagnostico/7/MLB123', False, title='<script>')
        self.assertIn('&lt;script&gt;', html)
        self.assertNotIn('Metas de vendas</a>', html)
        self.assertEqual(navigation(7, '../invalid', '/', True), '')

    def test_entry_checks_store_ownership_and_tab(self):
        app = Flask(__name__)
        app.secret_key = 'test'
        query = Mock(return_value=[dict(cliente='Loja', titulo='Produto')])
        register(app, lambda f: f, lambda cid: cid == 7,
                 lambda: contextlib.nullcontext(None), query, lambda *args: args[-1])
        client = app.test_client()
        self.assertEqual(client.get('/anuncios/8/MLB123').status_code, 403)
        self.assertEqual(client.get('/anuncios/7/MLB123?aba=bad').status_code, 404)
        query.assert_not_called()
        response = client.get('/anuncios/7/MLB123?aba=historico')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Histórico de alterações', response.text)
        self.assertEqual(query.call_args.args[2], (7, 'MLB123'))
        query.return_value = []
        self.assertEqual(client.get('/anuncios/7/MLB999').status_code, 404)
