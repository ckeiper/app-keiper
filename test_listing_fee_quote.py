import contextlib
import unittest
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
from functools import wraps
from unittest.mock import Mock
import requests
from flask import Flask, session, redirect
from web_security import install_security
from listing_fee_quote import quote, render, register, LOGISTICS

NOW = datetime(2026, 10, 26, 18, 45, tzinfo=timezone.utc)


def item():
    return dict(id='MLB100', seller_id=123, site_id='MLB', currency_id='BRL', price=100,
                variations=[], category_id='MLB200', listing_type_id='gold_special',
                shipping=dict(logistic_type='fulfillment', mode='me2'))


def fee():
    return dict(currency_id='BRL', listing_type_id='gold_special', sale_fee_amount=15.25,
                sale_fee_details=dict(fixed_fee=5, financing_add_on_fee=23))


def requester(values=None):
    return Mock(side_effect=[Mock(status_code=200, json=Mock(return_value=v))
                             for v in (values if values is not None else [dict(id=123), item(), [fee()]])])


class FeeQuoteTests(unittest.TestCase):
    def test_exact_context_total_and_bounded_read_only_requests(self):
        values = [dict(id=123), item(), [fee()]]; before = deepcopy(values); get = requester(values)
        r = quote('secret-token', 123, 'MLB100', get, NOW)
        self.assertEqual(r['state'], 'quoted'); self.assertEqual(r['total'], Decimal('15.25'))
        self.assertEqual(r['fixed'], Decimal('5')); self.assertNotIn('financing', r)
        self.assertEqual(values, before); self.assertEqual(get.call_count, 3)
        self.assertEqual(get.call_args.args[0], 'https://api.mercadolibre.com/sites/MLB/listing_prices')
        self.assertEqual(get.call_args.kwargs['params'], dict(price='100.00', category_id='MLB200',
            listing_type_id='gold_special', currency_id='BRL', logistic_type='fulfillment',
            shipping_mode='me2', quantity=1, channel='marketplace'))
        for call in get.call_args_list:
            self.assertEqual(call.kwargs['timeout'], (3, 8)); self.assertFalse(call.kwargs['allow_redirects'])

    def test_account_ownership_blocks_before_item_or_quote_and_no_token_leak(self):
        for account in (dict(id=124), {}, [], None):
            get = requester([account]); r = quote('secret-token', 123, 'MLB100', get, NOW)
            self.assertEqual(r['state'], 'unknown'); self.assertEqual(get.call_count, 1)
            self.assertNotIn('secret-token', str(r))
        for changes in (dict(seller_id=124), dict(id='MLB999')):
            value = item(); value.update(changes); get = requester([dict(id=123), value])
            self.assertEqual(quote('secret-token', 123, 'MLB100', get)['state'], 'unknown')
            self.assertEqual(get.call_count, 2)
        for token, seller, identifier in [(None, 123, 'MLB100'), ('secret', None, 'MLB100'),
                                          ('secret', True, 'MLB100'), ('secret', 123, '../../users/me')]:
            get = Mock(); self.assertEqual(quote(token, seller, identifier, get)['state'], 'unknown'); get.assert_not_called()

    def test_incomplete_variant_currency_and_logistics_do_not_quote(self):
        changes = [dict(site_id='MLA'), dict(currency_id='ARS'), dict(price=None), dict(price=0),
                   dict(price=True), dict(price=float('nan')), dict(price='0.001'), dict(category_id='MLA200'),
                   dict(listing_type_id='unknown'), dict(variations=[dict(id=1)]), dict(variations=None),
                   dict(shipping=None), dict(shipping={}), dict(shipping=dict(logistic_type='fulfillment', mode='custom'))]
        for patch in changes:
            value = item(); value.update(patch); get = requester([dict(id=123), value])
            r = quote('secret', 123, 'MLB100', get)
            self.assertEqual(r['state'], 'unknown', patch); self.assertNotIn('total', r)
            self.assertEqual(get.call_count, 2)
        for logistic, mode in LOGISTICS.items():
            value = item(); value['shipping'] = dict(logistic_type=logistic, mode=mode)
            get = requester([dict(id=123), value, fee()])
            self.assertEqual(quote('secret', 123, 'MLB100', get)['state'], 'quoted')

    def test_missing_is_unknown_explicit_zero_survives_no_duplicate_or_foreign_option(self):
        for patch in (dict(currency_id='ARS'), dict(listing_type_id='gold_pro'), dict(sale_fee_amount=None),
                      dict(sale_fee_amount=-1), dict(sale_fee_amount='Infinity'), dict(sale_fee_amount=True),
                      dict(sale_fee_amount='9999999'), dict(sale_fee_amount='1.001'),
                      dict(sale_fee_details=dict(fixed_fee=20))):
            value = fee(); value.update(patch); r = quote('secret', 123, 'MLB100', requester([dict(id=123), item(), value]))
            self.assertEqual(r['state'], 'unknown', patch); self.assertNotIn('total', r)
        for value in ([], [fee(), fee()], None, [[fee()]]):
            self.assertEqual(quote('secret', 123, 'MLB100', requester([dict(id=123), item(), value]))['state'], 'unknown')
        value = fee(); value.update(sale_fee_amount=0, sale_fee_details={})
        r = quote('secret', 123, 'MLB100', requester([dict(id=123), item(), value]))
        self.assertEqual(r['state'], 'quoted'); self.assertEqual(r['total'], 0); self.assertIsNone(r['fixed'])

    def test_http_network_invalid_json_no_retries_or_remote_error_leak(self):
        for status in (301, 401, 403, 429, 500):
            get = Mock(return_value=Mock(status_code=status, json=Mock(return_value=dict(message='secret-token'))))
            r = quote('secret-token', 123, 'MLB100', get)
            self.assertEqual(r['state'], 'unknown'); self.assertNotIn('secret-token', str(r))
            self.assertEqual(get.call_count, 1)
        for error in (requests.Timeout('secret-token'), requests.ConnectionError('secret-token'), ValueError('secret-token')):
            get = Mock(side_effect=error); r = quote('secret-token', 123, 'MLB100', get)
            self.assertEqual(r['state'], 'unknown'); self.assertNotIn('secret-token', str(r))
            self.assertEqual(get.call_count, 1)

    def test_render_blank_error_zero_and_escaped_context(self):
        blank = render(1, 'MLB100', '<script>', 'csrf')
        self.assertNotIn('<script>', blank); self.assertNotIn('id="fee-quote-result"', blank)
        self.assertNotIn('R$ 0,00', blank)
        value = fee(); value.update(sale_fee_amount=0, sale_fee_details={})
        result = quote('secret', 123, 'MLB100', requester([dict(id=123), item(), value]), NOW)
        html = render(1, 'MLB100', 'Título', 'csrf', result)
        self.assertIn('R$ 0,00', html); self.assertIn('Não informado', html)
        self.assertIn('15:45:00', html); self.assertIn('não converte financing_add_on_fee em reais', html)
        error = render(1, 'MLB100', 'Título', 'csrf', dict(state='unknown', message='<script>', checked_at=NOW))
        self.assertNotIn('<script>', error); self.assertNotIn('class="pf-metric"', error)


class FeeQuoteRouteTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__); self.app.secret_key = 'isolated'; self.app.testing = True
        install_security(self.app)
        self.query = Mock(return_value=[dict(id=1, cliente='Loja', titulo='Teste', user_id=123)])
        self.resolve = Mock(return_value='secret-token'); self.get = requester()
        def login(fn):
            @wraps(fn)
            def guard(*args, **kwargs):
                return fn(*args, **kwargs) if session.get('usuario_id') else redirect('/login')
            return guard
        register(self.app, login, lambda cid: cid == 1, lambda: contextlib.nullcontext(None), self.query,
                 lambda *args: args[-1], self.resolve, self.get)
        self.client = self.app.test_client(); self.path = '/anuncios/1/MLB100/cotacao-tarifa'
        with self.client.session_transaction() as s:
            s.update(usuario_id=1, tipo='admin', _csrf='test-token')

    def test_only_explicit_post_queries_api_get_is_blank_and_sql_is_scoped(self):
        self.assertEqual(self.client.get(self.path).status_code, 200)
        self.resolve.assert_not_called(); self.get.assert_not_called()
        result = self.client.post(self.path, data=dict(_csrf='test-token'))
        self.assertEqual(result.status_code, 200); self.assertIn('R$ 15,25', result.text)
        self.assertNotIn('secret-token', result.text); self.assertEqual(result.headers['Cache-Control'], 'no-store')
        self.resolve.assert_called_once(); self.assertEqual(self.get.call_count, 3)
        self.assertTrue(all(c.args[1].lstrip().startswith('SELECT') and c.args[2] == (1, 'MLB100')
                            for c in self.query.call_args_list))

    def test_auth_scope_unknown_listing_csrf_block_before_token_or_api(self):
        self.assertEqual(self.app.test_client().get(self.path).status_code, 302)
        with self.client.session_transaction() as s: s['tipo'] = 'cliente'
        self.assertEqual(self.client.post(self.path, data=dict(_csrf='test-token')).status_code, 403)
        with self.client.session_transaction() as s: s['tipo'] = 'admin'
        self.assertEqual(self.client.get(self.path.replace('/1/', '/2/')).status_code, 403)
        self.assertEqual(self.client.get(self.path.replace('MLB100', 'bad')).status_code, 404)
        self.assertEqual(self.client.post(self.path).status_code, 400)
        self.query.assert_not_called()
        self.query.return_value = []
        self.assertEqual(self.client.post(self.path, data=dict(_csrf='test-token')).status_code, 404)
        self.resolve.assert_not_called(); self.get.assert_not_called()

    def test_failed_connection_stays_unknown_without_zero(self):
        self.resolve.return_value = None
        result = self.client.post(self.path, data=dict(_csrf='test-token'))
        self.assertEqual(result.status_code, 200); self.assertIn('Sem cotação verificável', result.text)
        self.assertNotIn('R$ 0,00', result.text); self.get.assert_not_called()
